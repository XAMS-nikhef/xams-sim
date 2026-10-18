"""xams-sim command line.

    xamssim status config/runs/cs137_cmb50_001.yaml   resolved state / source, input hashes, map status
    xamssim maps --state cmb50                         map status for one detector state
    xamssim validate config/runs/*.yaml                check run files (and the states / sources they use)
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
    print("           (Geant4 particle mode: S2; event chain: S3-S8 — not yet available)")
    missing = _print_maps(res, needed(stop))
    print(f"{missing} of {len(needed(stop))} maps needed for '{stop}' missing")
    return 0


def cmd_maps(a) -> int:
    res = resolve_state(a.state)
    print(f"state {a.state} (hv_case {res.state['hv_case']}, level {res.state['liquid_level_mm']} mm)")
    _print_maps(res, list(KINDS))
    return 0


def cmd_validate(a) -> int:
    bad = 0
    for p in a.runs:
        try:
            res = resolve(p)
            print(f"ok       {p}  (state {res.state_name}, source {res.source_name}, run key {res.run_key()})")
        except ConfigError as e:
            bad += 1
            print(f"INVALID  {e}")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="xamssim", description="XAMS simulation chain (xams-sim)")
    ap.add_argument("--version", action="version", version=f"xamssim {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status", help="resolved run configuration and map status")
    p.add_argument("run")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("maps", help="map status for one detector state")
    p.add_argument("--state", required=True)
    p.set_defaults(func=cmd_maps)
    p = sub.add_parser("validate", help="check run configuration files")
    p.add_argument("runs", nargs="+")
    p.set_defaults(func=cmd_validate)
    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except ConfigError as e:
        print(f"configuration error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
