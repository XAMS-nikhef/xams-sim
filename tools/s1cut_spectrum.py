#!/usr/bin/env python3
"""Energy spectra with and without the S1-AFT / drift-time consistency cut (same cut as
analysis_SR2026.2/studies/optsim_targets.py S1CUT=1: S1 AFT within 3 sigma of the drift-time calibration, S1 >= 20 PE).

Data: analysis_SR2026.2/outputs/s2_channels.npz (single scatters, Δ750 V; Cs-137 C28/C29 and no source B28/B29).
cS2 = S2 x exp(t / tau) with the lifetimes of elife_v2 (28-09: 157 µs, 29-09: 161 µs); cS1 as processed (v4).
Panels: cS1 and cS2 spectra, cS1-cS2 plane before / after, removed events; Cs-137 photopeak cS2 spread.

    python tools/s1cut_spectrum.py  ->  results/s1cut_spectrum/ (s1cut_spectrum.png, summary.json)
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "s1cut_spectrum"
DATA = ROOT.parent / "notebooks" / "analysis_SR2026.2" / "outputs" / "s2_channels.npz"
TAU = {28: 157.0, 29: 161.0}                       # µs, elife_v2


def s1_consistent(t_us, a1, s1, calmask, nsig=3.0):
    """copy of analysis_SR2026.2/studies/optsim_targets.py s1_consistent"""
    tb = np.arange(0, 44, 2.0)
    tc = 0.5 * (tb[1:] + tb[:-1])
    cm = calmask & (s1 > 50)
    cal = np.array([np.median(a1[cm & (t_us >= a) & (t_us < b)]) if (cm & (t_us >= a) & (t_us < b)).sum() >= 30 else np.nan
                    for a, b in zip(tb[:-1], tb[1:])])
    g = np.isfinite(cal)
    resid = a1 - np.interp(t_us, tc[g], cal[g])
    sb = np.array([20, 40, 70, 100, 200, 400, 1000, 1e9])
    sig = np.full(len(a1), np.nan)
    for a, b in zip(sb[:-1], sb[1:]):
        m = calmask & (s1 >= a) & (s1 < b)
        if m.sum() >= 30:
            sig[(s1 >= a) & (s1 < b)] = 1.4826 * np.median(np.abs(resid[m] - np.median(resid[m])))
    return (s1 >= 20) & np.isfinite(sig) & (np.abs(resid) < nsig * sig)


def robust_spread(v):
    med = np.median(v)
    return 1.4826 * np.median(np.abs(v - med)) / med


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = np.load(DATA)
    res = {}
    fig, ax = plt.subplots(2, 4, figsize=(20, 9))
    band = np.load(DATA.parent / "aft_maps.npz")["cs_cs1_band"]
    for row, (src, lab) in enumerate((("cs137", "Cs-137"), ("none", "no source"))):
        g = {k: D[f"{src}_{k}"] for k in ("x", "y", "drift_time", "s2_area", "s1_area", "cs1", "s1_aft_led", "run")}
        t = g["drift_time"] / 1e3
        r = np.hypot(g["x"], g["y"])
        day = np.where(g["run"] < 7680, 28, 29)
        tau = np.where(day == 28, TAU[28], TAU[29])
        cs2 = g["s2_area"] * np.exp(t / tau)
        cs1 = g["cs1"]
        base = (r < 20) & (t > 2) & (t < 38) & np.isfinite(cs1)
        calm = base & (g["s2_area"] > 2e4) & (r < 18)
        cons = s1_consistent(t, g["s1_aft_led"], g["s1_area"], calm)
        keep, cut = base & cons, base & ~cons
        out = dict(n=int(base.sum()), kept=int(keep.sum()), removed_fraction=round(float(cut.sum() / base.sum()), 4))
        # 1D spectra
        for k, (q, bins, name) in enumerate(((cs1, np.linspace(0, 2500, 126), "cS1 [PE]"),
                                             (cs2, np.geomspace(1e3, 1e6, 121), "cS2 [PE]"))):
            a = ax[row, k]
            a.hist(q[base], bins, histtype="step", color="k", label="all")
            a.hist(q[keep], bins, histtype="step", color="C0", label="consistent S1")
            a.hist(q[cut], bins, histtype="stepfilled", alpha=0.4, color="C3", label="removed")
            a.set(xlabel=name, ylabel="events", yscale="log", title=f"{lab}: {name.split()[0]} spectrum")
            if k == 1:
                a.set_xscale("log")
            a.legend(fontsize=7)
        for k, (m, tt) in enumerate(((base, "all"), (cut, "removed by the cut"))):
            a = ax[row, 2 + k]
            a.hist2d(cs1[m], np.log10(np.maximum(cs2[m], 1)), bins=[np.linspace(0, 2500, 120), np.linspace(3, 6, 120)],
                     norm=LogNorm(), cmap="viridis")
            a.set(xlabel="cS1 [PE]", ylabel="log10 cS2", title=f"{lab}: {tt}")
        # photopeak (Cs) cS2 spread with / without the cut, bulk drift region
        if src == "cs137":
            pk = (cs1 > band[0]) & (cs1 < band[1])
            for nm, m in (("all", base & pk), ("consistent", keep & pk)):
                out[f"photopeak_{nm}"] = dict(n=int(m.sum()), cs2_median=round(float(np.median(cs2[m])), 0),
                                              cs2_spread=round(float(robust_spread(cs2[m])), 4))
            out["photopeak_removed_fraction"] = round(float(1 - (keep & pk).sum() / (base & pk).sum()), 4)
        # what is removed: S2/S1, drift, radius
        out["removed_median"] = dict(s2_over_s1=round(float(np.median(g["s2_area"][cut] / g["s1_area"][cut])), 1),
                                     drift_us=round(float(np.median(t[cut])), 1), r_mm=round(float(np.median(r[cut])), 1),
                                     cs1=round(float(np.median(cs1[cut])), 0))
        out["kept_median"] = dict(s2_over_s1=round(float(np.median(g["s2_area"][keep] / g["s1_area"][keep])), 1),
                                  drift_us=round(float(np.median(t[keep])), 1), r_mm=round(float(np.median(r[keep])), 1),
                                  cs1=round(float(np.median(cs1[keep])), 0))
        res[lab] = out
    fig.tight_layout()
    fig.savefig(OUT / "s1cut_spectrum.png", dpi=110)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
