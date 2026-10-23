"""The run number as the identity of a simulation (plan S10, decided 2026-10-23).

Every simulation has a run number (900000-999999); the run id of everything it makes is that number, six digits:
the Geant4 output (<data>/g4/<id>), the chain's strax data (<data>/strax/<id>-<type>-<hash>), the provenance
(<data>/provenance/<id>/), the run document and the amstrax data. The run file's name is only a label.

    ensure_number(run file)   a run file without run_number gets one, written into the file when it is submitted or
                              first run. Production (the account with the run-database writer account): reserved in
                              run.runs_mc as the highest production number + 1 (rundb.reserve; the unique index on
                              `number` makes concurrent submissions safe). Private: the next free 99xxxx of this area.
    check_identity(res)       production: one run file = one run number = one simulation, the number from the run
                              database; a changed run is a new run (a new run file without number, `supersedes`).
                              Private: numbers are free; a changed run or another run file under the same number
                              replaces the old private run (clear: its outputs are deleted first).
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from .config import DATA, ROOT, STUDIES, ConfigError, Resolved, load_yaml

PRIVATE = (990000, 999999)
PRODUCTION = (900000, 989999)
EXAMPLES = (999901, 999999)          # the example run files of the repository (config/runs); skipped by next_free
PROV = DATA / "provenance"


def run_id(res: Resolved) -> str:
    n = res.run.get("run_number")
    if n is None:
        raise ConfigError(f"{res.run_path}: no run_number (every simulation has one; `xamssim particle` / `xamssim chain` "
                          "give a run file without one the next free private number)")
    return f"{int(n):06d}"


def number_of(run_file) -> int | None:
    try:
        n = load_yaml(Path(run_file)).get("run_number")
        return int(n) if n is not None else None
    except Exception:
        return None


def run_files() -> list:
    """All run files: studies (<studies>/<study>/runs/*.yaml) and the examples (xams-sim config/runs)."""
    return sorted(list(Path(STUDIES).glob("*/runs/*.yaml")) + list((ROOT / "config" / "runs").glob("*.yaml")))


def numbers_in_use() -> dict:
    """run number -> run files using it, plus the numbers that have provenance or Geant4 output (files may be gone)."""
    out: dict = {}
    for f in run_files():
        n = number_of(f)
        if n is not None:
            out.setdefault(n, []).append(f)
    for base in (PROV, DATA / "g4"):
        if base.is_dir():
            for d in base.iterdir():
                if d.is_dir() and re.fullmatch(r"\d{6}", d.name):
                    out.setdefault(int(d.name), [])
    from . import amstrax_io                                     # run documents in the raw-records store
    if amstrax_io.STORE is not None and Path(amstrax_io.STORE).is_dir():
        for f in Path(amstrax_io.STORE).glob("[0-9]" * 6 + "-metadata.json"):
            out.setdefault(int(f.name[:6]), [])
    from . import rundb                                          # production: the numbers in run.runs_mc
    if rundb.configured():
        col = rundb.collection()
        for d in col.find({}, {"number": 1}):
            out.setdefault(int(d["number"]), [])
    return out


def next_free(block: tuple = PRIVATE) -> int:
    lo, hi = block
    used = [n for n in numbers_in_use() if lo <= n <= hi and not EXAMPLES[0] <= n <= EXAMPLES[1]]
    n = max(used) + 1 if used else lo + 1
    if n > hi or EXAMPLES[0] <= n <= EXAMPLES[1]:
        raise ConfigError(f"no free run number in {lo}-{hi}")
    return n


def production_account() -> bool:
    """Production = the account has the run-database writer account ([mc] in ~/.xams_config, i.e. xamsdata)."""
    from . import rundb
    return rundb.configured()


def ensure_number(run_path, production: bool | None = None) -> int:
    """The run file's number; a run file without one gets one written into it. Production: reserved in run.runs_mc
    (highest production number + 1; safe for concurrent submissions, rundb.reserve). Private: the next free private
    number in this area (a lock against two of your own submissions at once)."""
    import fcntl
    run_path = Path(run_path)
    n = number_of(run_path)
    if n is not None:
        return n
    if production is None:
        production = production_account()
    kind = "production" if production else "private"
    lock = DATA / "locks" / "run_numbers.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        n = number_of(run_path)                                  # numbered meanwhile by another process
        if n is not None:
            return n
        if production:
            from . import rundb
            n = rundb.reserve(run_path)
        else:
            n = next_free(PRIVATE)
        lines = run_path.read_text().splitlines(keepends=True)
        i = 0
        while i < len(lines) and (lines[i].startswith("#") or not lines[i].strip()):   # after the leading comments
            i += 1
        lines.insert(i, f"run_number: {n}               # assigned by xamssim {dt.date.today()} ({kind})\n")
        run_path.write_text("".join(lines))
    print(f"{run_path.name}: no run number -> {n} ({kind}), written into the run file")
    return n


def _records(rid: str) -> list:
    d = PROV / rid
    return [json.loads(f.read_text()) for f in sorted(d.glob("*.json"))] if d.is_dir() else []


def clear(rid: str, log=print) -> list:
    """Delete everything of run `rid` in this account's folders (Geant4, chain data, provenance, raw records / run
    document / truth, live data, amstrax products): a private run that is replaced."""
    import os
    import shutil

    from . import amstrax_io
    places = [DATA / "g4" / rid, PROV / rid] + list((DATA / "strax").glob(f"{rid}-*"))
    if amstrax_io.STORE is not None:
        store = Path(amstrax_io.STORE)
        places += list(store.glob(f"{rid}-*")) + list(store.glob(f"{rid}.*"))
        try:
            from .live import live_root
            places.append(live_root(store) / rid)
        except Exception:
            pass
    proc = Path(os.environ["XAMSSIM_PROCESSED"]) if os.environ.get("XAMSSIM_PROCESSED") else DATA.parent / "processed"
    places += list(proc.glob(f"{rid}-*"))
    gone = []
    for p in places:
        if p.is_dir():
            shutil.rmtree(p); gone.append(p)
        elif p.exists():
            p.unlink(); gone.append(p)
    if gone:
        log(f"run {rid}: {len(gone)} outputs of the earlier run with this number deleted")
    return gone


def check_identity(res: Resolved) -> str:
    """Production: one run file = one run number = one simulation, and the number comes from the run database (refused
    otherwise). Private: numbers are free; a changed run or another run file under the same number replaces the old
    private run (its outputs deleted first)."""
    rid = run_id(res)
    n = int(rid)
    me = Path(res.run_path).resolve()
    production = production_account()
    if production and not PRODUCTION[0] <= n <= PRODUCTION[1]:
        raise ConfigError(f"run number {n}: not a production number ({PRODUCTION[0]}-{PRODUCTION[1]}); production "
                          "numbers come from the run database (leave run_number out, the submission takes one)")
    if not production and not PRIVATE[0] <= n <= PRIVATE[1]:
        raise ConfigError(f"run number {n}: private runs use {PRIVATE[0]}-{PRIVATE[1]} (production numbers come from the "
                          "run database, under the production account)")
    if production:
        from . import rundb
        doc = rundb.find(n)
        if doc is None:
            raise ConfigError(f"run {rid} is not in {rundb.DB}.{rundb.COLLECTION}: production numbers come from the run "
                              "database (leave run_number out, the submission takes one)")
        made = Path((doc.get("xamssim") or {}).get("run_file", "")).resolve()
        if made != me:
            raise ConfigError(f"run {rid} belongs to {made} in the run database, not to {res.run_path}")
    conflict = ""
    for r in _records(rid):
        if Path(r.get("run_file", "")).resolve() != me:
            conflict = f"run {rid} was made from {r.get('run_file')}"
        elif r.get("run_key") and r["run_key"] != res.run_key():
            conflict = f"run {rid} was made with other settings (run key {r['run_key']}, now {res.run_key()})"
    if conflict and production:
        raise ConfigError(conflict + ": a changed run is a new run: a new run file without number (the submission "
                          f"takes the next one), with `supersedes: {n}` (the app's rerun)")
    if conflict:
        print(conflict + ": private, so it is replaced")
        clear(rid)
    if production and PROV.is_dir():
        for d in PROV.iterdir():
            if d.is_dir() and d.name != rid and re.fullmatch(r"\d{6}", d.name):
                rec = next(iter(_records(d.name)[-1:]), None)
                if rec and Path(rec.get("run_file", "")).resolve() == me:
                    raise ConfigError(f"{res.run_path} was run before as run {d.name}; one run file is one run: "
                                      "for another number make a new run file")
    return rid
