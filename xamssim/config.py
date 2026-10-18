"""Load, validate and hash xams-sim configurations.

A simulation run is one YAML file (config/runs/<name>.yaml) that names a detector state and a source; everything else is
referenced:

    run  ─┬─ state  (config/states/<name>.yaml) ── hv_case ── efield/cases.yaml (electrode voltages, field cage, SiPMs)
          ├─ source (config/sources/<name>.yaml)
          ├─ geometry (config/geometry.yaml: shapes, positions, which part is which material)
          └─ materials (config/materials.yaml: the single source of material properties incl. optics)

`resolve(run_path)` loads and checks all of it and returns a `Resolved` object; `Resolved.map_keys()` gives, per kind of
map, a short hash of exactly the inputs that map depends on (the map registry uses it to find or request maps).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
HV_CASES = ROOT / "efield" / "cases.yaml"

# data products of the chain, in order; `stop_after` must be one of them
PRODUCTS = ("geant4_interactions", "clustered_interactions", "quanta", "drifted_electrons", "extracted_electrons",
            "s2_photons", "photoelectrons", "raw_records")

NUM = (int, float)
OPT_NUM = (int, float, type(None))
SCHEMA = {
    "run": ({"state": str, "source": str, "n_events": int, "seed": int, "stop_after": str, "physics": dict},
            {"state", "source", "n_events", "seed"}),
    "state": ({"description": str, "hv_case": str, "liquid_level_mm": NUM, "pressure_bar": OPT_NUM,
               "electron_lifetime_us": OPT_NUM, "sensors": dict},
              {"hv_case", "liquid_level_mm"}),
    "source": ({"isotope": str, "activity_bq": OPT_NUM, "position_mm": (list, type(None)), "collimator": (dict, str, type(None)),
                "type": str, "energy_keV": OPT_NUM, "direction": str, "half_angle_deg": NUM, "z_target_mm": NUM,
                "description": str},
               {"isotope"}),
}
HV_KEYS = ("A", "G", "C", "BS", "TS", "PMT_T", "PMT_B", "SIPM")


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


def load_materials_and_geometry() -> tuple:
    """geometry.yaml + materials.yaml, with the check that every material the geometry names is defined."""
    geo = load_yaml(CONFIG / "geometry.yaml")
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
    hv_case: dict
    hv_global: dict          # efield/cases.yaml sections that apply to every case (field cage, SiPM model)

    # --- the inputs each kind of map depends on (only these enter its key) ---
    def _geometry_physical(self) -> dict:
        return {k: v for k, v in self.geometry.items() if k not in {"meta", "targets", "sources", "liquid"}}

    def map_inputs(self) -> dict:
        level = self.state["liquid_level_mm"]
        mats = self.materials["materials"]
        eps = {k: v["electrical"].get("relative_permittivity") for k, v in mats.items()}
        light = {"geometry": self._geometry_physical(), "optics": self.materials["optics"], "liquid_level_mm": level}
        hv = {k: self.hv_case[k] for k in HV_KEYS}
        field = {"geometry": self._geometry_physical(), "permittivity": eps, "hv": hv,
                 "hv_global": self.hv_global, "liquid_level_mm": level}
        return {
            "field": field,
            "drift": {**field, "drift_model": "v(E) + diffusion (S4)"},
            "extraction_el": {"mesh_common": self.geometry.get("mesh_common"), "meshes": self.geometry.get("meshes"),
                              "hv": {k: hv[k] for k in ("A", "G", "C", "TS")}, "liquid_level_mm": level,
                              "pressure_bar": self.state.get("pressure_bar"), "permittivity": eps},
            "s1_light": light,
            "s2_pattern": light,
        }

    def map_keys(self) -> dict:
        return {kind: short_hash(inp) for kind, inp in self.map_inputs().items()}

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
    if cases.get("liquid_level_mm") is not None and cases["liquid_level_mm"] != state["liquid_level_mm"]:
        raise ConfigError(f"liquid level differs: state {sp.name} {state['liquid_level_mm']} mm, "
                          f"{HV_CASES.name} {cases['liquid_level_mm']} mm (the field maps use the latter)")

    geo, mat = load_materials_and_geometry()
    return Resolved(run_path=run_path, run=run, state_name=run["state"], state=state, source_name=run["source"],
                    source=source, geometry=geo, materials=mat,
                    hv_case=hv_case, hv_global={k: cases[k] for k in ("field_cage", "sipm") if k in cases})


def resolve_state(state_name: str) -> Resolved:
    """Resolve a state without a run (for `xamssim maps --state`): a dummy run with a placeholder source."""
    tmp = {"state": state_name, "source": "_none", "n_events": 1, "seed": 0}
    sp = _named("state", state_name)
    state = load_yaml(sp)
    check(state, "state", str(sp))
    cases = load_yaml(HV_CASES)
    if state["hv_case"] not in cases.get("cases", {}):
        raise ConfigError(f"{sp}: hv_case '{state['hv_case']}' not in {HV_CASES}")
    geo, mat = load_materials_and_geometry()
    return Resolved(run_path=sp, run=tmp, state_name=state_name, state=state, source_name="-", source={},
                    geometry=geo, materials=mat,
                    hv_case=cases["cases"][state["hv_case"]], hv_global={k: cases[k] for k in ("field_cage", "sipm") if k in cases})
