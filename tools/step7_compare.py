#!/usr/bin/env python3
"""Step 7: data targets (targets/data_2026-10-05.json, from analysis_SR2026.2/studies/optsim_targets.py) next to the
simulation (scans s2_optics, s1_optics), in the same bins.

    python tools/step7_compare.py   ->  results/step7/compare.png, results/step7/sim_binned.json

Sim band = all s2_optics points at the 4 mm level (PTFE R 0.90-0.99, steel R 0.2-0.5) / all s1_optics points.
Data: LED gains (load correction undone), no source / Na-22 / Cs-137 at Δ750 V. Equal QE top / bottom in the sim.
Frames: data x runs along +u (towards ch1/ch3), the sim's +x towards sectors II/IV (ch2/ch4): x_data = -x_sim,
y_data = y_sim.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from scan_data import load, top_fraction  # noqa: E402

OUT = ROOT / "results" / "step7"
TOP = (1, 2, 3, 4)
COL = {"none": "k", "na22": "C1", "cs137": "C3"}
LAB = {"none": "data, no source", "na22": "data, Na-22", "cs137": "data, Cs-137"}


def sim_binned(p, edges):
    rec = p["rec"]
    det = rec[np.isin(rec["sensor"], (0,) + TOP)]
    x, y = -det["x0"], det["y0"]                     # data frame
    r = np.hypot(x, y)
    out = {}
    out["s2_aft_vs_r"] = [top_fraction(det[(r >= a) & (r < b)])[0] for a, b in zip(edges["r"][:-1], edges["r"][1:])]
    t = det[np.isin(det["sensor"], TOP)]
    xt, yt = -t["x0"], t["y0"]
    s = t["sensor"]
    u = np.where(np.isin(s, (1, 3)), 1, -1).astype(float)
    v = np.where(np.isin(s, (1, 2)), 1, -1).astype(float)
    pe = edges["pos"]
    out["u_vs_x"] = [float(u[(np.abs(yt) < 3) & (xt >= a) & (xt < b)].mean()) for a, b in zip(pe[:-1], pe[1:])]
    out["v_vs_y"] = [float(v[(np.abs(xt) < 3) & (yt >= a) & (yt < b)].mean()) for a, b in zip(pe[:-1], pe[1:])]
    out["s2_aft_r25"] = top_fraction(det[r < 25])[0]
    return out


def sim_s1(p, edges):
    rec = p["rec"]
    det = rec[np.isin(rec["sensor"], (0,) + TOP) & (np.hypot(rec["x0"], rec["y0"]) < 25)]
    z = det["z0"]
    return [top_fraction(det[(z >= a) & (z < b)])[0] for a, b in zip(edges["z"][:-1], edges["z"][1:])]


def mid(e):
    e = np.asarray(e, float)
    return 0.5 * (e[1:] + e[:-1])


def arr(l):
    return np.array([np.nan if x is None else x for x in l], float)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = json.load(open(ROOT / "targets" / "data_2026-10-05.json"))
    ed = D["edges"]
    s2 = [p for p in load("s2_optics")["points"] if p["config_json"]["liquid"]["level_above_gate_mm"] == 4.0]
    S2 = [sim_binned(p, ed) for p in s2]
    s1 = load("s1_optics")["points"]
    S1 = [sim_s1(p, ed) for p in s1]
    json.dump(dict(s2=S2, s1=S1, s2_params=[p["params"] for p in s2], s1_params=[p["params"] for p in s1]),
              open(OUT / "sim_binned.json", "w"), indent=1, default=float)

    fig, ax = plt.subplots(2, 2, figsize=(11, 8))
    # S2 AFT vs size
    a = ax[0, 0]
    xs = np.sqrt(np.array(ed["s2"][:-1]) * np.array(ed["s2"][1:]))
    lo, hi = min(s["s2_aft_r25"] for s in S2), max(s["s2_aft_r25"] for s in S2)
    a.axhspan(lo, hi, color="C0", alpha=0.3, label="simulation (optics ranges)")
    for k in COL:
        a.errorbar(xs, arr(D[k]["s2_aft_vs_size_led"]), arr(D[k]["s2_aft_vs_size_led_err"]), fmt="o", ms=5, color=COL[k], label=LAB[k])
    a.set_xscale("log")
    a.set_xlabel("S2 area [PE]")
    a.set_ylabel("S2 area fraction top")
    a.set_title("S2 AFT vs S2 size (r < 25 mm)", fontsize=10)
    a.legend(fontsize=7)
    # S2 AFT vs r
    a = ax[0, 1]
    rc = mid(ed["r"])
    sr = np.array([s["s2_aft_vs_r"] for s in S2])
    a.fill_between(rc, sr.min(0), sr.max(0), color="C0", alpha=0.3, label="simulation")
    for k in COL:
        a.errorbar(rc, arr(D[k]["s2_aft_vs_r_led"]), arr(D[k]["s2_aft_vs_r_led_err"]), fmt="o", ms=5, color=COL[k], label=LAB[k])
    a.set_xlabel("r [mm]")
    a.set_ylabel("S2 area fraction top")
    a.set_title("S2 AFT vs r (S2 3-20 kPE)", fontsize=10)
    a.legend(fontsize=7)
    # S1 AFT vs z
    a = ax[1, 0]
    zc = mid(ed["z"])
    s1a = np.array(S1)
    a.fill_between(zc, s1a.min(0), s1a.max(0), color="C0", alpha=0.3, label="simulation (PTFE R 0.90-0.99)")
    for k in COL:
        a.errorbar(zc, arr(D[k]["s1_aft_vs_z_led"]), arr(D[k]["s1_aft_vs_z_led_err"]), fmt="o", ms=5, color=COL[k], label=LAB[k])
    a.set_xlabel("z [mm] (gate 0, cathode -51.8)")
    a.set_ylabel("S1 area fraction top")
    a.set_title("S1 AFT vs z (S1 > 20 PE, r < 25 mm)", fontsize=10)
    a.legend(fontsize=7)
    # u, v profiles
    a = ax[1, 1]
    pc = mid(ed["pos"])
    su = np.array([s["u_vs_x"] for s in S2])
    sv = np.array([s["v_vs_y"] for s in S2])
    a.fill_between(pc, su.min(0), su.max(0), color="C0", alpha=0.3, label="simulation u(x)")
    a.fill_between(pc, sv.min(0), sv.max(0), color="C2", alpha=0.3, label="simulation v(y)")
    a.errorbar(pc, arr(D["none"]["u_vs_x"]), arr(D["none"]["u_vs_x_err"]), fmt="ko", ms=4, label="data u(x), no source")
    a.errorbar(pc, arr(D["none"]["v_vs_y"]), arr(D["none"]["v_vs_y_err"]), fmt="s", mfc="none", mec="k", ecolor="k", ms=4, label="data v(y), no source")
    a.set_xlabel("position along the axis [mm] (posrec v2)")
    a.set_ylabel("top-array asymmetry")
    a.set_title("top-sector pattern: u = (1+3-2-4)/top, v = (1+2-3-4)/top", fontsize=10)
    a.legend(fontsize=7)
    fig.suptitle("Step 7: data (LED gains, Δ750 V; points with statistical errors) vs optical simulation (bands; level 4 mm, equal QE)")
    fig.tight_layout()
    fig.savefig(OUT / "compare.png", dpi=130)
    print("written", OUT / "compare.png")

    # threshold test: S2 AFT vs r per S2 size (no source); a per-channel threshold loss shrinks with S2 size
    bys = D["none"]["s2_aft_vs_r_by_size_led"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ratios = []
    for (lab, v), col in zip(bys.items(), plt.cm.viridis(np.linspace(0, 0.9, len(bys)))):
        lo, hi = (float(x) for x in lab.split("-"))
        y, e = arr(v["aft"]), arr(v["err"])
        ax[0].errorbar(rc, y, e, fmt="o", ms=5, color=col, label=f"S2 {lo / 1e3:.0f}–{hi / 1e3:.0f} kPE")
        ring = np.nanmean(y[3:5])                       # r 7.5-12.5 mm
        r0, e0 = y[0] / ring, e[0] / ring
        ratios.append((np.sqrt(lo * hi), r0, e0))
    ax[0].fill_between(rc, sr.min(0), sr.max(0), color="C0", alpha=0.25, lw=0, label="simulation (geometry, any S2 size)")
    ax[0].set(xlabel="r [mm]", ylabel="S2 area fraction top", title="data, no source, per S2 size")
    ax[0].legend(fontsize=7)
    ratios = np.array(ratios)
    ax[1].errorbar(ratios[:, 0], ratios[:, 1], ratios[:, 2], fmt="ko", ms=5, label="data")
    simr = sr[:, 0] / sr[:, 3:5].mean(1)
    ax[1].axhspan(simr.min(), simr.max(), color="C0", alpha=0.3, lw=0, label="simulation")
    ax[1].set(xscale="log", xlabel="S2 area [PE]", ylabel="AFT(r < 2.5 mm) / AFT(r 7.5–12.5 mm)",
              title="central dip vs S2 size")
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "central_dip_vs_size.png", dpi=130)
    json.dump(dict(central_over_ring=ratios.tolist(), sim=[float(simr.min()), float(simr.max())]),
              open(OUT / "central_dip_vs_size.json", "w"), indent=1)


if __name__ == "__main__":
    main()
