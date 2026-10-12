#!/usr/bin/env python3
"""S1 area fraction top versus drift time: do the odd event groups have an S1 that belongs to their drift time?

The S1 AFT measures the depth of the S1 light independently of the drift time (simulation step 6/7: 0.11 at the
cathode → 0.25 at the gate). Calibration: median S1 AFT versus drift time of "normal" events (S2 > 20 kPE, r < 18 mm,
outside the y < 0 region, S1 > 100 PE), per sample. Each event's S1 AFT is turned into a drift time t_S1 with that
curve; t_S1 - t_drift is ~0 for normal events and far off for an S1 that does not come from the drift position
(e.g. light from outside the PTFE wall, or an S1 that does not belong to the S2).

Groups (no source and Cs-137, all energies): the y < 0 region (y < -3, r 10-18 mm, S2 > 50 kPE) vs its mirror
(y > 3); the central small-S2 population (no source, S2 3-20 kPE, r < 2.5 mm) vs the ring (r 7.5-12.5 mm).
Data: analysis_SR2026.2/outputs/s2_channels.npz (studies/s2_channels.py, stbc-i2, read-only).

    python tools/s1aft_depth.py  ->  results/s1aft_depth/ (s1aft_depth.png, summary.json)
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "s1aft_depth"
DATA = ROOT.parent / "measurements" / "analysis_SR2026.2" / "outputs" / "s2_channels.npz"
TB = np.arange(0, 41.1, 2.5)                    # drift-time bins [µs]
TC = 0.5 * (TB[1:] + TB[:-1])
S1MIN = 100


def medians(t, a, m):
    return np.array([np.median(a[m & (t >= lo) & (t < hi)]) if (m & (t >= lo) & (t < hi)).sum() >= 20 else np.nan
                     for lo, hi in zip(TB[:-1], TB[1:])])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = np.load(DATA)
    res = {}
    fig, ax = plt.subplots(2, 3, figsize=(17, 9))
    for row, src in enumerate(("none", "cs137")):
        g = {k: D[f"{src}_{k}"] for k in ("x", "y", "drift_time", "s2_area", "s1_area", "s1_aft_led", "s2_range_50p_area")}
        t = g["drift_time"] / 1e3
        r = np.hypot(g["x"], g["y"])
        s1 = g["s1_area"]
        a1 = g["s1_aft_led"]
        ok1 = (s1 > S1MIN) & np.isfinite(a1)
        region = (g["y"] < -3) & (g["y"] > -17) & (r > 10) & (r < 18)
        normal = ok1 & (g["s2_area"] > 2e4) & (r < 18) & ~region
        cal = medians(t, a1, normal)
        good = np.isfinite(cal)
        # monotonic calibration (S1 AFT falls with depth): invert by interpolation on the sorted curve
        tc, cc = TC[good], cal[good]
        order = np.argsort(cc)

        def t_from_aft(a):
            return np.interp(a, cc[order], tc[order], left=np.nan, right=np.nan)

        dt_s1 = t_from_aft(a1)
        groups = {
            "y<0 region, S2>50k": ok1 & region & (g["s2_area"] > 5e4),
            "mirror y>0, S2>50k": ok1 & (g["y"] > 3) & (r > 10) & (r < 18) & (g["s2_area"] > 5e4),
        }
        if src == "none":
            groups["centre r<2.5, S2 3-20k"] = ok1 & (r < 2.5) & (g["s2_area"] > 3e3) & (g["s2_area"] < 2e4)
            groups["ring 7.5-12.5, S2 3-20k"] = ok1 & (r > 7.5) & (r < 12.5) & (g["s2_area"] > 3e3) & (g["s2_area"] < 2e4)
        out = dict(calibration_s1aft=[None if not np.isfinite(v) else round(float(v), 4) for v in cal], groups={})
        a = ax[row, 0]
        a.plot(TC, cal, "k-", lw=2, label="calibration (normal events)")
        for k, (name, m) in enumerate(groups.items()):
            a.plot(TC, medians(t, a1, m), "o--", ms=4, color=f"C{k}", label=name)
            d = dt_s1[m] - t[m]
            d = d[np.isfinite(d)]
            ax[row, 1].hist(d, np.linspace(-40, 40, 81), histtype="step", density=True, color=f"C{k}", label=name)
            s2s1 = g["s2_area"][m] / s1[m]
            ax[row, 2].hist(np.log10(s2s1), np.linspace(1, 4, 61), histtype="step", density=True, color=f"C{k}", label=name)
            shallow = m & (t < 20)
            ds = dt_s1[shallow] - t[shallow]
            ds = ds[np.isfinite(ds)]
            out["groups"][name] = dict(
                n=int(m.sum()), n_drift_lt_20=int(shallow.sum()),
                median_dt_s1_minus_drift_us=round(float(np.median(d)), 2) if len(d) else None,
                frac_off_by_more_than_10us=round(float(np.mean(np.abs(d) > 10)), 3) if len(d) else None,
                shallow_median_dt_s1_minus_drift_us=round(float(np.median(ds)), 2) if len(ds) else None,
                shallow_frac_off_10us=round(float(np.mean(np.abs(ds) > 10)), 3) if len(ds) else None,
                median_s1=round(float(np.median(s1[m])), 1), median_s2_over_s1=round(float(np.median(s2s1)), 1),
                median_s1_aft=round(float(np.median(a1[m])), 4))
        lab = "no source" if src == "none" else "Cs-137 (all energies)"
        a.set(xlabel="drift time [µs]", ylabel="median S1 AFT (LED gains)", title=f"{lab}: S1 AFT vs drift time (S1 > {S1MIN} PE)")
        a.legend(fontsize=7)
        ax[row, 1].set(xlabel="t(S1 AFT) − t(drift) [µs]", ylabel="normalised", title="depth from S1 AFT minus drift time")
        ax[row, 1].legend(fontsize=7)
        ax[row, 2].set(xlabel="log10(S2 / S1)", ylabel="normalised", title="S2 / S1")
        ax[row, 2].legend(fontsize=7)
        res[lab] = out
    fig.tight_layout()
    fig.savefig(OUT / "s1aft_depth.png", dpi=115)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    for lab, o in res.items():
        print(lab)
        for k, v in o["groups"].items():
            print(f"  {k:26s} {v}")


if __name__ == "__main__":
    main()
