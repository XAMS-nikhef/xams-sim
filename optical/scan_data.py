"""Read a scan made by optical/run_scan.py.

    from scan_data import load
    scan = load("s2_reference")         # name in run/scans/
    for p in scan["points"]:
        p["params"], p["n_photons"], p["rec"] (detected photons, read_output.RECORD), p["tally"] ({(end_code, volume): n})
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_output import read  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOP = (1, 2, 3, 4)
BOTTOM = 0


def load(name, records=True):
    d = ROOT / "run" / "scans" / name
    idx = json.load(open(d / "points.json"))
    for p in idx["points"]:
        recs, tally, n = [], Counter(), 0
        for part in p["parts"]:
            f = d / part["file"]
            s = json.load(open(str(f) + ".summary.json"))
            n += s["n_photons"]
            for t in s["tally"]:
                tally[(t["end_code"], t["volume"])] += t["n"]
            if records:
                recs.append(read(f)[0])
        p["n_photons"] = n
        p["tally"] = dict(tally)
        if records:
            p["rec"] = np.concatenate(recs) if recs else None
        p["config_json"] = json.load(open(d / p["config"]))
    idx["timing"] = json.load(open(d / "timing.json")) if (d / "timing.json").exists() else None
    return idx


def top_fraction(rec):
    """top / (top + bottom) of detected photons and its binomial error"""
    t = np.isin(rec["sensor"], TOP).sum()
    b = (rec["sensor"] == BOTTOM).sum()
    n = t + b
    f = t / n if n else np.nan
    return f, np.sqrt(f * (1 - f) / n) if n else np.nan
