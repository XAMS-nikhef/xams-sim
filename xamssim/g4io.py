"""Read the output of the Geant4 particle mode (g4/include/ParticleMode.hh).

    from xamssim import g4io
    h, dep, ev = g4io.read(DATA / "g4/cs137_cmb50_001")   # header dict, deposits, events (numpy structured arrays)
    g4io.names(h, "particle", dep["particle"])                  # codes -> names
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _stem(path) -> Path:
    p = Path(path)
    if p.is_dir():
        p = p / "deposits"
    return p.with_suffix("") if p.suffix in (".bin", ".json") else p


def read(path, mmap: bool = False):
    """Return (header, deposits, events). With mmap=True the deposits are memory-mapped (large files)."""
    stem = _stem(path)
    h = json.loads(stem.with_suffix(".json").read_text())
    ddt = np.dtype([tuple(x) for x in h["deposit_dtype"]])
    edt = np.dtype([tuple(x) for x in h["event_dtype"]])
    if ddt.itemsize != h["deposit_record_bytes"] or edt.itemsize != h["event_record_bytes"]:
        raise ValueError("record layout in the header does not match its byte size")
    # the .bin next to the header (folders may be moved / renamed); the path stored in the header only as a fallback
    dpath = stem.with_suffix(".bin")
    if not dpath.exists():
        dpath = Path(h["files"]["deposits"])
    dep = np.memmap(dpath, dtype=ddt, mode="r") if mmap else np.fromfile(dpath, dtype=ddt)
    ev = np.fromfile(stem.parent / (stem.name + ".events.bin"), dtype=edt)
    if len(dep) != h["counts"]["deposits"] or len(ev) != h["counts"]["events"]:
        raise ValueError(f"record counts differ from the header: {len(dep)} / {len(ev)} vs {h['counts']}")
    return h, dep, ev


def names(h: dict, table: str, codes) -> np.ndarray:
    t = np.array(h["codes"][table], dtype=object)
    return t[np.asarray(codes)]


def code(h: dict, table: str, name: str) -> int:
    """Code of a name (-1 if it never occurred)."""
    t = h["codes"].get(table, [])
    return t.index(name) if name in t else -1


def _drop_paths(obj):
    """The object without absolute file paths (they change when a folder moves, the content does not)."""
    if isinstance(obj, dict):
        return {k: _drop_paths(v) for k, v in obj.items() if not (isinstance(v, str) and v.startswith("/"))}
    if isinstance(obj, list):
        return [_drop_paths(v) for v in obj]
    return obj


def output_hash(path) -> str:
    """Content hash of a particle-mode output: the full config Geant4 ran with (geometry, materials, source, physics,
    seed, xams-sim version), the event and deposit counts, the code tables and record layout — not file paths.
    The chain's input plugin tracks it, so new Geant4 output never reuses old strax data."""
    from .config import short_hash
    h = json.loads(_stem(path).with_suffix(".json").read_text())
    h = {k: v for k, v in h.items() if k != "files"}
    info = dict(h.get("info", {}))
    if "config_json" in info:
        info["config_json"] = json.loads(info["config_json"])
    h["info"] = info
    return short_hash(_drop_paths(h))
