#!/usr/bin/env python3
"""geometry.yaml + materials.yaml -> config.json for the Geant4 application (which reads JSON only).

Picks one liquid-level scenario and one value for every free optical parameter (a range [lo, hi] in the YAML means
"free": the midpoint is used unless overridden with --set), checks that every value the simulation needs is present,
and adds derived quantities (liquid surface z, mesh list sorted by z).

    python optical/make_config.py --level 4.0 --out run/config.json
    python optical/make_config.py --level 2.0 --set optics.ptfe_in_gas.reflectivity=0.75 --out run/scan_01.json
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# values the v1 simulation cannot run without (dotted paths into the YAML)
REQUIRED = ["mesh_common.foil_thickness_mm", "mesh_common.hole_size_mm", "mesh_common.bar_width_mm",
            "mesh_common.pitch_mm", "mesh_common.foil_diameter_mm", "ptfe_cylinder.inner_diameter_mm",
            "ptfe_cylinder.length_mm", "ptfe_cylinder.z_top_mm", "mesh_common.ring.inner_diameter_mm", "pmt_common.photocathode_square_mm",
            "pmt_common.window_thickness_mm", "pmt_common.window_face_square_mm"]
# second-order values with a default if still open
DEFAULTS = {"ptfe_bucket.bottom_thickness_mm": 10.0,       # not on the drawing (2026-10-06): = wall
            "cryostat_vessel.end_thickness_mm": 2.77,      # not on the drawing: = wall
            "cryostat_vessel.bottom_gap_mm": 10.0}         # vessel inner bottom to bucket bottom: not known


def get(d, path):
    for k in path.split("."):
        d = d[int(k)] if isinstance(d, list) else d[k]
    return d


def put(d, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d[int(k)] if isinstance(d, list) else d[k]
    last = keys[-1]
    if isinstance(d, list):
        d[int(last)] = value
    else:
        d[last] = value


def pick_free(x):
    """[lo, hi] -> midpoint (free parameter); recurse into dicts / lists of dicts"""
    if isinstance(x, dict):
        return {k: pick_free(v) for k, v in x.items()}
    if isinstance(x, list) and len(x) == 2 and all(isinstance(v, (int, float)) for v in x):
        return 0.5 * (x[0] + x[1])
    if isinstance(x, list):
        return [pick_free(v) for v in x]
    return x


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--geometry", default=str(ROOT / "config" / "geometry.yaml"))
    ap.add_argument("--materials", default=str(ROOT / "config" / "materials.yaml"))
    ap.add_argument("--level", type=float, required=True, help="liquid level above the gate (mm)")
    ap.add_argument("--set", action="append", default=[], help="override, e.g. optics.lxe.rayleigh_length_cm=40")
    ap.add_argument("--out", default=str(ROOT / "run" / "config.json"))
    args = ap.parse_args()

    g = yaml.safe_load(open(args.geometry))
    mat = yaml.safe_load(open(args.materials))
    g["optics"] = mat["optics"]          # materials.yaml is the single source of the optical properties
    missing = []
    for p in REQUIRED:
        try:
            if get(g, p) is None:
                missing.append(p)
        except (KeyError, IndexError):
            missing.append(p)
    for p, v in DEFAULTS.items():
        if get(g, p) is None:
            put(g, p, v)
            print(f"default used: {p} = {v}")
    for i, m in enumerate(g["meshes"]):
        if m.get("z_mm") is None:
            missing.append(f"meshes.{i}.z_mm ({m['name']})")
    for i, p in enumerate(g["pmts"]):
        if p.get("window_z_mm") is None:
            missing.append(f"pmts.{i}.window_z_mm ({p['name']})")
    if missing:
        print("MISSING (fill in geometry.yaml):", *missing, sep="\n  ")
        return 1

    cfg = {k: g[k] for k in ("mesh_common", "meshes", "ptfe_cylinder", "field_shaping_rings", "pmt_common", "pmts", "sipms", "pmt_ptfe",
                                "ptfe_bucket", "cryostat_vessel") if k in g}
    hp = g["mesh_common"].get("hole_pattern_file")
    if hp:
        cfg["mesh_common"]["holes"] = json.load(open(Path(args.geometry).parent / hp))["holes"]
    cfg["optics"] = pick_free(g["optics"])
    # material properties for Geant4: density, NIST name or composition, state / temperature / pressure
    cfg["materials"] = {k: {kk: vv for kk, vv in v.items() if kk != "electrical"} for k, v in mat["materials"].items()}
    used = {g[k]["material"] for k in g if isinstance(g[k], dict) and "material" in g[k]}
    used |= {g["pmt_common"].get("window_material"), g["pmt_common"].get("body_material")} - {None}
    unknown = sorted(used - set(mat["materials"]))
    if unknown:
        print("geometry.yaml uses materials not defined in materials.yaml:", unknown)
        return 1
    cfg["liquid"] = {"level_above_gate_mm": args.level, "surface_z_mm": args.level}
    cfg["meshes"] = sorted(cfg["meshes"], key=lambda m: -m["z_mm"])
    for s in args.set:
        path, val = s.split("=", 1)
        try:
            val = json.loads(val)
        except json.JSONDecodeError:
            pass
        put(cfg, path, val)
    anode = next(m["z_mm"] for m in cfg["meshes"] if m["name"] == "anode")
    if not 0 < args.level < anode:
        print(f"liquid level {args.level} mm must lie between the gate (0) and the anode ({anode})")
        return 1
    cfg["meta"] = {"geometry": str(Path(args.geometry).resolve()), "geometry_version": g["meta"]["version"],
                   "materials": str(Path(args.materials).resolve()),
                   "overrides": args.set}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(cfg, open(args.out, "w"), indent=1)
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
