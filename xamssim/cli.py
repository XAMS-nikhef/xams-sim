"""xams-sim command line — everything is started from the `xamssim` conda env (the Geant4 program xamsg4 is run in the
`g4` env automatically; `g4` only has to be activated to compile). <data> = xamssim.config.DATA
(default ../simulations/data, or $XAMSSIM_DATA).

    xamssim particle config/runs/<run>.yaml [--events N]   Geant4 particle mode -> <data>/g4/<run>/deposits.*
    xamssim particle config/runs/vis_cs137.yaml --vis      particle viewer: look at a few events
    xamssim optical  <scan>.yaml [--jobs 8]                optical simulation (scan) -> <data>/scans/<scan>/
    xamssim optical  <scan>.yaml --vis [--point N]         optical viewer for a point of the scan (--list: the points)
    xamssim chain    config/runs/<run>.yaml [--target T]   simulation chain on <data>/g4/<run> -> <data>/strax/ (up to raw_records)
    xamssim status   config/runs/<run>.yaml                resolved state / source, input hashes, map status
    xamssim maps     --state cmb50                         map status for one detector state
    xamssim maps     --state cmb50 --export field          3D field of the state from the solved COMSOL model (licence)
    xamssim maps     --state cmb50 --export cells          gate and cathode mesh-cell fields from the cell models (licence)
    xamssim maps     --state cmb50 --export drift          drift map in the composite field (field + mesh cells)
    xamssim maps     --state cmb50 --export el             extraction / EL map from the gate + anode cell (licence)
    xamssim maps     --state cmb50 --export light          S1 / S2 light maps per channel (Geant4 optical, ~5 min)
    xamssim validate config/runs/*.yaml                    check run files (and the states / sources they use)
    xamssim show     <run> [--hash H] [--diff] [--full]    with which parameters the run's data were made
    xamssim amstrax  <run> [--lifetime-us T]               simulated raw records -> amstrax store (process like data)
    xamssim list     [--run PAT] [--prune | --delete]      runs, Geant4 output, strax products (current / old), maps;
                                                          --delete removes the old data after a confirmation,
                                                          --delete --all --run PAT: all data of those runs
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
    print(f"detector   {res.detector}: config/detectors/{res.detector}/geometry.yaml (version "
          f"{res.geometry.get('meta', {}).get('version')}), config/materials.yaml")
    print(f"chain      Geant4 particle mode -> {' -> '.join(('clustered_interactions', 'quanta', 'drifted_electrons', 'extracted_electrons', 's2_photons', 'photoelectrons', 'raw_records'))}")
    print("           (Geant4 particle mode: xamssim particle; up to raw_records: xamssim chain; amstrax: xamssim.amstrax_io)")
    missing = _print_maps(res, needed(stop))
    print(f"{missing} of {len(needed(stop))} maps needed for '{stop}' missing")
    return 0


# --make: the order in which missing maps are made (drift needs the field and the mesh cells)
MAKE_ORDER = ("field", "mesh_cells", "drift", "extraction_el", "s1_light", "s2_pattern")


def _make_maps(res, dry_run: bool) -> int:
    """Make the missing maps of a state with their registered commands, in dependency order (COMSOL steps need the
    licence; s1_light and s2_pattern share one command)."""
    import subprocess

    from .config import ROOT
    from .maps import status
    rows = {r["kind"]: r for r in status(res)}
    todo, seen = [], set()
    for kind in MAKE_ORDER:
        r = rows[kind]
        if not r["present"] and r["make"] not in seen:
            todo.append((kind, r["make"]))
            seen.add(r["make"])
    if not todo:
        print(f"state {res.state_name}: all maps present")
        return 0
    for kind, cmd in todo:
        print(f"{'would make' if dry_run else 'making'} {kind}: {cmd}", flush=True)
        if not dry_run and subprocess.call(cmd, shell=True, cwd=ROOT) != 0:
            print(f"stopped: making {kind} failed (COMSOL steps need the licence server)")
            return 1
    return 0


def cmd_maps(a) -> int:
    res = resolve_state(a.state)
    if a.make:
        rc = _make_maps(res, a.dry_run)
        if rc or a.dry_run:
            return rc
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
        run(a.run, n_events=a.events, seed=a.seed, out_dir=a.out, dry_run=a.dry_run, force=a.force)
    return 0


def cmd_chain(a) -> int:
    from .chain import run
    from pathlib import Path

    from .runlock import run_lock
    with run_lock(Path(a.run).stem):
        return run(a.run, target=a.target, g4_out=a.g4, lifetime_us=a.lifetime_us)


def cmd_amstrax(a) -> int:
    from . import amstrax_io
    from pathlib import Path
    from .runlock import run_lock
    with run_lock(Path(a.run).stem):
        rid = amstrax_io.export(a.run, lifetime_us=a.lifetime_us)
    print(f"run {rid} ({Path(a.run).stem}) in {amstrax_io.STORE}: raw records, run document, truth file; process it "
          f"with the analysis like a data run, e.g. EventDisplay({int(rid)}, ...)")
    return 0


def cmd_live(a) -> int:
    from pathlib import Path

    from . import live
    from .runlock import run_lock
    with run_lock(Path(a.run).stem):
        rid = live.write(a.run, lifetime_us=a.lifetime_us)
    print(f"run {rid} ({Path(a.run).stem}): live data, run document, truth file; amstrax makes raw_records from them with "
          f"its DAQReader (amstrax.contexts.context_for_daq_reader)")
    return 0


def cmd_web(a) -> int:
    import sys

    from .config import ROOT
    sys.path.insert(0, str(ROOT))                    # the app lives next to the package (web/), not inside it
    try:
        from web.app import main
    except ImportError as e:
        print(f"the simulation app needs its web extra: pip install -e '{ROOT}[web]' ({e})")
        return 1
    print(f"XAMS simulation app on http://{a.host}:{a.port}")
    main(host=a.host, port=a.port, debug=a.debug)
    return 0


def cmd_rundb(a) -> int:
    import json

    from . import rundb
    if a.record:
        entries = json.loads(open(a.entries).read())
        return 0 if rundb.record_processing(a.record, entries["data"], a.status, entries.get("corrections_version")) else 1
    rng = tuple(int(x) for x in a.range.split("-")) if a.range else None
    if not rundb.configured():
        print(f"no [mc] account in {rundb.CONFIG_FILE}: run documents are written only as files")
        return 1
    if a.delete and not a.yes:
        rundb.delete(rng, a.tag, dry_run=True)
        if input("delete these run documents from run.runs_mc? [y/N] ").strip().lower() != "y":
            return 0
    rundb.delete(rng, a.tag, dry_run=not a.delete)
    return 0


def cmd_corrections(a) -> int:
    import json

    from . import corrections
    if not a.calibrated:
        for n in a.run:
            corrections.show(n)
        return 0
    if a.from_run is None:
        print("--calibrated needs --from-run (the run the calibration was measured on)", file=sys.stderr)
        return 2
    rng = tuple(int(x) for x in a.runs.split("-")) if a.runs else None
    numbers = sorted(set(a.run) | (set(corrections.runs(rng, a.state, a.tag)) if (rng or a.state or a.tag) else set()))
    values = json.loads(open(a.calibrated).read())
    corrections.set_calibrated(values, a.from_run, numbers, dry_run=a.dry_run)
    return 0


def cmd_show(a) -> int:
    from .provenance import show
    return show(a.run, product=a.product, lineage_hash=a.hash, n=a.n, full=a.full, with_diff=a.diff)


def cmd_list(a) -> int:
    from .listing import show
    if a.all and not (a.delete and a.run):
        print("--all goes with --delete and --run PATTERN (--run '*' for every run)", file=sys.stderr)
        return 2
    return show(a.run, prune=a.prune, delete=a.delete, yes=a.yes, everything=a.all)


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
    p.add_argument("--make", action="store_true",
                   help="make all missing maps of the state in dependency order (field, mesh cells, drift, EL, light), "
                        "running the commands the status shows (COMSOL on this machine, licence needed)")
    p.add_argument("--dry-run", action="store_true", help="with --make: only show the commands")
    p.add_argument("--photons-s1", type=float, default=5e7, help="light: photons for the S1 map (default 5e7)")
    p.add_argument("--photons-s2", type=float, default=1e8, help="light: photons for the S2 map (default 1e8)")
    p.add_argument("--jobs", type=int, default=8, help="light: parallel Geant4 runs (default 8)")
    p.set_defaults(func=cmd_maps)
    p = sub.add_parser("list", help="what is in the data folder: runs, Geant4 output, strax products (current or "
                                    "old for the run file as it is now), maps per state")
    p.add_argument("--run", default="", metavar="PATTERN",
                   help="only the runs whose run id (= run file name) matches PATTERN: the whole id, with shell wildcards "
                        "* and ? (quote them: --run 'example*'); old maps are then left out")
    p.add_argument("--prune", action="store_true", help="also list the old data with its size (never deletes)")
    p.add_argument("--delete", action="store_true", help="delete the old data (Geant4 output for another Geant4 key, "
                                                         "strax products with an old lineage, unused maps) after a "
                                                         "confirmation")
    p.add_argument("--all", action="store_true", help="with --delete and --run: delete all Geant4 output and strax "
                                                      "products of the selected runs, current ones too (not the maps)")
    p.add_argument("--yes", action="store_true", help="with --delete: no confirmation")
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("amstrax", help="a run with run_number as a run for amstrax / the analysis: its simulated raw "
                                       "records, run document and truth file into the analysis' data folder (S8)")
    p.add_argument("run")
    p.add_argument("--lifetime-us", type=float, help="electron lifetime [µs] if the state has none (as for the chain)")
    p.set_defaults(func=cmd_amstrax)
    p = sub.add_parser("live", help="a run with run_number as redax live data (live_mc/<run>/) + run document and truth "
                                    "file, for amstrax's DAQReader (S10)")
    p.add_argument("run")
    p.add_argument("--lifetime-us", type=float, help="electron lifetime [µs] if the state has none (as for the chain)")
    p.set_defaults(func=cmd_live)
    p = sub.add_parser("corrections", help="per-run corrections of simulated runs (truth, calibrated) in their run "
                                           "document: show, or store a calibration with --calibrated")
    p.add_argument("run", nargs="*", type=int, help="run number(s)")
    p.add_argument("--calibrated", metavar="JSON", help="calibration values (elife, gain_to_pe_array, drift_time_gate, "
                                                        "drift_time_cathode; optional method, analysis_commit)")
    p.add_argument("--from-run", type=int, help="the run the calibration was measured on")
    p.add_argument("--runs", metavar="A-B", help="also all runs in this number range")
    p.add_argument("--state", help="also all runs of this state")
    p.add_argument("--tag", help="also all runs with this tag")
    p.add_argument("--dry-run", action="store_true", help="only show what would be stored")
    p.set_defaults(func=cmd_corrections)

    p = sub.add_parser("rundb", help="run documents of simulated runs in run.runs_mc (S10): list, or delete with --delete")
    p.add_argument("--range", help="run numbers LO-HI (default all of 900000-999999)")
    p.add_argument("--tag", help="only documents with this tag (e.g. test)")
    p.add_argument("--delete", action="store_true", help="delete the selected documents (after a confirmation)")
    p.add_argument("--yes", action="store_true", help="with --delete: without the confirmation")
    p.add_argument("--record", type=int, metavar="NUMBER", help="record amstrax processing of a simulated run: data[] "
                   "entries, processing_status, processing_history (from --entries, written by the production job)")
    p.add_argument("--entries", help="with --record: JSON {data: [...], corrections_version}")
    p.add_argument("--status", default="done", help="with --record: processing status (default done)")
    p.set_defaults(func=cmd_rundb)
    p = sub.add_parser("web", help="the simulation app (S11): which simulations exist and how they were made")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8071)
    p.add_argument("--debug", action="store_true", help="reload on code changes")
    p.set_defaults(func=cmd_web)
    p = sub.add_parser("show", help="with which parameters a run's data were made (provenance written by xamssim chain)")
    p.add_argument("run", help="run id or run file")
    p.add_argument("--product", help="the entry that made this product (data type), e.g. s2_photoelectrons")
    p.add_argument("--hash", help="the entry that made the product with this lineage hash (as in xamssim list)")
    p.add_argument("--n", type=int, help="entry number (default: the newest)")
    p.add_argument("--diff", action="store_true", help="what changed since: the run file resolved now vs the entry")
    p.add_argument("--full", action="store_true", help="the whole provenance record (JSON)")
    p.set_defaults(func=cmd_show)
    p = sub.add_parser("validate", help="check run configuration files")
    p.add_argument("runs", nargs="+")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("particle", help="Geant4 particle mode: production (energy deposits) or --vis viewer")
    p.add_argument("run")
    p.add_argument("--events", type=int, help="number of primaries (default: n_events of the run)")
    p.add_argument("--seed", type=int)
    p.add_argument("--out", help="output folder (default <data>/g4/<run name>)")
    p.add_argument("--dry-run", action="store_true", help="write config.json and run.mac, do not run Geant4")
    p.add_argument("--force", action="store_true", help="rerun Geant4 even if its output is current for the run file")
    p.add_argument("--vis", action="store_true", help="interactive Qt viewer (then /run/beamOn N in the window)")
    p.set_defaults(func=cmd_particle)
    p = sub.add_parser("chain", help="simulation chain (strax / fuse) on the Geant4 output of a run")
    p.add_argument("run")
    p.add_argument("--target", choices=["geant4_interactions", "clustered_interactions", "quanta", "drifted_electrons",
                                        "extracted_electrons", "s2_photons", "photoelectrons", "events", "raw_records"],
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
    except RuntimeError as e:
        from .runlock import RunLocked
        if not isinstance(e, RunLocked):
            raise
        print(f"busy: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
