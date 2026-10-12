#!/usr/bin/env python3
"""Unbiased search for local sources of the Cs-137 photopeak cS2 spread: spread per cell in azimuth × depth and in x-y
per depth slice, without assumptions about where anything sits.

Data: analysis_SR2026.2/outputs/s2_channels.npz, Cs-137 Δ750 V (all positions), photopeak band from the stbc-i2
edge fit, clean cuts (S1 ≥ 20 PE in top and bottom, drift > 3 µs, gate-corrected S2 width > 450 ns, S1 AFT consistent
with the drift time), r < 22 mm. cS2 = S2 × exp(t/τ) (τ 157 / 161 µs on 28 / 29-09), total and bottom only (LED gains;
the bottom PMT is hardly affected by the load). Spread per cell = 1.4826 · MAD / median (relative to the cell's own
median, so slow yield gradients do not count); error ≈ 1.25 · spread / sqrt(2n). Pull of a cell = (spread − global
median spread) / error.

    python tools/spread_map.py  ->  results/spread_map/ (spread_map.png, summary.json)
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

OUT = ROOT / "results" / "spread_map"
DATA = ROOT.parent / "measurements" / "analysis_SR2026.2" / "outputs" / "s2_channels.npz"
T_GATE, T_CATH, L = 1.15, 38.2, 51.8


def rspread(v):
    m = np.median(v)
    return 1.4826 * np.median(np.abs(v - m)) / m


def main():
    OUT.mkdir(parents=True, exist_ok=True)
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
    pk = clean & (g["cs1"] > band[0]) & (g["cs1"] < band[1]) & (r < 22)
    tau = np.where(g["run"] < 7680, 157.0, 161.0)
    corr = np.exp(t / tau)
    q = {"total": g["ch"].sum(1) * corr, "bottom": g["ch"][:, 0] * corr}
    res = {"n_photopeak": int(pk.sum())}
    PB = np.arange(0, 361, 30)
    ZB = np.array([-51.8, -42, -34, -26, -18, -10, -3])
    XB = np.arange(-22, 22.1, 5.5)
    fig, ax = plt.subplots(2, 4, figsize=(21, 9))
    for row, key in enumerate(("total", "bottom")):
        v = q[key]
        glob = rspread(v[pk])
        # azimuth x depth, outer region r 8-22 mm, plus the inner column r < 8 mm per depth
        M = np.full((len(PB) - 1, len(ZB) - 1), np.nan)
        PU = np.full_like(M, np.nan)
        for i, (p0, p1) in enumerate(zip(PB[:-1], PB[1:])):
            for j, (z0, z1) in enumerate(zip(ZB[:-1], ZB[1:])):
                m = pk & (r > 8) & (phi >= p0) & (phi < p1) & (z >= z0) & (z < z1)
                if m.sum() >= 60:
                    s = rspread(v[m])
                    M[i, j] = s
                    PU[i, j] = (s - glob) / (1.25 * s / np.sqrt(2 * m.sum()))
        inner = []
        for z0, z1 in zip(ZB[:-1], ZB[1:]):
            m = pk & (r <= 8) & (z >= z0) & (z < z1)
            inner.append(dict(z=[float(z0), float(z1)], n=int(m.sum()), spread=round(float(rspread(v[m])), 4) if m.sum() >= 60 else None))
        a = ax[row, 0]
        im = a.pcolormesh(PB, ZB, M.T, cmap="viridis", shading="flat")
        a.set(xlabel="azimuth φ [°] (data x-y frame)", ylabel="z [mm]", title=f"{key} cS2 spread, r 8–22 mm (global {glob:.3f})")
        plt.colorbar(im, ax=a, fraction=0.046, pad=0.03)
        a = ax[row, 1]
        im = a.pcolormesh(PB, ZB, PU.T, cmap="RdBu_r", vmin=-5, vmax=5, shading="flat")
        a.set(xlabel="azimuth φ [°]", ylabel="z [mm]", title=f"{key}: pull of each cell vs the global spread")
        plt.colorbar(im, ax=a, fraction=0.046, pad=0.03)
        # x-y for the upper and lower half of the drift region
        for k2, (z0, z1, lab) in enumerate(((-26, -3, "upper half"), (-51.8, -26, "lower half"))):
            S = np.full((len(XB) - 1, len(XB) - 1), np.nan)
            for i in range(len(XB) - 1):
                for j in range(len(XB) - 1):
                    m = pk & (x >= XB[i]) & (x < XB[i + 1]) & (y >= XB[j]) & (y < XB[j + 1]) & (z >= z0) & (z < z1)
                    if m.sum() >= 60:
                        S[i, j] = rspread(v[m])
            a = ax[row, 2 + k2]
            im = a.pcolormesh(XB, XB, S.T, cmap="viridis", vmin=glob * 0.8, vmax=glob * 1.25, shading="flat")
            a.set_aspect("equal")
            a.set(xlabel="x [mm]", ylabel="y [mm]", title=f"{key} cS2 spread, {lab} (z {z0:.0f} … {z1:.0f})")
            plt.colorbar(im, ax=a, fraction=0.046, pad=0.03)
            res.setdefault(key, {})[f"xy_{lab}"] = [[None if not np.isfinite(s_) else round(float(s_), 4) for s_ in rw] for rw in S]
        hot = [dict(phi=[float(PB[i]), float(PB[i + 1])], z=[float(ZB[j]), float(ZB[j + 1])], spread=round(float(M[i, j]), 4),
                    pull=round(float(PU[i, j]), 1)) for i in range(M.shape[0]) for j in range(M.shape[1]) if np.isfinite(PU[i, j]) and PU[i, j] > 3]
        res[key].update(global_spread=round(float(glob), 4), phi_z_spread=[[None if not np.isfinite(s_) else round(float(s_), 4) for s_ in rw] for rw in M],
                        phi_z_pull=[[None if not np.isfinite(s_) else round(float(s_), 1) for s_ in rw] for rw in PU],
                        inner_column=inner, cells_pull_gt_3=sorted(hot, key=lambda h: -h["pull"]),
                        pull_rms=round(float(np.nanstd(PU)), 2), phi_edges=PB.tolist(), z_edges=ZB.tolist())
    fig.suptitle("Cs-137 photopeak cS2 spread per cell (clean cuts, Δ750 V, all source positions)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "spread_map.png", dpi=105)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    for key in ("total", "bottom"):
        rr = res[key]
        print(key, "global", rr["global_spread"], "pull rms", rr["pull_rms"], "cells with pull > 3:", rr["cells_pull_gt_3"])
        print("   inner column (r<8) per z:", [(i["z"], i["spread"], i["n"]) for i in rr["inner_column"]])
        print("   spread by depth (median over azimuth):", [round(float(np.nanmedian([rw[j] for rw in rr["phi_z_spread"] if rw[j] is not None])), 3) for j in range(len(ZB) - 1)])
        print("   spread by azimuth (median over depth):", [round(float(np.nanmedian([s_ for s_ in rw if s_ is not None])), 3) if any(s_ is not None for s_ in rw) else None for rw in rr["phi_z_spread"]])


if __name__ == "__main__":
    main()
