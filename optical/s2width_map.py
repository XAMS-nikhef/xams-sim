#!/usr/bin/env python3
"""S2 width maps: are the narrow small S2s local to the centre?

Data: analysis_SR2026.2/outputs/s2_channels.npz (single scatters, Δ750 V, v4 positions). Quality cuts: S1 ≥ 20 PE seen
by top and bottom, S1 AFT consistent with the drift time (3σ, as optsim_targets S1CUT=1). Width = S2 range_50p_area,
corrected to the gate for diffusion: w_gate = sqrt(w² − k·t), k = 3600 ns²/µs (step3_drift width50² slope).
Panels: median w_gate on x-y per S2 size class (no source 3–20 kPE, 20–50 kPE, > 50 kPE; Cs-137 photopeak); w_gate and
AFT versus r; AFT versus w_gate at the centre and in the ring.

    python optical/s2width_map.py  ->  results/s2width_map/ (s2width_map.png, summary.json)
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
from s1cut_spectrum import s1_consistent  # noqa: E402

OUT = ROOT / "results" / "s2width_map"
DATA = ROOT.parent / "measurements" / "analysis_SR2026.2" / "outputs" / "s2_channels.npz"
K_DIFF = 3600.0
E = np.arange(-25, 25.1, 2.5)
RE = np.arange(0, 25.1, 2.5)
RC = 0.5 * (RE[1:] + RE[:-1])


def load(src):
    D = np.load(DATA)
    g = {k: D[f"{src}_{k}"] for k in ("x", "y", "drift_time", "s2_area", "s1_area", "s1_aft_led", "s2_range_50p_area",
                                      "ch", "cs1")}
    t = g["drift_time"] / 1e3
    r = np.hypot(g["x"], g["y"])
    a1 = g["s1_aft_led"]
    q = (g["s1_area"] >= 20) & (a1 > 0) & (a1 < 1) & s1_consistent(t, a1, g["s1_area"], (g["s2_area"] > 2e4) & (r < 18))
    w = g["s2_range_50p_area"]
    wg = np.sqrt(np.clip(w ** 2 - K_DIFF * t, 0, None))
    top = g["ch"][:, 1:].sum(1)
    aft = top / (top + g["ch"][:, 0])
    return dict(x=g["x"], y=g["y"], r=r, t=t, s2=g["s2_area"], cs1=g["cs1"], wg=wg, aft=aft, q=q)


def grid(x, y, v, nmin=15):
    i, j = np.digitize(x, E) - 1, np.digitize(y, E) - 1
    n = len(E) - 1
    M = np.full((n, n), np.nan)
    for a in range(n):
        for b in range(n):
            m = (i == a) & (j == b)
            if m.sum() >= nmin:
                M[a, b] = np.median(v[m])
    return M


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    B, C = load("none"), load("cs137")
    band = np.load(DATA.parent / "aft_maps.npz")["cs_cs1_band"]
    pk = C["q"] & (C["cs1"] > band[0]) & (C["cs1"] < band[1])
    classes = [("no source 3–20 kPE", B, B["q"] & (B["s2"] > 3e3) & (B["s2"] < 2e4)),
               ("no source 20–50 kPE", B, B["q"] & (B["s2"] > 2e4) & (B["s2"] < 5e4)),
               ("no source > 50 kPE", B, B["q"] & (B["s2"] > 5e4)),
               ("Cs-137 photopeak", C, pk)]
    fig, ax = plt.subplots(2, 4, figsize=(20, 9))
    res = {}
    for k, (lab, S, m) in enumerate(classes):
        M = grid(S["x"][m], S["y"][m], S["wg"][m])
        a = ax[0, k]
        im = a.pcolormesh(E, E, M.T, cmap="viridis", vmin=300, vmax=650, shading="flat")
        ph = np.linspace(0, 2 * np.pi, 200)
        a.plot(25 * np.cos(ph), 25 * np.sin(ph), "w--", lw=0.6)
        a.set_aspect("equal")
        a.set(xlabel="x [mm]", ylabel="y [mm]", title=f"S2 width50 at the gate: {lab}")
        plt.colorbar(im, ax=a, fraction=0.046, pad=0.03, label="ns")
        wr = [float(np.median(S["wg"][m & (S["r"] >= lo) & (S["r"] < hi)])) if (m & (S["r"] >= lo) & (S["r"] < hi)).sum() > 15
              else None for lo, hi in zip(RE[:-1], RE[1:])]
        ar = [float(np.median(S["aft"][m & (S["r"] >= lo) & (S["r"] < hi)])) if (m & (S["r"] >= lo) & (S["r"] < hi)).sum() > 15
              else None for lo, hi in zip(RE[:-1], RE[1:])]
        ax[1, 0].plot(RC, [np.nan if v is None else v for v in wr], "o-", ms=4, label=lab)
        ax[1, 1].plot(RC, [np.nan if v is None else v for v in ar], "o-", ms=4, label=lab)
        cen, ring = m & (S["r"] < 2.5), m & (S["r"] > 7.5) & (S["r"] < 12.5)
        res[lab] = dict(n=int(m.sum()), width_gate_vs_r=wr, aft_vs_r=ar,
                        width_centre=float(np.median(S["wg"][cen])) if cen.sum() else None,
                        width_ring=float(np.median(S["wg"][ring])) if ring.sum() else None,
                        frac_narrow_lt_450_centre=float(np.mean(S["wg"][cen] < 450)) if cen.sum() else None,
                        frac_narrow_lt_450_ring=float(np.mean(S["wg"][ring] < 450)) if ring.sum() else None)
    ax[1, 0].set(xlabel="r [mm]", ylabel="median S2 width50 at the gate [ns]", title="S2 width versus r")
    ax[1, 1].set(xlabel="r [mm]", ylabel="median S2 AFT (LED gains)", title="S2 AFT versus r")
    for a in ax[1, :2]:
        a.legend(fontsize=7)
    # AFT versus width, small no-source S2s: centre vs ring
    m = classes[0][2]
    wb = np.arange(200, 801, 50)
    wc = 0.5 * (wb[1:] + wb[:-1])
    for lab, sel, st in (("centre r < 2.5", m & (B["r"] < 2.5), "o-"), ("ring 7.5–12.5", m & (B["r"] > 7.5) & (B["r"] < 12.5), "s--"),
                         ("r 12.5–20", m & (B["r"] > 12.5) & (B["r"] < 20), "^:")):
        v = [np.median(B["aft"][sel & (B["wg"] >= a) & (B["wg"] < b)]) if (sel & (B["wg"] >= a) & (B["wg"] < b)).sum() > 10 else np.nan
             for a, b in zip(wb[:-1], wb[1:])]
        ax[1, 2].plot(wc, v, st, label=lab)
        ax[1, 3].hist(B["wg"][sel], wb, histtype="step", density=True, label=lab)
    ax[1, 2].set(xlabel="S2 width50 at the gate [ns]", ylabel="median S2 AFT", title="no source 3–20 kPE: AFT versus width")
    ax[1, 3].set(xlabel="S2 width50 at the gate [ns]", ylabel="normalised", title="no source 3–20 kPE: width distribution")
    for a in ax[1, 2:]:
        a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "s2width_map.png", dpi=110)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    for lab, v in res.items():
        print(lab, {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items() if not k.endswith("_vs_r")})
        print("   width vs r", [None if x is None else round(x) for x in v["width_gate_vs_r"]])


if __name__ == "__main__":
    main()
