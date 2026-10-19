"""xams-sim command line — everything is started from the `xamssim` conda env (the Geant4 program xamsg4 is run in the
`g4` env automatically; `g4` only has to be activated to compile). <data> = xamssim.config.DATA
(default ../simulations/data, or $XAMSSIM_DATA).

    xamssim particle config/runs/<run>.yaml [--events N]   Geant4 particle mode -> <data>/g4/<run>/deposits.*
    xamssim particle config/runs/vis_cs137.yaml --vis      particle viewer: look at a few events
    xamssim optical  <scan>.yaml [--jobs 8]                optical simulation (scan) -> <data>/scans/<scan>/
    xamssim optical  <scan>.yaml --vis [--point N]         optical viewer for a point of the scan (--list: the points)
    xamssim chain    config/runs/<run>.yaml [--target T]   simulation chain on <data>/g4/<run> -> <data>/strax/ (up to photoelectrons)
    xamssim status   config/runs/<run>.yaml                resolved state / source, input hashes, map status
    xamssim maps     --state cmb50                         map status for one detector state
    xamssim maps     --state cmb50 --export field          3D field of the state from the solved COMSOL model (licence)
    xamssim maps     --state cmb50 --export cells          gate and cathode mesh-cell fields from the cell models (licence)
    xamssim maps     --state cmb50 --export drift          drift map in the composite field (field + mesh cells)
    xamssim maps     --state cmb50 --export el             extraction / EL map from the gate + anode cell (licence)
    xamssim maps     --state cmb50 --export light          S1 / S2 light maps per channel (Geant4 optical, ~5 min)
    xamssim validate config/runs/*.yaml                    check run files (and the states / sources they use)
    xamssim list     [filter] [--prune | --delete]         runs, Geant4 output, strax products (current / old), maps;
                                                          --delete removes the old data after a confirmation
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
    print("           (Geant4 particle mode: xamssim particle; up to photoelectrons: xamssim chain; S7-S8 not yet available)")
    missing = _print_maps(res, needed(stop))
    print(f"{missing} of {len(needed(stop))} maps needed for '{stop}' missing")
    return 0


def cmd_maps(a) -> int:
    res = resolve_state(a.state)
    if a.export:
        from . import fieldmap
        from . import cellmap, driftmap, elmap, lightmap
        light = lambda r: lightmap.export(r, a.photons_s1, a.photons_s2, a.jobs)  # noqa: E731
        e = {"field": fieldmap.export, "cells": cellmap.export, "drift": driftmap.export, "el": elmap.export,
             "light": light}[a.export](res)
        for x in (e if isinstance(e, list) else [e]):                    # light: s1_light and s2_pattern
            print(f"registered {x['kind']} {x['key']}: maps/{x['files'][0]}  ({x['producer_version']})")
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
    return run(a.run, target=a.target, g4_out=a.g4, lifetime_us=a.lifetime_us)


def cmd_list(a) -> int:
    from .listing import show
    return show(a.filter or "", prune=a.prune, delete=a.delete, yes=a.yes)


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
    p.add_argument("--export", choices=["field", "cells", "drift", "el", "light"],
                   help="make a map and register it (field: 3D field from the solved COMSOL model, needs the licence; "
                        "cells: mesh-cell fields of gate and cathode from the solved cell models, needs the licence; "
                        "drift: electron end points and drift times in the composite field; "
                        "el: extraction and electroluminescence from the gate + anode cell, needs the licence; "
                        "light: S1 and S2 light maps per channel from Geant4 optical runs, ~5 min)")
    p.add_argument("--photons-s1", type=float, default=5e7, help="light: photons for the S1 map (default 5e7)")
    p.add_argument("--photons-s2", type=float, default=2e7, help="light: photons for the S2 map (default 2e7)")
    p.add_argument("--jobs", type=int, default=8, help="light: parallel Geant4 runs (default 8)")
    p.set_defaults(func=cmd_maps)
    p = sub.add_parser("list", help="what is in the data folder: runs, Geant4 output, strax products (current or "
                                    "old for the run file as it is now), maps per state")
    p.add_argument("filter", nargs="?", help="only run ids containing this text")
    p.add_argument("--prune", action="store_true", help="also list the old data with its size (never deletes)")
    p.add_argument("--delete", action="store_true", help="delete the old data (Geant4 output for another Geant4 key, "
                                                         "strax products with an old lineage, unused maps) after a "
                                                         "confirmation")
    p.add_argument("--yes", action="store_true", help="with --delete: no confirmation")
    p.set_defaults(func=cmd_list)
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
    p.add_argument("--target", choices=["geant4_interactions", "clustered_interactions", "quanta", "drifted_electrons",
                                        "extracted_electrons", "s2_photons", "photoelectrons"],
                   help="last product (default: the run's stop_after, at most the last implemented one)")
    p.add_argument("--g4", help="Geant4 output folder (default <data>/g4/<run name>)")
    p.add_argument("--lifetime-us", type=float, help="electron lifetime [µs] for a state without a measured one "
                                                     "(overrides the state; tracked in the lineage)")
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
