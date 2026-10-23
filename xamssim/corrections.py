"""Per-run corrections of simulated runs, in their own run document (plan S10, decided 2026-10-23).

    xamssim corrections 990001                                     # show truth and calibrated
    xamssim corrections --calibrated cal.json --from-run 990001 --state sept    # store a calibration

A simulated run's run document (`<number>-metadata.json` next to its raw records; production runs also in
run.runs_mc) holds:

    xamssim.corrections.truth        the simulation's own values (written by `xamssim live`)
    xamssim.corrections.calibrated   measured on the reconstructed MC with the data calibration steps, with version,
                                     from_run, method, analysis_commit, date
    xamssim.corrections.history      earlier calibrations

amstrax reconstructs simulated runs with an MC global version (amstrax_files `_global_MC1.json`: the cuts and settings of
the data version, the per-run corrections as rundoc:// addresses: calibrated, else truth) and
`amstrax.contexts.for_mc_run`, which puts the calibration version into the addresses: each calibration gets its own
lineage, so products of an older calibration are never used for a newer one.

A calibration measured on one run applies to all runs of the same *condition* (`xamssim.condition`: state and maps,
i.e. the same truth); runs of another condition are refused. Values never change under a run's feet: a new calibration
gets the next version (pass 1 = truth, version 0; pass 2 = calibrated, version 1, ...).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .config import MC_RUN_NUMBERS, ConfigError

KEYS = ("elife", "gain_to_pe_array", "drift_time_gate", "drift_time_cathode")    # per-run corrections (MC1)
INFO = ("method", "analysis_commit")                                            # optional, describes a calibration


def _store() -> Path:
    from . import amstrax_io
    if amstrax_io.STORE is None:
        raise ConfigError("XAMSSIM_AMSTRAX_STORE is not set (setup_xamssim.sh does)")
    return Path(amstrax_io.STORE)


def doc_path(number: int) -> Path:
    return _store() / f"{int(number):06d}-metadata.json"


def load(number: int) -> dict:
    from bson import json_util
    p = doc_path(number)
    if not p.exists():
        raise ConfigError(f"no run document {p}")
    return json.loads(p.read_text(), object_hook=json_util.object_hook)


def _save(doc: dict) -> None:
    from bson import json_util                                    # as strax writes run documents
    doc_path(doc["number"]).write_text(json.dumps(doc, sort_keys=True, indent=4, default=json_util.default))


def runs(numbers: tuple[int, int] | None = None, state: str | None = None, tag: str | None = None) -> list[int]:
    """Simulated runs with a run document in the store, selected by number range, state and / or tag."""
    lo, hi = numbers or MC_RUN_NUMBERS
    out = []
    for p in sorted(_store().glob("[0-9][0-9][0-9][0-9][0-9][0-9]-metadata.json")):
        n = int(p.name[:6])
        if not lo <= n <= hi or not MC_RUN_NUMBERS[0] <= n <= MC_RUN_NUMBERS[1]:
            continue
        if state or tag:
            d = load(n)
            if state and d.get("xamssim", {}).get("state") != state or tag and tag not in d.get("tags", []):
                continue
        out.append(n)
    return out


def corrections(doc: dict) -> dict:
    """The corrections block of a run document (older documents: xamssim.truth only)."""
    x = doc.get("xamssim", {})
    c = dict(x.get("corrections") or {})
    if "truth" not in c and "truth" in x:
        c["truth"] = x["truth"]
    return c


def version(doc: dict) -> int:
    return int((corrections(doc).get("calibrated") or {}).get("version", 0))


def show(number: int, log=print) -> dict:
    doc = load(number)
    c = corrections(doc)
    cal = c.get("calibrated") or {}
    log(f"run {int(number):06d}: state {doc.get('xamssim', {}).get('state')}, condition "
        f"{doc.get('xamssim', {}).get('condition', '- (made before 2026-10-23)')}, calibration version {version(doc)}")
    for k in KEYS:
        t, m = (c.get("truth") or {}).get(k), cal.get(k)
        log(f"  {k:20s} truth {_fmt(t):>14s}   calibrated {_fmt(m):>14s}" + (f"   ({_diff(t, m)})" if m is not None else ""))
    if cal:
        log(f"  calibrated from run {cal.get('from_run')} on {cal.get('date')}: {cal.get('method') or '-'}"
            + (f", analysis {cal['analysis_commit']}" if cal.get("analysis_commit") else ""))
    if c.get("history"):
        log(f"  {len(c['history'])} earlier calibration(s)")
    return c


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, (list, tuple)):
        return f"[{len(v)} values]"
    return f"{v:.6g}"


def _diff(t, m) -> str:
    if isinstance(t, (int, float)) and isinstance(m, (int, float)) and t:
        return f"{100 * (m - t) / t:+.1f} %"
    return "differs" if t != m else "same"


def set_calibrated(values: dict, from_run: int, numbers: list[int], dry_run: bool = False, log=print) -> int:
    """Store a calibration (values measured on run from_run) in the run documents of the given runs, which must have
    the same condition as from_run; production runs also in run.runs_mc. Returns the number of runs updated."""
    from . import rundb
    vals = {k: v for k, v in values.items() if k in KEYS}
    unknown = sorted(set(values) - set(KEYS) - set(INFO))
    if unknown or not vals:
        raise ConfigError(f"calibration values: expected some of {KEYS} (+ {INFO}), got {sorted(values)}")
    cond = load(from_run).get("xamssim", {}).get("condition")
    if cond is None:
        raise ConfigError(f"run {from_run} has no xamssim.condition (made before 2026-10-23): rerun it (new number)")
    if not numbers:
        raise ConfigError("no runs selected")
    docs = [load(n) for n in numbers]
    wrong = [d["number"] for d in docs if d.get("xamssim", {}).get("condition") != cond]
    if wrong:
        raise ConfigError(f"runs {wrong} have another condition (state / maps) than run {from_run}: "
                          "its calibration does not apply to them")
    now = dt.datetime.now(tz=dt.timezone.utc)
    col = None if dry_run else rundb.collection()
    for d in docs:
        c = corrections(d)
        cal = dict(vals, version=version(d) + 1, from_run=int(from_run), date=now,
                   **{k: values[k] for k in INFO if values.get(k)})
        hist = list(c.get("history") or []) + ([c["calibrated"]] if c.get("calibrated") else [])
        log(f"run {d['number']:06d}: calibration version {cal['version']} ({', '.join(sorted(vals))})"
            + (" [dry run]" if dry_run else ""))
        if dry_run:
            continue
        d.setdefault("xamssim", {})["corrections"] = dict(c, calibrated=cal, history=hist)
        d["xamssim"].pop("truth", None)
        _save(d)
        if col is not None and col.find_one({"number": d["number"]}, {"_id": 1}) is not None:
            col.update_one({"number": d["number"]}, {"$set": {"xamssim.corrections": d["xamssim"]["corrections"]},
                                                     "$unset": {"xamssim.truth": ""}})
            log(f"  run database: {rundb.DB}.{rundb.COLLECTION} run {d['number']:06d} updated")
    return len(docs)
