"""The simulation chain as a strax context: one run file -> every setting (plan S3: up to `quanta`).

    xamssim chain config/runs/cs137_cmb50_001.yaml                 # -> <data>/strax/, prints a summary
    st, run_id = chain.context("config/runs/cs137_cmb50_001.yaml")
    st.get_array(run_id, "microphysics_summary")

Plugins (fuse 1.6.3 unless noted):
    geant4_interactions      XamsG4Input (xamssim.plugins)  — <data>/g4/<run>/deposits.*
    clustered_interactions   LineageClustering + MergeLineage   (physics.clustering: lineage, default)
                             FindCluster + MergeCluster         (physics.clustering: dbscan)
    volume_properties, interactions_in_roi                      XamsVolumeProperties, XamsVolumeSelection (xamssim.plugins:
                                                                four XAMS volumes, all kept), fuse DefaultSimulation
    electric_field_values    XamsElectricField (xamssim.plugins) — |E| at (x, y, z) from the state's 3D field map
    quanta                   NestYields — NEST with the local field and the xenon density of the volume
    microphysics_summary     MicroPhysicsSummary

All settings come from the configuration (fuse plugin defaults are XENONnT values; every one that matters is set):
    volumes (cm)   drift region  gate mesh z .. cathode z, r < PTFE cylinder inner radius          (geometry.yaml)
                   below cathode cathode z .. bottom PMT window, same radius
                   above gate    gate .. liquid surface (gate + liquid level of the state)
                   gas           liquid surface .. top PMT window
    densities      liquid / gas xenon from materials.yaml
    field          <data>/maps/field/<key>/efield_xyz.npz of the state (3D, from the COMSOL model)
    NEST           default NEST ER / NR models (parameters -1), no extra width parameters

Clustering and timeline options come from the run file's `physics` block (PHYSICS_DEFAULTS).
"""
from __future__ import annotations

import warnings
from pathlib import Path

from .config import DATA, ROOT, ConfigError, Resolved, resolve

# physics options of a run file and their defaults
PHYSICS_DEFAULTS = {
    "clustering": "lineage",           # lineage | dbscan
    "source_rate_hz": 100.0,           # events placed on the timeline at this rate (fuse source_rate)
    "time_threshold_ns": 10.0,         # lineage: break the lineage after this time gap
    "gamma_distance_threshold_cm": 0.0,  # lineage: do not break a gamma lineage within this distance
    "brem_distance_threshold_cm": 0.0,   # lineage: same for bremsstrahlung
    "micro_separation_cm": 0.005,      # dbscan: cluster size
    "micro_separation_time_ns": 10.0,  # dbscan: time window
    "production_cut_mm": 0.1,          # Geant4 (particle mode), not used here
}

STORE = DATA / "strax"


def physics(res: Resolved) -> dict:
    p = dict(res.run.get("physics") or {})
    unknown = set(p) - set(PHYSICS_DEFAULTS)
    if unknown:
        raise ConfigError(f"{res.run_path}: unknown physics options {sorted(unknown)} (known: {sorted(PHYSICS_DEFAULTS)})")
    out = {**PHYSICS_DEFAULTS, **p}
    if out["clustering"] not in ("lineage", "dbscan"):
        raise ConfigError(f"{res.run_path}: physics.clustering must be lineage or dbscan, not '{out['clustering']}'")
    return out


def volumes(res: Resolved) -> dict:
    """The two boundaries XamsVolumeProperties needs (cm): liquid surface and field-cage radius; the regions inside
    come from the drift map."""
    g = res.geometry
    z_gate = next(m["z_mm"] for m in g["meshes"] if m["name"] == "gate")
    return dict(z_liquid_cm=(z_gate + res.state["liquid_level_mm"]) / 10,
                r_field_cage_cm=g["ptfe_cylinder"]["inner_diameter_mm"] / 20)


def plugins(clustering: str) -> list:
    import fuse

    from .plugins import (XamsElectricField, XamsElectronDrift, XamsExtractionEL, XamsG4Input, XamsVolumeProperties,
                          XamsVolumeSelection)
    mp = fuse.micro_physics
    clus = ([mp.LineageClustering, mp.MergeLineage] if clustering == "lineage" else [mp.FindCluster, mp.MergeCluster])
    return [XamsG4Input, 
            *clus, 
            XamsVolumeProperties, 
            XamsVolumeSelection,
            mp.cuts_and_selections.DefaultSimulation, 
            XamsElectricField, 
            mp.NestYields, 
            mp.MicroPhysicsSummary,
            XamsElectronDrift,
            XamsExtractionEL]


def _el_settings(res: Resolved, xams_el_map: str | None) -> dict:
    """Settings of the extraction / EL step; the map only if it exists (it is needed for extracted_electrons only)."""
    from . import elmap
    g = res.geometry
    z = {m["name"]: m for m in g["meshes"]}
    out = dict(gate_angle_deg=z["gate"].get("angle_to_anodes_deg", 0.0), mesh_pitch_mm=g["mesh_common"]["pitch_mm"],
               z_anode_cm=z["anode"]["z_mm"] / 10)
    try:
        out["xams_el_map"] = str(xams_el_map or elmap.path(res))
    except FileNotFoundError:
        pass
    return out


def settings(res: Resolved, g4_dir: Path, xams_efield_map: str | None = None, g4_output_hash: str | None = None,
             xams_drift_map: str | None = None, xams_el_map: str | None = None) -> dict:
    from . import driftmap, fieldmap, g4io
    p = physics(res)
    mats = res.materials["materials"]
    lxe, gxe = mats["liquid_xenon"]["density_g_cm3"], mats["gas_xenon"]["density_g_cm3"]
    return dict(
        path=str(g4_dir), file_name="deposits", g4_output_hash=g4_output_hash or g4io.output_hash(g4_dir),
        preselect_r_max_cm=volumes(res)["r_field_cage_cm"],
        source_rate=p["source_rate_hz"], n_interactions_per_chunk=1e5,
        first_chunk_left=0,                      # fuse default 1 ms: negative chunk start if the first event is earlier
        # clustering
        **(dict(time_threshold=p["time_threshold_ns"], gamma_distance_threshold=p["gamma_distance_threshold_cm"],
                brem_distance_threshold=p["brem_distance_threshold_cm"]) if p["clustering"] == "lineage" else
           dict(micro_separation=p["micro_separation_cm"], micro_separation_time=p["micro_separation_time_ns"],
                tag_cluster_by="energy")),
        # volumes, densities
        **volumes(res),
        density_liquid_g_cm3=lxe, density_gas_g_cm3=gxe,
        # field, NEST
        xams_efield_map=str(xams_efield_map or fieldmap.path(res)),
        nest_er_yields_parameters=-1, nest_nr_yields_parameters=-1, nest_width_parameters={},
        # drift (S4): drift map of the state, lifetime of the state, diffusion of the liquid
        xams_drift_map=str(xams_drift_map or driftmap.path(res)),
        **({"electron_lifetime_us": res.state["electron_lifetime_us"]} if res.state.get("electron_lifetime_us") else {}),
        diffusion_longitudinal_cm2_s=mats["liquid_xenon"]["transport"]["diffusion_longitudinal_cm2_s"],
        diffusion_transverse_cm2_s=mats["liquid_xenon"]["transport"]["diffusion_transverse_cm2_s"],
        # extraction and EL (S5)
        **_el_settings(res, xams_el_map),
    )


def g4_dir(res: Resolved) -> Path:
    return DATA / "g4" / res.run_path.stem


def context(run_path, g4_out=None, store=STORE, **overrides):
    """(strax context, run id) for a run file. `overrides`: fuse options on top of the configuration (studies)."""
    import strax
    warnings.filterwarnings("ignore", module="straxen|utilix|fuse")
    res = resolve(run_path)
    gdir = Path(g4_out) if g4_out else g4_dir(res)
    if not (gdir / "deposits.json").exists():
        raise ConfigError(f"no Geant4 output in {gdir}: xamssim particle {res.run_path}")
    cfg = settings(res, gdir, xams_efield_map=overrides.get("xams_efield_map"),
                   xams_drift_map=overrides.get("xams_drift_map"), xams_el_map=overrides.get("xams_el_map"))
    cfg.update(overrides)
    st = strax.Context(storage=[strax.DataDirectory(str(store))], register=plugins(physics(res)["clustering"]),
                       config=cfg)
    st.set_context_config({"check_available": ()})
    _check_g4(res, gdir)
    return st, res.run_path.stem


def _check_g4(res: Resolved, gdir: Path) -> None:
    """Warn when the Geant4 output was made for another Geant4 configuration than the run file now gives (geometry,
    materials, liquid level, source, events, seed; Resolved.g4_key). The data stay consistent either way: the Geant4
    output hash is in the lineage."""
    import json
    try:
        made = json.loads((gdir / "config.json").read_text()).get("xamssim", {}).get("g4_key")
    except (OSError, ValueError):
        return
    if made and made != res.g4_key():
        print(f"WARNING: {gdir.name}: Geant4 output made for another Geant4 configuration (g4 key {made}, the run "
              f"file now gives {res.g4_key()}): rerun xamssim particle {res.run_path.name} if Geant4 should follow")


# chain products (config.PRODUCTS) implemented so far -> strax data type
TARGETS = {"geant4_interactions": "geant4_interactions", "clustered_interactions": "clustered_interactions",
           "quanta": "microphysics_summary", "drifted_electrons": "drifted_electrons",
           "extracted_electrons": "extracted_electrons", "s2_photons": "extracted_electrons"}


def run(run_path, target: str | None = None, g4_out=None, lifetime_us: float | None = None) -> int:
    """Process a run up to `target` (default: the run's stop_after, at most the last implemented product)."""
    import time

    import numpy as np

    from .config import PRODUCTS
    res = resolve(run_path)
    stop = res.run.get("stop_after", "raw_records")
    if target is None:
        done = [p for p in PRODUCTS[: PRODUCTS.index(stop) + 1] if p in TARGETS]
        target = done[-1]
        if target != stop:
            print(f"stop_after '{stop}' not implemented yet; processing up to '{target}'")
    if target not in TARGETS:
        raise ConfigError(f"target '{target}' not implemented (available: {list(TARGETS)})")
    if PRODUCTS.index(target) >= PRODUCTS.index("drifted_electrons") and not (lifetime_us or res.state.get("electron_lifetime_us")):
        raise ConfigError(f"state '{res.state_name}' has no electron_lifetime_us (needed for the drift): set it in the "
                          f"state or give --lifetime-us")
    over = {"electron_lifetime_us": float(lifetime_us)} if lifetime_us else {}
    if over:
        print(f"electron lifetime {lifetime_us} µs (given on the command line; state: {res.state.get('electron_lifetime_us')})")
    st, run_id = context(run_path, g4_out=g4_out, **over)
    t0 = time.time()
    # store the clusters and their volumes too (all clusters, also the dropped ones), then the target; fuse saves a
    # product only when it is the single target of a request (SaveWhen.TARGET), hence one make per product
    if target in ("quanta", "drifted_electrons", "extracted_electrons", "s2_photons"):
        keep = ["clustered_interactions", "volume_properties"] + (["microphysics_summary"] if target != "quanta" else []) \
            + (["drifted_electrons"] if target in ("extracted_electrons", "s2_photons") else [])
        for t in keep:                                   # NEST stored too: every later step reads the same draw
            st.make(run_id, t)
    d = st.get_array(run_id, TARGETS[target])
    print(f"run {res.run_path.name} (run id {run_id}): {TARGETS[target]} — {len(d)} rows, "
          f"{len(np.unique(d['eventid'])) if len(d) and 'eventid' in d.dtype.names else '-'} events, "
          f"{time.time() - t0:.0f} s; stored in {STORE}")
    from .plugins import VOLUME_NAMES
    if "vol_id" in (d.dtype.names or ()):
        for v, name in VOLUME_NAMES.items():
            m = d["vol_id"] == v
            print(f"  {name:<14} {m.sum():8d} clusters, mean {d['ed'][m].mean() if m.any() else 0:6.1f} keV")
    if "n_s2_photons" in (d.dtype.names or ()):
        dr = st.get_array(run_id, "drifted_electrons", progress_bar=False)
        m = dr["n_electron_interface"] > 0
        print(f"  electrons at the surface {dr['n_electron_interface'].sum():12d}, extracted {d['n_electron_extracted'].sum():12d} "
              f"({d['n_electron_extracted'].sum() / max(1, dr['n_electron_interface'].sum()):.3f}); S2 photons "
              f"{d['n_s2_photons'].sum():.3e}, {np.median(d['el_photons_per_electron'][m]):.0f} per electron (median), "
              f"S2 width50 {np.median(d['s2_width50'][m]):.0f} ns (median of the clusters)")
    if "drift_end" in (d.dtype.names or ()):
        from .driftmap import CODES
        q = st.get_array(run_id, "microphysics_summary", progress_bar=False)
        for c, name in CODES.items():
            m = d["drift_end"] == c
            if m.any():
                print(f"  electrons ending at {name:<8} {m.sum():8d} clusters, {q['electrons'][m].sum():12d} electrons made, "
                      f"{d['n_electron_interface'][m].sum():12d} at the surface")
    return 0
