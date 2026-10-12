#!/usr/bin/env python3
"""Threshold / charge-sharing toy (option A): can the readout make the central dip of the S2 area fraction top?

Per event: S2 photons shared over the five PMT channels with the simulated light response at the event position
(geometry v4, fit_s2 points PTFE R 0.95 / specular 0.1 / steel R 0.2, Rayleigh 30/45/60 pooled), arrival times from
the S2 time profile (electrons spread by diffusion, each emitting uniformly while crossing the gas gap), 4 ns samples,
single-PE charge with gain spread, measured single-photon pulse shapes, noise. Then the readout as in the data:
  - V1725 self-trigger per channel: a record runs from 32 samples before a threshold crossing until 24 samples
    under threshold (DAQ threshold top 30 ADC on 28-09 / 20 ADC on 29-09, bottom 60 ADC);
  - amstrax hits: samples >= 15 ADC (strax.find_hits default) inside records; the S2 area per channel is the sum of
    hit samples only (strax.sum_waveform uses the hit waveform, no integration extension);
  - peak: hits of all channels clustered with a 300 ns gap; the S2 is the largest cluster;
  - area -> PE with the LED gains (as the data targets, "led").
Output: S2 area fraction top vs true r for the data's S2-size classes, and vs S2 size, next to the data
(targets/data_2026-10-05_single.json, no source).

    python tools/threshold_toy.py [--n 40000] [--pe-per-e 25] [--q 1.0]  ->  results/threshold_toy/
Positions are the true ones (no position reconstruction). Not modelled: afterpulses, delayed electrons / photons,
PMT non-linearity and the load effect, baseline shifts, peak splitting.
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from read_output import read  # noqa: E402

OUT = ROOT / "results" / "threshold_toy"
ANA = ROOT.parent / "measurements" / "analysis_SR2026.2"
CH = (0, 1, 2, 3, 4)                      # 0 = bottom, 1-4 = top anodes
GAIN = np.array([12.6, 56.0, 47.8, 53.0, 44.6])   # ADC*samples per PE (LED, P3a/P3b/P4 average; bottom -800 V)
GAIN_RES = np.array([0.40, 0.39, 0.44, 0.40, 0.38])  # single-PE resolution (LED fits)
NOISE = 3.0                               # ADC rms per sample (2.4 PMTs off, ~+1 with HV on)
HIT_THR = 15                              # strax.find_hits default
PRE, SUT = 32, 24                         # samples (0x8038 = 8, 0x8078 = 6)
GAP = 75                                  # 300 ns peak gap in samples
DT = 4.0                                  # ns per sample
W_BOX = 480.0                             # ns, gas-gap crossing (S2 width50 ~520 ns at the gate)
DIFF_K = 3600.0                           # width50^2 slope ns^2/us (step3_drift)
T_MAX = 40.0                              # us, drift time to the cathode at 750 V
NWIN = 1400                               # samples per event window


def templates():
    d = np.load(ANA / "outputs" / "delayed" / "pulse_shapes.npz")
    t = {}
    for c in CH:
        w = d[f"r007717_ch0"] if c == 0 else d[f"r007682_ch{c}"]   # bottom: science run (LED shape is not single PE)
        w = np.clip(w, 0, None)
        t[c] = w / w.sum()
    return t


def light_map(cell=1.0, rmax=27.0):
    """per-cell channel counts of detected photons by origin, pooled over the three Rayleigh points"""
    idx = json.load(open(ROOT / "run" / "scans" / "fit_s2" / "points.json"))
    want = {"optics.ptfe_in_liquid.reflectivity": 0.95, "optics.ptfe_in_liquid.specular_fraction": 0.1,
            "optics.stainless_steel_reflectivity": 0.2}
    nb = int(2 * rmax / cell)
    H = np.zeros((5, nb, nb))
    for p in idx["points"]:
        if any(abs(p["params"][k] - v) > 1e-9 for k, v in want.items()):
            continue
        for q in p["parts"]:
            rec = read(ROOT / "run" / "scans" / "fit_s2" / q["file"])[0]
            rec = rec[np.isin(rec["sensor"], CH)]
            x, y = -rec["x0"], rec["y0"]                    # data frame
            for c in CH:
                m = rec["sensor"] == c
                H[c] += np.histogram2d(x[m], y[m], bins=nb, range=[[-rmax, rmax], [-rmax, rmax]])[0]
    # 3x3 smoothing (3 mm box) for statistics
    from numpy.lib.stride_tricks import sliding_window_view
    P = np.pad(H, ((0, 0), (1, 1), (1, 1)))
    Hs = sliding_window_view(P, (3, 3), axis=(1, 2)).sum(axis=(-1, -2))
    return Hs, cell, rmax


def channel_probs(Hs, cell, rmax, x, y, q):
    i = np.clip(((x + rmax) / cell).astype(int), 0, Hs.shape[1] - 1)
    j = np.clip(((y + rmax) / cell).astype(int), 0, Hs.shape[2] - 1)
    n = Hs[:, i, j].T.copy()                                # (events, 5)
    n[:, 1:] *= q                                           # top/bottom efficiency ratio
    return n / n.sum(1, keepdims=True)


def dilate(a, left, right):
    """True where some a within [i - right, i + left] (record from crossing - PRE to last above + SUT)"""
    c = np.concatenate([[0], np.cumsum(a)])
    n = len(a)
    i = np.arange(n)
    lo = np.clip(i - right, 0, n)
    hi = np.clip(i + left + 1, 0, n)
    return (c[hi] - c[lo]) > 0


def event(rng, n_pe, p, sigma_ns, thr_top, tmpl, pe_per_e):
    n_e = max(rng.poisson(n_pe / pe_per_e), 1)
    # expected photons per sample: each electron spreads its photons uniformly over the box
    t0 = -4 * sigma_ns - 200
    starts = rng.normal(0, sigma_ns, n_e)
    lam = np.zeros(NWIN)
    k = int(W_BOX / DT)
    s_idx = np.clip(((starts - t0) / DT).astype(int), 0, NWIN - k - 1)
    np.add.at(lam, s_idx, 1.0)
    lam = np.convolve(lam, np.ones(k), mode="full")[:NWIN] * (n_pe / n_e / k)
    areas, hits_t, hits_a, hits_c = np.zeros(5), [], [], []
    for c in CH:
        n = rng.poisson(lam * p[c])
        q = GAIN[c] * (n + np.sqrt(n) * GAIN_RES[c] * rng.standard_normal(NWIN))
        q = np.clip(q, 0, None)
        wf = np.convolve(q, tmpl[c], mode="full")[:NWIN] + rng.normal(0, NOISE, NWIN)
        thr = 60 if c == 0 else thr_top
        rec = dilate(wf >= thr, SUT, PRE)
        h = rec & (wf >= HIT_THR)
        ii = np.nonzero(h)[0]
        hits_t.append(ii), hits_a.append(wf[ii]), hits_c.append(np.full(len(ii), c))
    t = np.concatenate(hits_t)
    if not len(t):
        return np.zeros(5)
    a, ch = np.concatenate(hits_a), np.concatenate(hits_c)
    o = np.argsort(t, kind="stable")
    t, a, ch = t[o], a[o], ch[o]
    cl = np.concatenate([[0], np.cumsum(np.diff(t) > GAP)])
    best = np.argmax(np.bincount(cl, weights=a / GAIN[ch]))
    m = cl == best
    for c in CH:
        areas[c] = a[m & (ch == c)].sum()
    return areas / GAIN                                                       # PE with LED gains


def run(args):
    rng = np.random.default_rng(args.seed)
    tmpl = templates()
    Hs, cell, rmax = light_map()
    n = args.n
    r = 25 * np.sqrt(rng.uniform(0, 1, n))
    ph = rng.uniform(0, 2 * np.pi, n)
    x, y = r * np.cos(ph), r * np.sin(ph)
    td = rng.uniform(0.5, T_MAX - 1, n)
    sig = np.sqrt(DIFF_K * td) / 2.355
    n_pe = np.exp(rng.uniform(np.log(1.5e3), np.log(4e5), n))
    thr = np.where(rng.uniform(0, 1, n) < 0.5, 30, 20)
    P = channel_probs(Hs, cell, rmax, x, y, args.q)
    A = np.zeros((n, 5))
    for i in range(n):
        A[i] = event(rng, n_pe[i], P[i], sig[i], thr[i], tmpl, args.pe_per_e)
        if i % 5000 == 0:
            print(i, flush=True)
    return dict(r=r, n_pe=n_pe, thr=thr, P=P, A=A, td=td)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40000)
    ap.add_argument("--pe-per-e", type=float, default=25.0)
    ap.add_argument("--q", type=float, default=1.0, help="top/bottom efficiency ratio applied to the light response")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    R = run(args)
    A, r = R["A"], R["r"]
    top, bot = A[:, 1:].sum(1), A[:, 0]
    s2 = top + bot
    aft = top / np.maximum(s2, 1e-9)
    aft_true = R["P"][:, 1:].sum(1)
    D = json.load(open(ROOT / "targets" / "data_2026-10-05_single.json"))["none"]
    E = json.load(open(ROOT / "targets" / "data_2026-10-05_single.json"))["edges"]
    re_ = np.array(E["r"])
    rc = 0.5 * (re_[1:] + re_[:-1])
    sizes = [(3e3, 5e3), (5e3, 1e4), (1e4, 2e4), (2e4, 5e4), (5e4, 3e5)]
    res = dict(args=vars(args), r_centres=rc.tolist(), by_size={}, keep_top=[], keep_bot=[])
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
    for k, (lo, hi) in enumerate(sizes):
        ms = (s2 >= lo) & (s2 < hi)
        toy = [float(np.median(aft[ms & (r >= a) & (r < b)])) if (ms & (r >= a) & (r < b)).sum() > 20 else None
               for a, b in zip(re_[:-1], re_[1:])]
        tru = [float(np.median(aft_true[ms & (r >= a) & (r < b)])) if (ms & (r >= a) & (r < b)).sum() > 20 else None
               for a, b in zip(re_[:-1], re_[1:])]
        key = f"{lo:.0f}-{hi:.0f}"
        res["by_size"][key] = dict(toy=toy, true=tru)
        col = f"C{k}"
        ax[0].plot(rc, [np.nan if v is None else v for v in toy], "-", color=col, lw=2, alpha=0.6, label=f"toy {lo/1e3:.0f}–{hi/1e3:.0f} kPE")
        d = D["s2_aft_vs_r_by_size_led"][key]
        ax[0].errorbar(rc, [np.nan if v is None else v for v in d["aft"]], [np.nan if v is None else v for v in d["err"]],
                       fmt="o", ms=4, color=col)
        tv = np.array([np.nan if v is None else v for v in toy])
        dv = np.array([np.nan if v is None else v for v in d["aft"]])
        ring = (rc > 7) & (rc < 13)
        res["by_size"][key]["toy_centre_over_ring"] = float(tv[0] / np.nanmean(tv[ring]))
        res["by_size"][key]["data_centre_over_ring"] = float(dv[0] / np.nanmean(dv[ring]))
        res["by_size"][key]["true_centre_over_ring"] = float(tru[0] / np.nanmean(np.array(tru, float)[ring])) if tru[0] else None
    ax[0].set(xlabel="r [mm] (toy: true r)", ylabel="S2 area fraction top", title="AFT vs r per S2 size: toy (lines) vs data (points)")
    ax[0].legend(fontsize=7)
    # centre / ring vs size
    xs = [np.sqrt(lo * hi) for lo, hi in sizes]
    ax[1].plot(xs, [res["by_size"][f"{lo:.0f}-{hi:.0f}"]["toy_centre_over_ring"] for lo, hi in sizes], "s-", label="toy (readout)")
    ax[1].plot(xs, [res["by_size"][f"{lo:.0f}-{hi:.0f}"]["true_centre_over_ring"] for lo, hi in sizes], "^--", label="toy, no readout loss")
    ax[1].plot(xs, [res["by_size"][f"{lo:.0f}-{hi:.0f}"]["data_centre_over_ring"] for lo, hi in sizes], "o", color="k", label="data")
    ax[1].set(xscale="log", xlabel="S2 [PE]", ylabel="AFT(r < 2.5) / AFT(7.5–12.5 mm)", title="central dip vs S2 size")
    ax[1].legend(fontsize=8)
    # kept fraction vs size, centre vs ring
    se = np.array(E["s2"])
    for lab, m, st in (("centre r<2.5", r < 2.5, "-"), ("ring 7.5–12.5", (r > 7.5) & (r < 12.5), "--")):
        kt = [float(np.median((top / (R["n_pe"] * aft_true))[m & (s2 >= a) & (s2 < b)])) for a, b in zip(se[:-1], se[1:])]
        kb = [float(np.median((bot / (R["n_pe"] * (1 - aft_true)))[m & (s2 >= a) & (s2 < b)])) for a, b in zip(se[:-1], se[1:])]
        sc = np.sqrt(se[:-1] * se[1:])
        ax[2].plot(sc, kt, "C3" + st, label=f"top kept, {lab}")
        ax[2].plot(sc, kb, "C0" + st, label=f"bottom kept, {lab}")
        res["keep_top"].append(dict(sel=lab, s2=sc.tolist(), keep=kt))
        res["keep_bot"].append(dict(sel=lab, s2=sc.tolist(), keep=kb))
    ax[2].set(xscale="log", xlabel="S2 [PE] (measured)", ylabel="measured / true PE", title="charge kept by the readout")
    ax[2].legend(fontsize=7)
    # AFT vs size (r < 25) toy vs data
    aft_size = [float(np.median(aft[(s2 >= a) & (s2 < b)])) for a, b in zip(se[:-1], se[1:])]
    res["aft_vs_size_toy"] = aft_size
    res["aft_vs_size_data"] = D["s2_aft_vs_size_led"]
    fig.tight_layout()
    fig.savefig(OUT / f"threshold_toy{args.tag}.png", dpi=130)
    json.dump(res, open(OUT / f"summary{args.tag}.json", "w"), indent=1)
    print(json.dumps({k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if "over" in kk}
                      for k, v in res["by_size"].items()}, indent=1))
    print("AFT vs size toy ", [round(v, 3) for v in aft_size])
    print("AFT vs size data", [None if v is None else round(v, 3) for v in D["s2_aft_vs_size_led"]])


if __name__ == "__main__":
    main()
