#!/usr/bin/env python3
"""Two checks of the SiPM / drift-field hypothesis with existing data (2026-10-12).

1. Apparent electron lifetime versus radius: ln(S2) versus drift time for Cs-137 photopeak events (clean cuts, no
   lifetime correction), per radius ring and per half (azimuth). Attachment to impurities gives the same τ
   everywhere; a geometric charge loss towards the wall (electrons pulled to the SiPMs) gives a shorter apparent τ
   near the wall.
2. Spread of deep events versus time since HV-on: per run, the bottom-PMT cS2 spread of photopeak events with
   z < −26 mm against the time since the last cathode ramp-up (slow-control archive). Charge-up of an insulating foil
   would give a trend in the first hours.

Inputs: analysis_SR2026.2/outputs/s2_channels.npz; run start times (run database, read-only) and the HV lines of the
slow-control archive (read-only), both copied to the session scratchpad (paths as arguments).
    python tools/sipm_checks.py RUNTIMES.json SC_HV.jsonl  ->  results/sipm_checks/ (sipm_checks.png, summary.json)
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
from s1cut_spectrum import s1_consistent  # noqa: E402

OUT = ROOT / "results" / "sipm_checks"
DATA = ROOT.parent / "notebooks" / "analysis_SR2026.2" / "outputs" / "s2_channels.npz"
T_GATE, T_CATH, L = 1.15, 38.2, 51.8


def rspread(v):
    m = np.median(v)
    return 1.4826 * np.median(np.abs(v - m)) / m


def fit_tau(t, s2):
    """robust ln(S2) vs t: medians in 3 µs bins (4-34 µs), weighted line fit -> τ [µs] and error"""
    tb = np.arange(4, 34.01, 3.0)
    tc, md, me = [], [], []
    for a, b in zip(tb[:-1], tb[1:]):
        m = (t >= a) & (t < b) & (s2 > 0)
        if m.sum() >= 40:
            v = np.log(s2[m])
            tc.append(0.5 * (a + b)), md.append(np.median(v)), me.append(1.2533 * np.std(v) / np.sqrt(m.sum()))
    tc, md, me = map(np.array, (tc, md, me))
    if len(tc) < 4:
        return np.nan, np.nan
    (k, c), cov = np.polyfit(tc, md, 1, w=1 / me, cov="unscaled")
    tau = -1 / k
    return float(tau), float(np.sqrt(cov[0, 0]) / k ** 2)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    runtimes = {int(k): v for k, v in json.load(open(sys.argv[1])).items()}
    D = np.load(DATA)
    g = {k: D[f"cs137_{k}"] for k in ("x", "y", "drift_time", "s2_area", "s1_area", "s1_aft_led", "s2_range_50p_area", "cs1", "ch", "run")}
    t = g["drift_time"] / 1e3
    x, y = g["x"], g["y"]
    r, phi = np.hypot(x, y), np.degrees(np.arctan2(y, x)) % 360
    z = -L * (t - T_GATE) / (T_CATH - T_GATE)
    a1, s1 = g["s1_aft_led"], g["s1_area"]
    wg = np.sqrt(np.clip(g["s2_range_50p_area"] ** 2 - 3600 * t, 0, None))
    band = np.load(DATA.parent / "aft_maps.npz")["cs_cs1_band"]
    clean = (s1 >= 20) & (a1 > 0) & (a1 < 1) & (t > 3) & (wg > 450) & s1_consistent(t, a1, s1, (g["s2_area"] > 2e4) & (r < 18))
    pk = clean & (g["cs1"] > band[0]) & (g["cs1"] < band[1])
    s2b, s2t = g["ch"][:, 0], g["ch"].sum(1)
    res = {"lifetime": {}, "time_since_hv": {}}
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.6))
    # ---- 1: apparent lifetime versus radius, per day (lifetimes differ per day) and per azimuth half
    rings = [(0, 8), (8, 14), (14, 19), (19, 24)]
    for k, (day, lo, hi) in enumerate((("28-09", 7600, 7680), ("29-09", 7680, 7730))):
        d = pk & (g["run"] >= lo) & (g["run"] < hi)
        for lab, sel, st in (("all φ", np.ones_like(d), "o-"), ("φ 0–150°", (phi < 150), "s--"), ("φ 150–360°", (phi >= 150), "^:")):
            taus, errs = [], []
            for a, b in rings:
                m = d & sel & (r >= a) & (r < b)
                tau, e = fit_tau(t[m], s2b[m])
                taus.append(tau), errs.append(e)
            res["lifetime"][f"{day} {lab}"] = dict(rings=rings, tau_bottom_us=[round(v, 1) for v in taus], err=[round(v, 1) for v in errs])
            ax[0].errorbar([0.5 * (a + b) for a, b in rings], taus, errs, fmt=st, ms=4, color=f"C{k}", label=f"{day}, {lab}")
    ax[0].set(xlabel="r [mm]", ylabel="apparent lifetime τ (bottom S2) [µs]", title="Apparent electron lifetime versus radius", ylim=(0, 400))
    ax[0].legend(fontsize=6.5)
    # ---- 2: deep spread per run versus time since the last cathode ramp-up
    tc, vc = [], []
    for line in open(sys.argv[2]):
        if '"hv_cathode_vmon"' in line:
            dd = json.loads(line)
            if dd.get("q") == "ok":
                tc.append(np.datetime64(dd["t"][:19]).astype("datetime64[s]").astype(float)), vc.append(abs(dd["v"]))
    tc, vc = np.array(tc), np.array(vc)
    on = vc > 1000
    ramps = tc[1:][on[1:] & ~on[:-1]]                                 # cathode crossing 1 kV upward
    # also the anode restart after the 29-09 trip: any supply crossing up counts — use the anode as well
    ta, va = [], []
    for line in open(sys.argv[2]):
        if '"hv_anode_vmon"' in line:
            dd = json.loads(line)
            if dd.get("q") == "ok":
                ta.append(np.datetime64(dd["t"][:19]).astype("datetime64[s]").astype(float)), va.append(abs(dd["v"]))
    ta, va = np.array(ta), np.array(va)
    aon = va > 1000
    ramps = np.sort(np.concatenate([ramps, ta[1:][aon[1:] & ~aon[:-1]]]))
    rows = []
    for run in np.unique(g["run"]).astype(int):
        if run not in runtimes:
            continue
        t0 = np.datetime64(runtimes[run][0][:19]).astype("datetime64[s]").astype(float)
        prev = ramps[ramps <= t0]
        if not len(prev):
            continue
        since_h = (t0 - prev[-1]) / 3600
        m = pk & (g["run"] == run)
        deep, top = m & (z < -26), m & (z > -15)
        if deep.sum() >= 150 and top.sum() >= 100:
            rows.append((run, since_h, rspread(s2b[deep] * np.exp(t[deep] / 160)), rspread(s2b[top] * np.exp(t[top] / 160)),
                         int(deep.sum())))
    rows = np.array(rows)
    res["time_since_hv"] = dict(columns=["run", "hours_since_hv_on", "deep_spread", "top_spread", "n_deep"],
                                rows=[[int(a), round(b, 2), round(c, 3), round(d, 3), int(e)] for a, b, c, d, e in rows],
                                hv_ramp_times=[str(np.datetime64(int(v), "s")) for v in ramps])
    ax[1].plot(rows[:, 1], rows[:, 2], "o", label="deep (z < −26 mm)")
    ax[1].plot(rows[:, 1], rows[:, 3], "s", label="top (z > −15 mm)")
    ax[1].set(xscale="log", xlabel="time since HV-on [h]", ylabel="bottom cS2 spread per run (photopeak)", title="Spread per run versus time since HV-on")
    ax[1].legend(fontsize=8)
    ax[2].plot(rows[:, 0], rows[:, 2], "o", label="deep")
    ax[2].plot(rows[:, 0], rows[:, 3], "s", label="top")
    ax[2].set(xlabel="run", ylabel="spread", title="Spread per run")
    ax[2].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "sipm_checks.png", dpi=115)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    for k, v in res["lifetime"].items():
        print(f"{k:22s} τ by ring {v['rings']}: {v['tau_bottom_us']} ± {v['err']}")
    print("HV ramp-up times:", res["time_since_hv"]["hv_ramp_times"])
    for row in res["time_since_hv"]["rows"]:
        print("   run %d  %.2f h after HV-on  deep %.3f  top %.3f  (n %d)" % tuple(row))


if __name__ == "__main__":
    main()
