"""Run documents of simulated runs in the XAMS run database (plan S10, point 1): collection `run.runs_mc`.

`xamssim live` and `xamssim amstrax` always write the run document as a file next to the data (`<number>-metadata.json`)
and, when a writer account is configured, also put it into `run.runs_mc` of the MongoDB on xams. Never into `runs_gas`
(the dispatcher numbers data runs as the highest number there + 1). amstrax reads run documents of numbers >= 900000
from `runs_mc` (after a stored file).

Account: `~/.xams_config`, section `[mc]` with MONGO_USER and MONGO_PASSWORD (an account that can only write
`run.runs_mc`, made by the user); the SSH tunnel to xams (DAQ_HOST, DAQ_USER, DAQ_PASSWORD, MONGO_PORT) as amstrax uses
it, from `[default]`. Without a `[mc]` section nothing is written to the database.

A rerun of a simulated run (same number) replaces its document; documents are removed with `delete(...)` (by number
range or tag), e.g. the first runs tagged `test` in the run file.
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

from .config import MC_RUN_NUMBERS, ConfigError

DB, COLLECTION = "run", "runs_mc"
CONFIG_FILE = Path(os.environ.get("HOME", "~")) / ".xams_config"


def _account() -> dict | None:
    cfg = configparser.ConfigParser()
    if not CONFIG_FILE.exists() or not cfg.read(CONFIG_FILE) or "mc" not in cfg:
        return None
    base = dict(cfg["default"]) if "default" in cfg else {}       # the SSH tunnel to xams, as amstrax uses it
    return {**base, **dict(cfg["mc"])}                             # the writer account


def configured() -> bool:
    return _account() is not None


def collection():
    """The runs_mc collection with the writer account, or None if no [mc] account is configured."""
    acc = _account()
    if acc is None:
        return None
    import pymongo
    from amstrax.rundb import establish_ssh_tunnel
    port = establish_ssh_tunnel(acc["daq_host"], acc["daq_user"], acc["daq_password"], int(acc["mongo_port"]), {})
    client = pymongo.MongoClient(f"mongodb://{acc['mongo_user']}:{acc['mongo_password']}@127.0.0.1:{port}/admin")
    return client[DB][COLLECTION]


def _check_number(n: int) -> int:
    lo, hi = MC_RUN_NUMBERS
    if not lo <= int(n) <= hi:
        raise ConfigError(f"run number {n} outside the simulated range {lo}-{hi}: not written to {DB}.{COLLECTION}")
    return int(n)


PRODUCTION_NUMBERS = (900000, 989999)


def reserve(run_file, log=print) -> int:
    """The next production run number, taken in run.runs_mc: highest production number + 1 (900001 if none), written
    as a reserved run document (run file, submission time, status submitted). The unique index on `number` makes
    concurrent submissions safe: a lost race fails the insert and takes the following number."""
    import datetime as dt
    import getpass

    from pymongo.errors import DuplicateKeyError
    col = collection()
    if col is None:
        raise ConfigError(f"no [mc] account in {CONFIG_FILE}: production numbers come from the run database")
    lo, hi = PRODUCTION_NUMBERS
    for _ in range(100):
        last = col.find_one({"number": {"$gte": lo, "$lte": hi}}, {"number": 1}, sort=[("number", -1)])
        n = max(int(last["number"]) + 1 if last else lo + 1, lo + 1)
        if n > hi:
            raise ConfigError(f"no free production number in {lo}-{hi}")
        now = dt.datetime.now(tz=dt.timezone.utc)
        doc = {"number": n, "name": f"{n:06d}", "mode": "simulation (reserved)", "tags": ["simulation"],
               "xamssim": {"run_file": str(Path(run_file).resolve()), "run_name": Path(run_file).stem,
                           "reserved": now, "reserved_by": getpass.getuser()},
               "processing_status": {"status": "submitted", "time": now, "host": "stbc"}}
        try:
            col.insert_one(doc)
        except DuplicateKeyError:
            continue                                                       # taken meanwhile: the next one
        log(f"  run database: {DB}.{COLLECTION} run {n:06d} reserved for {Path(run_file).name}")
        return n
    raise ConfigError("could not reserve a production run number (100 attempts)")


def find(number: int) -> dict | None:
    col = collection()
    return None if col is None else col.find_one({"number": int(number)}, {"number": 1, "xamssim": 1})


def register(doc: dict, log=print) -> bool:
    """Insert or replace the run document of a simulated run in run.runs_mc; False if no account is configured."""
    n = _check_number(doc["number"])
    col = collection()
    if col is None:
        log(f"  run database: no [mc] account in {CONFIG_FILE}: run document only as a file")
        return False
    old = col.find_one({"number": n}, {"xamssim.run_key": 1})
    col.replace_one({"number": n}, doc, upsert=True)
    was = (old or {}).get("xamssim", {}).get("run_key")
    log(f"  run database: {DB}.{COLLECTION} run {n:06d} " + ("added" if old is None else
        "updated" if was == doc.get("xamssim", {}).get("run_key") else f"replaced (run key {was} -> rerun)"))
    return True


def record_processing(number: int, entries: list, status: str = "done", corrections_version: str | None = None,
                      log=print) -> bool:
    """After amstrax processed a simulated run: its data[] entries (replacing older ones of the same types),
    processing_status and a processing_history line in run.runs_mc, as the auto-processing does for data runs."""
    import datetime as dt
    import getpass
    n = _check_number(number)
    col = collection()
    if col is None:
        log(f"  run database: no [mc] account in {CONFIG_FILE}: processing not recorded")
        return False
    now = dt.datetime.now()
    entries = [dict(e, time=dt.datetime.fromisoformat(e["time"])) if isinstance(e.get("time"), str) else e
               for e in entries]                                   # as the auto-processing: a date, not a string
    types = sorted({e["type"] for e in entries})
    col.update_one({"number": n}, {"$pull": {"data": {"type": {"$in": types}}}})
    hist = dict(time=now, user=getpass.getuser(), host="stbc", action="mc_production", status=status,
                corrections_version=corrections_version, targets=types)
    res = col.update_one({"number": n}, {"$push": {"data": {"$each": entries}, "processing_history": hist},
                                         "$set": {"processing_status": dict(status=status, time=now, host="stbc")}})
    col.update_one({"number": n, "xamssim.made": {"$exists": False}}, {"$set": {"xamssim.made": now}})
    log(f"  run database: run {n:06d} processing {status} recorded ({', '.join(types)})" if res.matched_count
        else f"  run database: run {n:06d} not in {DB}.{COLLECTION}: processing not recorded")
    return bool(res.matched_count)


def delete(numbers: tuple[int, int] | None = None, tag: str | None = None, dry_run: bool = True, log=print) -> int:
    """Remove run documents from run.runs_mc by number range and / or tag (only ever within the simulated range)."""
    lo, hi = numbers or MC_RUN_NUMBERS
    q = {"number": {"$gte": _check_number(lo), "$lte": _check_number(hi)}}
    if tag:
        q["tags"] = tag
    col = collection()
    if col is None:
        raise ConfigError(f"no [mc] account in {CONFIG_FILE}")
    found = sorted(d["number"] for d in col.find(q, {"number": 1}))
    log(f"{len(found)} run documents in {DB}.{COLLECTION} match {q}: {found[:20]}{' ...' if len(found) > 20 else ''}")
    if not dry_run and found:
        col.delete_many(q)
        log(f"deleted {len(found)}")
    return len(found)
