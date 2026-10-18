#!/usr/bin/env python3
"""Top deficit or bottom excess? Cs-137 photopeak (fixed S2 per event, Δ750 V, LED gains; from
analysis_SR2026.2/scratch/top_bottom_vs_r.py -> optical/targets/top_bottom_vs_r_cs137.json) vs the simulation (s2_optics,
level 4): top, bottom and total light and the area fraction top versus r, each normalised to r = 7.5-12.5 mm.

    python optical/top_bottom_compare.py  ->  results/step7/top_bottom_vs_r.png
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "optical"))
from scan_data import load  # noqa: E402

TOP = (1, 2, 3, 4)


def main():
    tf = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--targets=")), "top_bottom_vs_r_cs137_single.json")
    D = json.load(open(ROOT / "optical" / "targets" / tf))   # default: single scatters
    e = np.arange(0, 25.1, 2.5)
    rc = 0.5 * (e[1:] + e[:-1])
    sim = {k: [] for k in ("top", "bot", "tot", "aft")}
    for p in load("s2_optics")["points"]:
        if p["params"]["level"] != 4.0:
            continue
        rec = p["rec"]
        r = np.hypot(rec["x0"], rec["y0"])
        t = np.histogram(r[np.isin(rec["sensor"], TOP)], e)[0].astype(float)
        b = np.histogram(r[rec["sensor"] == 0], e)[0].astype(float)
        area = e[1:] ** 2 - e[:-1] ** 2                      # emitted photons per ring ∝ area
        for k, v in (("top", t / area), ("bot", b / area), ("tot", (t + b) / area), ("aft", t / (t + b))):
            sim[k].append(v / v[3:5].mean())
    fig, ax = plt.subplots(1, 4, figsize=(16, 4))
    titles = {"top": "top PMT", "bot": "bottom PMT", "tot": "top + bottom", "aft": "area fraction top"}
    for a, k in zip(ax, ("top", "bot", "tot", "aft")):
        s = np.array(sim[k])
        lab = "simulation (light collection)" if k != "tot" else "simulation (light collection; S2 yield uniform)"
        a.fill_between(rc, s.min(0), s.max(0), color="C0", alpha=0.35, lw=0, label=lab)
        for day, col in (("28-09", "k"), ("29-09", "C3")):
            d = D[day]
            t, b = np.array(d["top"], float), np.array(d["bot"], float)
            te, be = np.array(d["top_err"], float), np.array(d["bot_err"], float)
            v, ve = {"top": (t, te), "bot": (b, be), "tot": (t + b, np.hypot(te, be)),
                     "aft": (t / (t + b), np.hypot(te * b, be * t) / (t + b) ** 2)}[k]
            n = v[3:5].mean()
            a.errorbar(rc, v / n, ve / n, fmt="o", ms=5, color=col, label=f"data Cs-137 photopeak {day}" + (" (single scatters)" if "single" in tf else ""))
        a.axhline(1, color="0.7", lw=0.6)
        a.set(xlabel="r [mm]", title=titles[k] + " (÷ value at r 7.5–12.5 mm)")
        a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(ROOT / "results" / "step7" / "top_bottom_vs_r.png", dpi=130)
    print("written")


if __name__ == "__main__":
    main()
