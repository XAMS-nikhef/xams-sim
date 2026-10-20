"""Load, validate and hash xams-sim configurations.

A simulation run is one YAML file (config/runs/<name>.yaml) that names a detector state and a source; everything else is
referenced:

    run  ─┬─ state  (config/states/<name>.yaml) ─┬─ detector ── config/detectors/<detector>/geometry.yaml (shapes,
          │                                       │               positions, which part is which material)
          │                                       └─ hv_case ── efield/cases.yaml (voltages, field cage, SiPMs)
          ├─ source (config/sources/<name>.yaml)
          └─ materials (config/materials.yaml: the single source of material properties incl. optics)

Several detectors can live side by side (e.g. today's XAMS, a future one with a SiPM top array): each state says which
one it describes, and every key (Geant4, maps, lineage) follows the resolved geometry, so runs of one detector never
make those of another old.

`resolve(run_path)` loads and checks all of it and returns a `Resolved` object; `Resolved.map_keys()` gives, per kind of
map, a short hash of exactly the inputs that map depends on (the map registry uses it to find or request maps).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
DETECTORS = CONFIG / "detectors"           # one folder per detector: geometry.yaml (+ its hole pattern etc.)
# where all outputs live (Geant4 runs, strax data, optical scans, maps, COMSOL results, check scratch): $XAMSSIM_DATA,
# else next to the code in the simulations folder (studies; a development checkout, e.g. on the Mac). A shared
# installation (STBC: software/xams-sim, no simulations folder next to it) refuses to run without $XAMSSIM_DATA, so
# that nothing is ever written into the software area.


class DataFolderError(RuntimeError):
    pass


def _data_folder() -> Path:
    if os.environ.get("XAMSSIM_DATA"):
        return Path(os.environ["XAMSSIM_DATA"]).resolve()
    studies = ROOT.parent / "simulations"
    if not studies.is_dir():
        raise DataFolderError(
            f"XAMSSIM_DATA is not set and there is no simulations folder next to {ROOT}: set XAMSSIM_DATA to your "
            "simulation data folder: in ~/.config/xamssim/env (a line XAMSSIM_DATA=/path; used by every terminal, "
            "Jupyter kernel and condor job), or in the environment (on STBC: source setup_xamssim.sh)")
    return (studies / "data").resolve()


DATA = _data_folder()
HV_CASES = ROOT / "efield" / "cases.yaml"

# data products of the chain, in order; `stop_after` must be one of them
PRODUCTS = ("geant4_interactions", "clustered_interactions", "quanta", "drifted_electrons", "extracted_electrons",
            "s2_photons", "photoelectrons", "events", "raw_records")

NUM = (int, float)
OPT_NUM = (int, float, type(None))
SCHEMA = {
    "run": ({"state": str, "source": str, "n_events": int, "seed": int, "stop_after": str, "physics": dict,
             "run_number": int},
            {"state", "source", "n_events", "seed"}),
    "state": ({"description": str, "detector": str, "hv_case": str, "liquid_level_mm": NUM, "pressure_bar": OPT_NUM,
               "electron_lifetime_us": OPT_NUM, "sensors": dict},
              {"detector", "hv_case", "liquid_level_mm"}),
    "source": ({"isotope": str, "activity_bq": OPT_NUM, "position_mm": (list, type(None)), "collimator": (dict, str, type(None)),
                "type": str, "energy_keV": OPT_NUM, "direction": str, "half_angle_deg": NUM, "z_target_mm": NUM,
                "description": str},
               {"isotope"}),
}
HV_KEYS = ("A", "G", "C", "BS", "TS", "PMT_T", "PMT_B", "SIPM")
MC_RUN_NUMBERS = (900000, 999999)       # run numbers of simulated runs (amstrax / the analysis address runs by number)


class ConfigError(ValueError):
    """A configuration file is missing, incomplete or inconsistent."""


def load_yaml(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"missing file: {path}")
    with open(path) as f:
        d = yaml.safe_load(f)
    if not isinstance(d, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return d


def check(d: dict, kind: str, where: str) -> None:
    keys, required = SCHEMA[kind]
    unknown = set(d) - set(keys)
    missing = required - set(d)
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {sorted(unknown)}; allowed: {sorted(keys)}")
    if missing:
        raise ConfigError(f"{where}: missing key(s) {sorted(missing)}")
    for k, v in d.items():
        if not isinstance(v, keys[k]) or (keys[k] is int and isinstance(v, bool)):
            raise ConfigError(f"{where}: '{k}' has type {type(v).__name__}, expected {keys[k]}")


def geometry_path(detector: str) -> Path:
    p = DETECTORS / detector / "geometry.yaml"
    if not p.exists():
        known = sorted(d.name for d in DETECTORS.iterdir() if (d / "geometry.yaml").exists()) if DETECTORS.exists() else []
        raise ConfigError(f"detector '{detector}': no {p} (known detectors: {known})")
    return p


def load_geometry(detector: str) -> dict:
    """The detector's geometry.yaml, with the files it refers to read in (mesh hole pattern), so that everything
    derived from it (keys, Geant4, COMSOL) follows their content."""
    p = geometry_path(detector)
    geo = load_yaml(p)
    mc = geo.get("mesh_common", {})
    if mc.get("hole_pattern_file") and "holes" not in mc:
        mc["holes"] = json.loads((p.parent / mc["hole_pattern_file"]).read_text())["holes"]
    return geo


def load_sensors(detector: str) -> dict:
    """The detector's sensors.yaml (sensor response per channel), {} if it has none."""
    p = geometry_path(detector).parent / "sensors.yaml"
    return load_yaml(p) if p.exists() else {}


def geometry_hash(geo: dict) -> str:
    """Hash of the physical geometry (what COMSOL, Geant4 and the maps depend on)."""
    return short_hash({k: v for k, v in geo.items() if k not in {"meta", "targets", "sources", "liquid"}})


def load_materials_and_geometry(detector: str) -> tuple:
    """The detector's geometry + materials.yaml, with the check that every material the geometry names is defined."""
    geo = load_geometry(detector)
    mat = load_yaml(CONFIG / "materials.yaml")
    for k in ("materials", "optics"):
        if k not in mat:
            raise ConfigError(f"materials.yaml: missing section '{k}'")
    for name, m in mat["materials"].items():
        if "density_g_cm3" not in m or "geant4" not in m or "electrical" not in m:
            raise ConfigError(f"materials.yaml: '{name}' needs density_g_cm3, geant4 and electrical")
        if m["electrical"].get("kind") not in ("conductor", "dielectric"):
            raise ConfigError(f"materials.yaml: '{name}' electrical.kind must be conductor or dielectric")
        if m["electrical"]["kind"] == "dielectric" and m["electrical"].get("relative_permittivity") is None:
            raise ConfigError(f"materials.yaml: dielectric '{name}' needs relative_permittivity")
    if "optics" in geo:
        raise ConfigError("geometry.yaml: optical properties belong in materials.yaml (single source)")
    used = {v["material"] for v in geo.values() if isinstance(v, dict) and "material" in v}
    pc = geo.get("pmt_common", {})
    used |= {pc.get("window_material"), pc.get("body_material")} - {None}
    unknown = sorted(used - set(mat["materials"]))
    if unknown:
        raise ConfigError(f"geometry.yaml uses materials not defined in materials.yaml: {unknown}")
    return geo, mat


def short_hash(obj) -> str:
    """Stable 12-character hash of a JSON-serialisable object (key order does not matter)."""
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def _named(kind: str, name: str) -> Path:
    return CONFIG / f"{kind}s" / f"{name}.yaml"


@dataclass
class Resolved:
    run_path: Path
    run: dict
    state_name: str
    state: dict
    source_name: str
    source: dict
    geometry: dict
    materials: dict
    detector: str
    hv_case: dict
    hv_global: dict          # efield/cases.yaml sections that apply to every case (field cage, SiPM model)

    # --- the inputs each kind of map depends on (only these enter its key) ---
    def _geometry_physical(self) -> dict:
        return {k: v for k, v in self.geometry.items() if k not in {"meta", "targets", "sources", "liquid"}}

    @property
    def geometry_path(self) -> Path:
        return geometry_path(self.detector)

    @property
    def sensors(self) -> dict:
        return load_sensors(self.detector)

    def map_inputs(self) -> dict:
        level = self.state["liquid_level_mm"]
        mats = self.materials["materials"]
        eps = {k: v["electrical"].get("relative_permittivity") for k, v in mats.items()}
        from .lightmap import MODEL
        light = {"geometry": self._geometry_physical(), "optics": self.materials["optics"], "liquid_level_mm": level,
                 "model": MODEL}
        hv = {k: self.hv_case[k] for k in HV_KEYS}
        field = {"geometry": self._geometry_physical(), "permittivity": eps, "hv": hv,
                 "hv_global": self.hv_global, "liquid_level_mm": level}
        cells = {"mesh_common": self.geometry.get("mesh_common"), "meshes": self.geometry.get("meshes"),
                 "hv": {k: hv[k] for k in ("A", "G", "C", "BS", "TS")}, "liquid_level_mm": level, "permittivity": eps,
                 "model": "quarter cell, gate and cathode (efield/comsol/make_cell.py)"}
        return {
            "field": field,
            "drift": {**field, "liquid": {"temperature_k": mats["liquid_xenon"].get("temperature_k"),
                                          "density_g_cm3": mats["liquid_xenon"].get("density_g_cm3"),
                                          "transport": {k: v for k, v in (mats["liquid_xenon"].get("transport") or {}).items()
                                                        if k in ("drift_velocity", "diffusion_longitudinal_cm2_s",
                                                                 "diffusion_transverse_cm2_s")}},
                      "mesh_cells": cells, "tracking": "driftmap v3: composite field (full TPC + mesh cells, cell average without x, y), against E, "
                                                      "NEST v(E), step 0.1 / 0.02 mm, grid 1 x 1 x 0.5 mm"},
            "mesh_cells": cells,
            "extraction_el": {"mesh_common": self.geometry.get("mesh_common"), "meshes": self.geometry.get("meshes"),
                              "hv": {k: hv[k] for k in ("A", "G", "C", "TS")}, "liquid_level_mm": level,
                              "pressure_bar": self.state.get("pressure_bar"), "permittivity": eps,
                              "gas": {k: mats["gas_xenon"].get(k) for k in ("density_g_cm3", "transport")},
                              "liquid_extraction": (mats["liquid_xenon"].get("transport") or {}).get("extraction"),
                              "model": "elmap v1: stack cell, anode aligned"},
            "s1_light": light,
            "s2_pattern": light,
        }

    def map_keys(self) -> dict:
        return {kind: short_hash(inp) for kind, inp in self.map_inputs().items()}

    def g4_materials(self) -> dict:
        """What Geant4 uses of materials.yaml: densities, compositions, state and the optics, not the electrical or
        transport properties (those belong to COMSOL and the chain)."""
        m = self.materials
        return {"materials": {n: {k: v for k, v in d.items() if k not in ("electrical", "transport")}
                              for n, d in m["materials"].items()}, "optics": m.get("optics")}

    def g4_key(self) -> str:
        """Hash of what the Geant4 particle run depends on: geometry, the materials as Geant4 uses them, liquid level,
        source (not its description), events, seed, production cut (not the HV, the maps or the chain settings)."""
        return short_hash({"geometry": self._geometry_physical(), "materials": self.g4_materials(),
                           "liquid_level_mm": self.state["liquid_level_mm"],
                           "source": {k: v for k, v in self.source.items() if k not in ("description", "activity_bq")},
                           "n_events": self.run["n_events"], "seed": self.run["seed"],
                           "production_cut_mm": (self.run.get("physics") or {}).get("production_cut_mm")})

    def run_key(self) -> str:
        """Hash of everything that defines the simulated run (for provenance / strax run ids)."""
        return short_hash({"run": self.run, "state": self.state, "source": self.source, "maps": self.map_keys()})


def resolve(run_path) -> Resolved:
    run_path = Path(run_path)
    run = load_yaml(run_path)
    check(run, "run", str(run_path))
    stop = run.get("stop_after", "raw_records")
    if stop not in PRODUCTS:
        raise ConfigError(f"{run_path}: stop_after '{stop}' is not a chain product {PRODUCTS}")
    if run["n_events"] <= 0:
        raise ConfigError(f"{run_path}: n_events must be > 0")
    if "run_number" in run and not MC_RUN_NUMBERS[0] <= run["run_number"] <= MC_RUN_NUMBERS[1]:
        raise ConfigError(f"{run_path}: run_number {run['run_number']} outside the MC range {MC_RUN_NUMBERS} "
                          f"(6 digits, after all data runs; amstrax compares run numbers as 6-digit strings)")

    sp = _named("state", run["state"])
    state = load_yaml(sp)
    check(state, "state", str(sp))
    src_p = _named("source", run["source"])
    source = load_yaml(src_p)
    check(source, "source", str(src_p))
    pos = source.get("position_mm")
    if pos is not None and (len(pos) != 3 or not all(isinstance(x, NUM) for x in pos)):
        raise ConfigError(f"{src_p}: position_mm must be [x, y, z] in mm or null")

    cases = load_yaml(HV_CASES)
    hv_name = state["hv_case"]
    if hv_name not in cases.get("cases", {}):
        raise ConfigError(f"{sp}: hv_case '{hv_name}' not in {HV_CASES} (known: {sorted(cases.get('cases', {}))})")
    hv_case = cases["cases"][hv_name]
    missing_hv = [k for k in HV_KEYS if k not in hv_case]
    if missing_hv:
        raise ConfigError(f"{HV_CASES}: case '{hv_name}' lacks {missing_hv}")

    geo, mat = load_materials_and_geometry(state["detector"])
    return Resolved(run_path=run_path, run=run, state_name=run["state"], state=state, source_name=run["source"],
                    source=source, geometry=geo, materials=mat, detector=state["detector"],
                    hv_case=hv_case, hv_global={k: cases[k] for k in ("field_cage",) if k in cases})


def resolve_state(state_name: str) -> Resolved:
    """Resolve a state without a run (for `xamssim maps --state`): a dummy run with a placeholder source."""
    tmp = {"state": state_name, "source": "_none", "n_events": 1, "seed": 0}
    sp = _named("state", state_name)
    state = load_yaml(sp)
    check(state, "state", str(sp))
    cases = load_yaml(HV_CASES)
    if state["hv_case"] not in cases.get("cases", {}):
        raise ConfigError(f"{sp}: hv_case '{state['hv_case']}' not in {HV_CASES}")
    geo, mat = load_materials_and_geometry(state["detector"])
    return Resolved(run_path=sp, run=tmp, state_name=state_name, state=state, source_name="-", source={},
                    geometry=geo, materials=mat, detector=state["detector"],
                    hv_case=cases["cases"][state["hv_case"]], hv_global={k: cases[k] for k in ("field_cage",) if k in cases})


def efield_detector(states: str = "", detector: str | None = None) -> str:
    """The detector of one COMSOL solve: that of the states (all the same), else --detector (default xams2026)."""
    if states:
        dets = {load_yaml(_named("state", n))["detector"] for n in states.split(",")}
        if len(dets) != 1:
            raise ConfigError(f"states {states} belong to different detectors {sorted(dets)}: solve them separately")
        d = dets.pop()
        if detector and detector != d:
            raise ConfigError(f"--detector {detector} differs from the states' detector {d}")
        return d
    return detector or "xams2026"


def efield_selection(states: str = "", cases: str = "", level: float | None = None) -> tuple[dict, float]:
    """HV cases and liquid level for one COMSOL solve (all cases of a solve share the geometry, so one level).

    states="sept,cmb50": the states' HV cases and their (common) liquid level — the normal way;
    cases="cmb_p100,..." + level: HV cases without a state (field studies), level given explicitly.
    """
    all_cases = load_yaml(HV_CASES)["cases"]
    if states:
        st = {n: load_yaml(_named("state", n)) for n in states.split(",")}
        levels = {s["liquid_level_mm"] for s in st.values()}
        if len(levels) != 1:
            raise ConfigError(f"states {sorted(st)} have different liquid levels {sorted(levels)}: solve them separately")
        lv = levels.pop()
        if level is not None and level != lv:
            raise ConfigError(f"--level {level} differs from the states' liquid level {lv} mm")
        names = list(dict.fromkeys(s["hv_case"] for s in st.values()))
        names += [c for c in (cases.split(",") if cases else []) if c not in names]
        return {n: all_cases[n] for n in names}, float(lv)
    if not cases or level is None:
        raise ConfigError("give --states (HV case and level from the states) or --cases with --level")
    return {n: all_cases[n] for n in cases.split(",")}, float(level)
