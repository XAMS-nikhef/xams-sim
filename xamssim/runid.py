"""The run number as the identity of a simulation (plan S10, decided 2026-10-23).

Every simulation has a run number (900000-999999); the run id of everything it makes is that number, six digits:
the Geant4 output (<data>/g4/<id>), the chain's strax data (<data>/strax/<id>-<type>-<hash>), the provenance
(<data>/provenance/<id>/), the run document and the amstrax data. The run file's name is only a label.

    ensure_number(run file)   a run file without run_number gets the next free *private* number (99xxxx), written into
                              the file on its first run; production numbers (900000-989999) are always set by hand
    check_identity(res)       one run file = one run number = one simulation: refuses a number that another run file
                              uses, a number whose provenance belongs to another run file or to other settings (run
                              key), and a run file that was run before under another number. A changed run is a new
                              run: a new run file with the next free number and `supersedes` (the app's rerun).
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
    return out


def next_free(block: tuple = PRIVATE) -> int:
    lo, hi = block
    used = [n for n in numbers_in_use() if lo <= n <= hi and not EXAMPLES[0] <= n <= EXAMPLES[1]]
    n = max(used) + 1 if used else lo + 1
    if n > hi or EXAMPLES[0] <= n <= EXAMPLES[1]:
        raise ConfigError(f"no free run number in {lo}-{hi}")
    return n


def ensure_number(run_path) -> int:
    """The run file's number; a run file without one gets the next free private number written into it."""
    run_path = Path(run_path)
    n = number_of(run_path)
    if n is not None:
        return n
    n = next_free(PRIVATE)
    lines = run_path.read_text().splitlines(keepends=True)
    i = 0
    while i < len(lines) and (lines[i].startswith("#") or not lines[i].strip()):   # after the leading comments
        i += 1
    lines.insert(i, f"run_number: {n}               # assigned by xamssim {dt.date.today()} (private)\n")
    run_path.write_text("".join(lines))
    print(f"{run_path.name}: no run number -> {n} (private), written into the run file")
    return n


def _records(rid: str) -> list:
    d = PROV / rid
    return [json.loads(f.read_text()) for f in sorted(d.glob("*.json"))] if d.is_dir() else []


def check_identity(res: Resolved) -> str:
    """Refuse anything that would make one run number stand for two simulations or one run file for two runs."""
    rid = run_id(res)
    n = int(rid)
    me = Path(res.run_path).resolve()
    others = [f for f in numbers_in_use().get(n, []) if Path(f).resolve() != me]
    if others:
        raise ConfigError(f"run number {n} of {res.run_path} is also used by {', '.join(map(str, others))}")
    for r in _records(rid):
        if Path(r.get("run_file", "")).resolve() != me:
            raise ConfigError(f"run {rid} was made from {r.get('run_file')}, not from {res.run_path}: give this run file "
                              f"its own number (next free private: {next_free(PRIVATE)})")
        if r.get("run_key") and r["run_key"] != res.run_key():
            raise ConfigError(f"run {rid} was made with other settings (run key {r['run_key']}, now {res.run_key()}): "
                              "a changed run is a new run: a new run file with the next free number and "
                              f"`supersedes: {n}` (the app's rerun)")
    if PROV.is_dir():
        for d in PROV.iterdir():
            if d.is_dir() and d.name != rid and re.fullmatch(r"\d{6}", d.name):
                rec = next(iter(_records(d.name)[-1:]), None)
                if rec and Path(rec.get("run_file", "")).resolve() == me:
                    raise ConfigError(f"{res.run_path} was run before as run {d.name}; one run file is one run: "
                                      "for another number make a new run file")
    return rid
