#!/usr/bin/env python3
"""Where does the low S2 area fraction top at y < 0 come from? Per-channel S2 light, data vs simulation.

Data: analysis_SR2026.2/outputs/s2_channels.npz (studies/s2_channels.py, read-only on stbc-i2, central v4): single
scatters at Δ750 V, S2 area per PMT channel (LED gains) from the stored peaks. Simulation: light map per sensor from the
81 fit_s2 points pooled (geometry v4; uniform S2 source, so detected counts per cell ∝ light collection), data frame.

A. Relative top-channel gains: fit g1..g4 (mean 1) so that the measured channel shares ch_i / top match the simulated
   shares per 2.5 mm cell (large S2s: no source > 20 kPE and the Cs-137 photopeak).
B. Cs-137 photopeak (fixed energy): S2 top, bottom and each channel versus y (strip |x| < 6 mm) and versus x (strip
   |y| < 6 mm), data ÷ simulation light collection, each normalised at the centre. Separates a top deficit from a
   bottom excess and from an S2-yield change (both move together).
C. The low-AFT region (y < 0, r 10-18 mm): AFT versus drift time against the mirror region (y > 0, r 10-18 mm), per
   day and sample; S1, S2 width and drift time of its events; top/bottom data / sim maps on x-y.

    python optical/channel_test.py  ->  results/channel_test/ (channel_test.png, summary.json)
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "optical"))
from read_output import read  # noqa: E402

OUT = ROOT / "results" / "channel_test"
DATA = ROOT.parent / "measurements" / "analysis_SR2026.2" / "outputs" / "s2_channels.npz"
E = np.arange(-25, 25.1, 2.5)
C = 0.5 * (E[1:] + E[:-1])


def sim_maps():
    cache = OUT / "sim_channels.npz"
    if cache.exists():
        return np.load(cache)["H"]
    idx = json.load(open(ROOT / "run" / "scans" / "fit_s2" / "points.json"))
    H = np.zeros((5, len(C), len(C)))
    for p in idx["points"]:
        for q in p["parts"]:
            rec = read(ROOT / "run" / "scans" / "fit_s2" / q["file"])[0]
            for s in range(5):
                m = rec["sensor"] == s
                H[s] += np.histogram2d(-rec["x0"][m], rec["y0"][m], bins=[E, E])[0]
    np.savez(cache, H=H)
    return H


def photopeak(cs1):
    """cS1 photopeak band (±0.5 sigma) from the edge fit on stbc-i2 (studies/aft_maps.py, photopeak.edge_and_fit);
    the local spectrum of single scatters has only a shoulder, so no local peak search"""
    lo, hi = np.load(DATA.parent / "aft_maps.npz")["cs_cs1_band"]
    return (cs1 > lo) & (cs1 < hi), 0.5 * (lo + hi), hi - lo


def cell_index(x, y):
    i, j = np.digitize(x, E) - 1, np.digitize(y, E) - 1
    ok = (i >= 0) & (i < len(C)) & (j >= 0) & (j < len(C))
    return i, j, ok


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = np.load(DATA)
    H = sim_maps()
    simtop = H[1:].sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        simshare = H[1:] / simtop                          # (4, nx, ny)
    res = {}

    # ---- A: relative top gains from channel shares
    samples = {}
    pk, mu, sg = photopeak(D["cs137_cs1"])
    samples["Cs-137 photopeak"] = {k: D[f"cs137_{k}"][pk] for k in ("x", "y", "ch")}
    big = D["none_s2_area"] > 2e4
    samples["no source > 20 kPE"] = {k: D[f"none_{k}"][big] for k in ("x", "y", "ch")}
    res["photopeak_cs1"] = [float(mu), float(sg)]
    res["gains"] = {}
    for name, s in samples.items():
        i, j, ok = cell_index(s["x"], s["y"])
        top = s["ch"][:, 1:].sum(1)
        share = s["ch"][:, 1:] / top[:, None]
        cells, dsh, ssh = [], [], []
        for a in range(len(C)):
            for b in range(len(C)):
                m = ok & (i == a) & (j == b)
                if m.sum() >= 50 and np.hypot(C[a], C[b]) < 22:
                    cells.append((a, b)), dsh.append(np.median(share[m], 0)), ssh.append(simshare[:, a, b])
        dsh, ssh = np.array(dsh), np.array(ssh)

        def resid(g):
            gg = np.append(g, 4 - g.sum())                 # mean gain fixed to 1
            m = ssh * gg
            return (dsh - m / m.sum(1, keepdims=True)).ravel()

        fit = least_squares(resid, np.ones(3))
        g = np.append(fit.x, 4 - fit.x.sum())
        rms0 = float(np.sqrt(np.mean(resid(np.ones(3)) ** 2)))
        res["gains"][name] = dict(g=g.round(3).tolist(), share_rms_before=round(rms0, 4),
                                  share_rms_after=round(float(np.sqrt(np.mean(fit.fun ** 2))), 4), cells=len(cells))

    # ---- B: Cs photopeak profiles vs y and vs x, data / sim, normalised at the centre
    s = samples["Cs-137 photopeak"]
    fig, ax = plt.subplots(2, 3, figsize=(17, 8.5))
    res["profiles"] = {}
    for row, (axis, strip) in enumerate((("y", s["x"]), ("x", s["y"]))):
        pos = s["y"] if axis == "y" else s["x"]
        sel = np.abs(strip) < 6
        k6 = np.abs(C) < 6
        quant = {"top": s["ch"][:, 1:].sum(1), "bottom": s["ch"][:, 0]}
        quant.update({f"ch{c}": s["ch"][:, c] for c in (1, 2, 3, 4)})
        simq = {"top": simtop, "bottom": H[0]}
        simq.update({f"ch{c}": H[c] for c in (1, 2, 3, 4)})
        prof = {}
        for name, q in quant.items():
            d = np.array([np.median(q[sel & (pos >= a) & (pos < b)]) if (sel & (pos >= a) & (pos < b)).sum() > 40 else np.nan
                          for a, b in zip(E[:-1], E[1:])])
            # sim map index [ix, iy]: profile along y = mean over the |x| < 6 mm rows of axis 0
            sm = simq[name][k6, :].mean(0) if axis == "y" else simq[name][:, k6].mean(1)
            r = d / sm
            ctr = np.nanmean(r[np.abs(C) < 3])
            prof[name] = (r / ctr)
            res["profiles"][f"{name}_vs_{axis}"] = [None if not np.isfinite(v) else round(float(v), 3) for v in r / ctr]
        a = ax[row, 0]
        for name, st in (("top", "C3o-"), ("bottom", "C0s-")):
            a.plot(C, prof[name], st, ms=4, label=f"S2 {name}")
        a.axhline(1, color="0.6", lw=0.6)
        a.set(xlabel=f"{axis} [mm] (strip |{'x' if axis == 'y' else 'y'}| < 6 mm)", ylabel="data ÷ simulation (÷ centre)",
              title=f"Cs-137 photopeak: top and bottom S2 vs {axis}", ylim=(0.5, 1.6))
        a.legend(fontsize=8)
        a = ax[row, 1]
        for c in (1, 2, 3, 4):
            a.plot(C, prof[f"ch{c}"], "o-", ms=3, label=f"ch{c}")
        a.axhline(1, color="0.6", lw=0.6)
        a.set(xlabel=f"{axis} [mm]", ylabel="data ÷ simulation (÷ centre)", title=f"each top channel vs {axis}", ylim=(0.5, 1.6))
        a.legend(fontsize=8)
        a = ax[row, 2]
        aft_r = prof["top"] / prof["bottom"]
        a.plot(C, aft_r, "ko-", ms=4)
        a.axhline(1, color="0.6", lw=0.6)
        a.set(xlabel=f"{axis} [mm]", ylabel="(top/bottom) data ÷ sim (÷ centre)", title=f"top/bottom ratio vs {axis}",
              ylim=(0.5, 1.6))
    fig.suptitle("Cs-137 photopeak (single scatters, Δ750 V, LED gains): data ÷ simulated light collection", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "channel_test.png", dpi=115)
    # ---- C: the low-AFT region at y < 0
    res["low_region"] = {}
    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    for k, (src, lab) in enumerate((("none", "no source"), ("cs137", "Cs-137"))):
        sel = D[f"{src}_s2_area"] > 5e4
        x, y, dt, ch, run = (D[f"{src}_{q}"][sel] for q in ("x", "y", "drift_time", "ch", "run"))
        dt = dt / 1e3
        top = ch[:, 1:].sum(1)
        aft = top / (top + ch[:, 0])
        r = np.hypot(x, y)
        low, mir = (y < -3) & (y > -17) & (r > 10) & (r < 18), (y > 3) & (r > 10) & (r < 18)
        bins = [0, 3, 6, 10, 15, 20, 25, 30, 35, 41]
        bc = 0.5 * (np.array(bins[1:]) + np.array(bins[:-1]))
        out = {}
        for nm, m, st in (("y<0 region", low, "o-"), ("mirror y>0", mir, "s--")):
            v = [float(np.median(aft[m & (dt >= a) & (dt < b)])) if (m & (dt >= a) & (dt < b)).sum() > 20 else np.nan
                 for a, b in zip(bins[:-1], bins[1:])]
            ax[k].plot(bc, v, st, label=nm)
            out[nm] = dict(aft_vs_drift=[round(q, 3) for q in v], n=int(m.sum()),
                           s1_median=float(np.median(D[f"{src}_s1_area"][sel][m])),
                           s2_width50_median=float(np.median(D[f"{src}_s2_range_50p_area"][sel][m])),
                           drift_median_us=float(np.median(dt[m])))
        out["drift_bins_us"] = bins
        res["low_region"][lab] = out
        ax[k].set(xlabel="drift time [µs]", ylabel="median S2 AFT (LED gains)", title=f"{lab}, S2 > 50 kPE, r 10–18 mm")
        ax[k].legend()
    fig.tight_layout()
    fig.savefig(OUT / "low_region_vs_drift.png", dpi=120)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(res["gains"], indent=1))
    print(json.dumps(res["low_region"], indent=1))
    for k in ("top_vs_y", "bottom_vs_y", "top_vs_x", "bottom_vs_x"):
        print(k, res["profiles"][k])


if __name__ == "__main__":
    main()
