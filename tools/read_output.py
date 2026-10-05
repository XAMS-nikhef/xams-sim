"""Read the per-photon output of xamsopt (binary records, layout of include/Output.hh PhotonRecord)."""
import json
from pathlib import Path

import numpy as np

RECORD = np.dtype([("event", "<i4"), ("x0", "<f4"), ("y0", "<f4"), ("z0", "<f4"), ("x1", "<f4"), ("y1", "<f4"),
                   ("z1", "<f4"), ("end_code", "<i2"), ("sensor", "<i2"), ("volume", "<i2"), ("n_refl", "<i2")])
END = {0: "unknown", 1: "detected", 2: "bulk_absorbed", 3: "surface_absorbed", 4: "escaped"}


def read(path):
    """records (numpy structured array) and {volume index: name}"""
    path = Path(path)
    rec = np.fromfile(path, dtype=RECORD)
    side = Path(str(path) + ".volumes.json")
    vols = {int(k): v for k, v in json.load(open(side)).items()} if side.exists() else {}
    return rec, vols


def summary(rec, vols=None):
    n = len(rec)
    out = {END.get(int(c), str(c)): int((rec["end_code"] == c).sum()) for c in np.unique(rec["end_code"])}
    det = rec[rec["end_code"] == 1]
    out["by_sensor"] = {int(s): int((det["sensor"] == s).sum()) for s in np.unique(det["sensor"])}
    out["n"] = n
    return out
