"""xams-sim command line — everything is started from the `xamssim` conda env (the Geant4 program xamsg4 is run in the
`g4` env automatically; `g4` only has to be activated to compile). <data> = xamssim.config.DATA
(default ../simulations/data, or $XAMSSIM_DATA).

    xamssim particle config/runs/<run>.yaml [--events N]   Geant4 particle mode -> <data>/g4/<run>/deposits.*  (plan S2)
    xamssim particle config/runs/vis_cs137.yaml --vis      particle viewer: look at a few events
    xamssim optical  <scan>.yaml           [--jobs 8]  optical simulation (scan) -> <data>/scans/<scan>/
    xamssim optical  <scan>.yaml           --vis       optical viewer for that scan (--point N; --list)
    xamssim chain    config/runs/<run>.yaml [--target quanta]  fuse micro-physics on <data>/g4/<run> -> <data>/strax/ (S3)
    xamssim status   config/runs/<run>.yaml                resolved state / source, input hashes, map status
    xamssim maps     --state cmb50                         map status for one detector state
    xamssim maps     --state cmb50 --export field          3D COMSOL field of the state -> <data>/maps/ (registered)
    xamssim maps     --state cmb50 --export drift          drift map (end points, drift times) from the field map
    xamssim validate config/runs/*.yaml                    check run files (and the states / sources they use)
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import ConfigError, resolve, resolve_state
from .maps import KINDS, MANIFEST, needed, status


def _print_maps(res, kinds) -> int:
    rows = status(res, kinds)
    n_missing = 0
    print(f"maps ({MANIFEST.relative_to(MANIFEST.parents[1])}):")
    for r in rows:
        if r["present"]:
            print(f"  [ok]      {r['kind']:<14} {r['key']}  {', '.join(r['files'])}")
        else:
            n_missing += 1
            print(f"  [missing] {r['kind']:<14} {r['key']}  make: {r['make']}   ({r['note']})")
    return n_missing


def cmd_status(a) -> int:
    res = resolve(a.run)
    run, st, src, hv = res.run, res.state, res.source, res.hv_case
    stop = run.get("stop_after", "raw_records")
    print(f"run        {res.run_path}   (run key {res.run_key()})")
    print(f"           {run['n_events']} events, seed {run['seed']}, stop after {stop}, physics {run.get('physics', {})}")
    print(f"state      {res.state_name}: {st.get('description', '')}")
    print(f"           hv_case {st['hv_case']}: A {hv['A']}  G {hv['G']}  C {hv['C']}  BS {hv['BS']}  TS {hv['TS']}  "
          f"PMT {hv['PMT_T']}/{hv['PMT_B']}  SiPM {hv['SIPM']} V")
    print(f"           level {st['liquid_level_mm']} mm, pressure {st.get('pressure_bar')} bar, "
          f"electron lifetime {st.get('electron_lifetime_us')} µs")
    print(f"source     {res.source_name}: {src.get('isotope')} at {src.get('position_mm')} mm, collimator {src.get('collimator')}")
    print(f"geometry   config/geometry.yaml (version {res.geometry.get('meta', {}).get('version')}), config/materials.yaml")
    print(f"chain      Geant4 particle mode -> {' -> '.join(('clustered_interactions', 'quanta', 'drifted_electrons', 'extracted_electrons', 's2_photons', 'photoelectrons', 'raw_records'))}")
    print("           (Geant4 particle mode: xamssim particle; up to quanta: xamssim chain; S4-S8 not yet available)")
    missing = _print_maps(res, needed(stop))
    print(f"{missing} of {len(needed(stop))} maps needed for '{stop}' missing")
    return 0


def cmd_maps(a) -> int:
    res = resolve_state(a.state)
    if a.export:
        from . import fieldmap
        from . import cellmap, driftmap
        e = {"field": fieldmap.export, "cells": cellmap.export, "drift": driftmap.export}[a.export](res)
        print(f"registered {e['kind']} {e['key']}: maps/{e['files'][0]}  ({e['producer_version']})")
    print(f"state {a.state} (hv_case {res.state['hv_case']}, level {res.state['liquid_level_mm']} mm)")
    _print_maps(res, list(KINDS))
    return 0


def cmd_validate(a) -> int:
    bad = 0
    for p in a.runs:
        try:
            res = resolve(p)
            from .chain import physics
            physics(res)
            print(f"ok       {p}  (state {res.state_name}, source {res.source_name}, run key {res.run_key()})")
        except ConfigError as e:
            bad += 1
            print(f"INVALID  {e}")
    return 1 if bad else 0


def cmd_particle(a) -> int:
    from .particle import run, vis
    if a.vis:
        vis(a.run, out_dir=a.out)
    else:
        run(a.run, n_events=a.events, seed=a.seed, out_dir=a.out, dry_run=a.dry_run)
    return 0


def cmd_chain(a) -> int:
    from .chain import run
    return run(a.run, target=a.target, g4_out=a.g4)


def cmd_optical(a) -> int:
    from .optical import list_points, scan, vis
    if a.list:
        list_points(a.scan)
        return 0
    if a.vis:
        vis(a.scan, point=a.point)
        return 0
    return scan(a.scan, jobs=a.jobs, dry=a.dry)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="xamssim", description="XAMS simulation chain (xams-sim)")
    ap.add_argument("--version", action="version", version=f"xamssim {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status", help="resolved run configuration and map status")
    p.add_argument("run")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("maps", help="map status for one detector state")
    p.add_argument("--state", required=True)
    p.add_argument("--export", choices=["field", "cells", "drift"],
                   help="make a map and register it (field: 3D field from the solved COMSOL model, needs the licence; "
                        "cells: mesh-cell fields of gate and cathode from the solved cell models, needs the licence; "
                        "drift: electron end points and drift times in the composite field)")
    p.set_defaults(func=cmd_maps)
    p = sub.add_parser("validate", help="check run configuration files")
    p.add_argument("runs", nargs="+")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("particle", help="Geant4 particle mode: production (energy deposits) or --vis viewer")
    p.add_argument("run")
    p.add_argument("--events", type=int, help="number of primaries (default: n_events of the run)")
    p.add_argument("--seed", type=int)
    p.add_argument("--out", help="output folder (default <data>/g4/<run name>)")
    p.add_argument("--dry-run", action="store_true", help="write config.json and run.mac, do not run Geant4")
    p.add_argument("--vis", action="store_true", help="interactive Qt viewer (then /run/beamOn N in the window)")
    p.set_defaults(func=cmd_particle)
    p = sub.add_parser("chain", help="simulation chain (strax / fuse) on the Geant4 output of a run")
    p.add_argument("run")
    p.add_argument("--target", choices=["geant4_interactions", "clustered_interactions", "quanta", "drifted_electrons"],
                   help="last product (default: the run's stop_after, at most the last implemented one)")
    p.add_argument("--g4", help="Geant4 output folder (default <data>/g4/<run name>)")
    p.set_defaults(func=cmd_chain)
    p = sub.add_parser("optical", help="optical simulation from a scan file: production, or --vis viewer")
    p.add_argument("scan", help="scan file, e.g. config/scans/example_s2.yaml")
    p.add_argument("--jobs", type=int, default=8)
    p.add_argument("--dry", action="store_true", help="list the scan points, do not run")
    p.add_argument("--vis", action="store_true", help="interactive Qt viewer for one point of the scan")
    p.add_argument("--point", type=int, default=0, help="scan point for the viewer (default 0)")
    p.add_argument("--list", action="store_true", help="list the scan points (number and parameter values)")
    p.set_defaults(func=cmd_optical)
    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except ConfigError as e:
        print(f"configuration error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
