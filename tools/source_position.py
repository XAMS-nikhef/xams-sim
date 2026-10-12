#!/usr/bin/env python3
"""Where was the (uncollimated) Cs-137 source? Fit of a point source to the 3D density of interactions.

Model per voxel (x, y, z): background(voxel) · [B + A · exp(−μ s) / d²], with d the distance source → voxel, s the path through
liquid xenon (inside the PTFE bucket, r < 56 mm, between the bucket floor z ≈ −113 mm and the liquid surface
z = +4 mm), μ = 0.022 /mm (662 keV in LXe; PTFE similar), background = the no-source density (same cuts): it carries the
detector's density distortions (slow drift at both ends, reconstruction), which act on source and background events
alike, so the source term is multiplied by it; A and B free (weighted least squares). Source position: radius R (outside the vessel), azimuth φ and height h
(z = 0 at the gate), grid search then refinement. z from the drift time for a uniform field (gate 1.15 µs, cathode
38.2 µs). Ignored: the steel vessel and cryostat walls (similar for all paths), PMTs and holders, scattering.

Data: analysis_SR2026.2/outputs/s2_channels.npz (Δ750 V, single scatters, S1 ≥ 20 PE top and bottom), r < 22 mm,
−48 < z < −3 mm. Frame: the data's x-y (v4 positions).

    python tools/source_position.py  ->  results/source_position/ (summary.json, source_position.png)
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "source_position"
DATA = ROOT.parent / "measurements" / "analysis_SR2026.2" / "outputs" / "s2_channels.npz"
MU, RB, ZTOP, ZBOT = 0.022, 56.0, 4.0, -113.0
T_GATE, T_CATH, L = 1.15, 38.2, 51.8
XE = np.arange(-22, 22.1, 4.0)
ZE = np.arange(-48, -2.9, 3.0)


POSITIONS = {"standard": [7645, 7646, 7647, 7648, 7649, 7668, 7669, 7687, 7688, 7689, 7690, 7691],
             "2 cm lower": [7665, 7666, 7667],
             "rotated ~170°": [7692, 7693, 7694, 7695, 7696],
             "rotated 90° clockwise": [7707, 7708, 7709, 7710] + list(range(7713, 7721))}


def load(src, runs=None):
    D = np.load(DATA)
    x, y, t = D[f"{src}_x"], D[f"{src}_y"], D[f"{src}_drift_time"] / 1e3
    a1, s1 = D[f"{src}_s1_aft_led"], D[f"{src}_s1_area"]
    z = -L * (t - T_GATE) / (T_CATH - T_GATE)
    m = (s1 >= 20) & (a1 > 0) & (a1 < 1) & (np.hypot(x, y) < 22)
    if runs is not None:
        m &= np.isin(D[f"{src}_run"], runs)
    H, _ = np.histogramdd(np.stack([x[m], y[m], z[m]], 1), bins=[XE, XE, ZE])
    return H


def path_in_lxe(S, P):
    """length of the segment S -> P (P inside) that lies in the LXe cylinder; S (3,), P (N,3)"""
    d = P - S
    a = d[:, 0] ** 2 + d[:, 1] ** 2
    b = 2 * (S[0] * d[:, 0] + S[1] * d[:, 1])
    c = S[0] ** 2 + S[1] ** 2 - RB ** 2
    disc = np.clip(b * b - 4 * a * c, 0, None)
    u_in = np.where(c > 0, (-b - np.sqrt(disc)) / (2 * np.where(a > 0, a, 1)), 0.0)
    u_in = np.clip(u_in, 0, 1)
    if S[2] > ZTOP:
        u_in = np.maximum(u_in, (ZTOP - S[2]) / (P[:, 2] - S[2]))
    if S[2] < ZBOT:
        u_in = np.maximum(u_in, (ZBOT - S[2]) / (P[:, 2] - S[2]))
    return (1 - np.clip(u_in, 0, 1)) * np.linalg.norm(d, axis=1)


def fit_position(Hc, Hb):
    xc, zc = 0.5 * (XE[1:] + XE[:-1]), 0.5 * (ZE[1:] + ZE[:-1])
    X, Y, Z = np.meshgrid(xc, xc, zc, indexing="ij")
    inside = (np.hypot(X, Y) < 22) & (Hb > 0)
    P = np.stack([X[inside], Y[inside], Z[inside]], 1)
    n = Hc[inside]
    bk = Hb[inside] / Hb[inside].mean()
    w = 1 / np.maximum(n, 1)

    def fit(S):
        sig = np.exp(-MU * path_in_lxe(S, P)) / np.sum((P - S) ** 2, axis=1)
        M = np.stack([bk * sig / sig.mean(), bk], 1)
        Aw = M * np.sqrt(w)[:, None]
        coef, *_ = np.linalg.lstsq(Aw, n * np.sqrt(w), rcond=None)
        coef = np.clip(coef, 0, None)
        return float(np.sum(w * (n - M @ coef) ** 2)), coef

    best = None
    for R in (85, 110, 140, 180, 240, 320, 450):
        for ph in np.radians(np.arange(0, 360, 10)):
            for h in np.arange(-180, 181, 20):
                S = np.array([R * np.cos(ph), R * np.sin(ph), h])
                c, coef = fit(S)
                if best is None or c < best[0]:
                    best = (c, S, coef)
    for _ in range(2):
        c0, S0, _ = best
        R0, ph0, h0 = np.hypot(S0[0], S0[1]), np.arctan2(S0[1], S0[0]), S0[2]
        for R in np.linspace(max(80, R0 * 0.7), R0 * 1.4, 15):
            for ph in ph0 + np.radians(np.arange(-10, 10.1, 2)):
                for h in np.arange(h0 - 20, h0 + 20.1, 4):
                    S = np.array([R * np.cos(ph), R * np.sin(ph), h])
                    c, coef = fit(S)
                    if c < best[0]:
                        best = (c, S, coef)
    c, S, coef = best
    R, ph = float(np.hypot(S[0], S[1])), float(np.degrees(np.arctan2(S[1], S[0])) % 360)
    prof = {}
    for name, vals in (("R_mm", np.linspace(80, 500, 22)), ("phi_deg", np.arange(0, 360, 5)), ("h_mm", np.arange(-180, 181, 5))):
        out = []
        for v in vals:
            if name == "R_mm":
                Sx = np.array([v * np.cos(np.radians(ph)), v * np.sin(np.radians(ph)), S[2]])
            elif name == "phi_deg":
                Sx = np.array([R * np.cos(np.radians(v)), R * np.sin(np.radians(v)), S[2]])
            else:
                Sx = np.array([S[0], S[1], v])
            out.append(fit(Sx)[0] - c)
        prof[name] = dict(values=[float(v) for v in vals], dchi2=[round(float(q), 1) for q in out])

    def interval(name):
        v, d = np.array(prof[name]["values"]), np.array(prof[name]["dchi2"])
        ok = v[d < 1.0 * c / max(int(inside.sum()) - 5, 1)]   # Δχ² < 1 after scaling by χ²/ndf
        return [float(ok.min()), float(ok.max())] if len(ok) else None

    return dict(radius_mm=round(R, 1), azimuth_deg=round(ph, 1), height_mm=round(float(S[2]), 1),
                source_xyz_mm=[round(float(q), 1) for q in S], chi2=round(c, 1), ndf=int(inside.sum() - 5),
                source_to_background=round(float(coef[0] / max(coef[1], 1e-9)), 3), n_events=int(n.sum()),
                range_R=interval("R_mm"), range_phi=interval("phi_deg"), range_h=interval("h_mm"), profiles=prof)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    Hb = load("none")
    res = {}
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for k, (name, runs) in enumerate(POSITIONS.items()):
        r = fit_position(load("cs137", runs), Hb)
        res[name] = r
        print(f"{name:24s} R {r['radius_mm']:6.0f} mm {r['range_R']}  φ {r['azimuth_deg']:5.0f}° {r['range_phi']}  "
              f"h {r['height_mm']:6.0f} mm {r['range_h']}  χ² {r['chi2']:.0f}/{r['ndf']}  n {r['n_events']}  S/B {r['source_to_background']}")
        for a, key in zip(ax, ("R_mm", "phi_deg", "h_mm")):
            a.plot(r["profiles"][key]["values"], np.array(r["profiles"][key]["dchi2"]) / (r["chi2"] / r["ndf"]), "-", color=f"C{k}", label=name)
    for a, lab in zip(ax, ("source distance from the axis R [mm]", "azimuth φ [°] (data x-y frame)", "height h [mm] (gate 0, cathode −51.8)")):
        a.set(xlabel=lab, ylabel="Δχ² (÷ χ²/ndf)", ylim=(0, 50))
        a.legend(fontsize=7)
    fig.suptitle("Cs-137 source position per run group (point source, LXe attenuation, background-shaped acceptance)", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "source_position.png", dpi=120)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
