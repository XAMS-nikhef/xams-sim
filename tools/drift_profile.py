#!/usr/bin/env python3
"""Drift-velocity profile from the S1 area fraction top: depth z from the S1 light split, versus the drift time.

The S1 AFT of an event depends on its depth (simulation: 0.11 at the cathode → 0.25 at the gate for equal QE), not on
the drift field. Measured median S1 AFT versus drift time, compared with the simulated S1 AFT(z) (best optics): since the S1 AFT
is small, ε_S1 is a near-pure scale and the local velocity v(t) ∝ (dAFT/dt)_data ÷ (dAFT/dz)_sim does not depend on it;
the scale follows from ∫ v dt = 51.8 mm between t_gate and t_cathode. A uniform drift field gives a
straight line from (t_gate, 0) to (t_cathode, −51.8 mm). A field-cage ring at a wrong potential shows as a change of
slope at its height (rings at z = −10.6, −20.4, −30.2, −40.0 mm).

Data: analysis_SR2026.2/outputs/s2_channels.npz, Cs-137 Δ750 V (28/29-09) photopeak (band from the stbc-i2 edge fit),
single scatters, S1 ≥ 20 PE in top and bottom, gate-corrected S2 width > 450 ns, r < 15 mm; no drift-time cut and no
S1-AFT consistency cut (circular).
Split by y > 0 / y < 0. t_gate 1.15 µs, t_cathode 38.2 µs (drift_time_gate_v0 / drift_time_cathode_v0, Δ750 V).

    python tools/drift_profile.py  ->  results/drift_profile/ (drift_profile.png, summary.json)
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
import step8_fit as S  # noqa: E402

OUT = ROOT / "results" / "drift_profile"
DATA = ROOT.parent / "measurements" / "analysis_SR2026.2" / "outputs" / "s2_channels.npz"
BEST = {"optics.ptfe_in_liquid.reflectivity": 0.95, "optics.ptfe_in_liquid.specular_fraction": 0.1,
        "optics.stainless_steel_reflectivity": 0.2, "optics.lxe.rayleigh_length_cm": 45}
T_GATE, T_CATH, L = 1.15, 38.2, 51.8
RINGS = (-10.625, -20.425, -30.225, -40.025)
RMAX = 15.0
odds = lambda a: a / (1 - a)  # noqa: E731


def sim_curve():
    idx = json.load(open(ROOT / "run" / "scans" / "fit_s1" / "points.json"))
    p = [q for q in idx["points"] if all(abs(q["params"][k] - v) < 1e-9 for k, v in BEST.items())][0]
    rec = S.point_records("fit_s1", p)
    rec = rec[np.isin(rec["sensor"], (0, 1, 2, 3, 4)) & (np.hypot(rec["x0"], rec["y0"]) < RMAX)]
    ze = np.arange(-51.8, 0.01, 1.0)
    zc = 0.5 * (ze[1:] + ze[:-1])
    top = np.isin(rec["sensor"], (1, 2, 3, 4))
    a = np.array([top[(rec["z0"] >= lo) & (rec["z0"] < hi)].mean() for lo, hi in zip(ze[:-1], ze[1:])])
    return zc, a


def invert(a_data, zc, a_sim, eps):
    """z for each measured AFT: interpolate on the ε-scaled simulated curve (monotonic in z)"""
    m = odds(a_sim) * eps
    s = m / (1 + m)
    o = np.argsort(s)
    return np.interp(a_data, s[o], zc[o], left=np.nan, right=np.nan)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    zc, a_sim = sim_curve()
    D = np.load(DATA)
    g = {k: D[f"cs137_{k}"] for k in ("x", "y", "drift_time", "s1_area", "s1_aft_led", "s2_range_50p_area", "cs1")}
    t = g["drift_time"] / 1e3
    r = np.hypot(g["x"], g["y"])
    a1 = g["s1_aft_led"]
    wg = np.sqrt(np.clip(g["s2_range_50p_area"] ** 2 - 3600 * t, 0, None))
    band = np.load(DATA.parent / "aft_maps.npz")["cs_cs1_band"]
    sel = (g["cs1"] > band[0]) & (g["cs1"] < band[1]) & (g["s1_area"] >= 20) & (a1 > 0) & (a1 < 1) & (wg > 450) & (r < RMAX)
    # global fit: z(t) piecewise linear with nodes at 6 equal steps from t_gate to t_cathode (z = 0 and -L fixed),
    # free: 5 inner node depths + ε; model AFT(t) = scaled simulated AFT at z(t); fitted to 1 µs medians of S1 AFT
    from scipy.optimize import least_squares
    tk = np.linspace(T_GATE, T_CATH, 7)
    tb = np.arange(T_GATE + 0.5, T_CATH - 0.49, 1.0)
    tcb = 0.5 * (tb[1:] + tb[:-1])

    def model(par):
        eps, zin = par[0], par[1:]
        zk = np.concatenate([[0.0], zin, [-L]])
        z = np.interp(tcb, tk, zk)
        m = odds(np.interp(z, zc, a_sim)) * eps
        return m / (1 + m), zk

    res = {"t_gate_us": T_GATE, "t_cathode_us": T_CATH, "nominal_mean_velocity_mm_per_us": L / (T_CATH - T_GATE),
           "node_times_us": tk.round(2).tolist(), "ring_heights_mm": list(RINGS)}
    s1 = g["s1_area"]
    big = (g["s1_area"] >= 100) & (g["s1_area"] < 3000) & (a1 > 0) & (a1 < 1) & (wg > 450) & (r < RMAX)
    samples = (("photopeak, all r < 15", sel, "k"), ("photopeak, y > 0", sel & (g["y"] > 0), "C0"),
               ("photopeak, y < 0", sel & (g["y"] < 0), "C3"), ("all Cs S1 100-3000 PE, r < 15", big, "C2"),
               ("all Cs, y > 0", big & (g["y"] > 0), "C9"), ("all Cs, y < 0", big & (g["y"] < 0), "C1"))
    fig, ax = plt.subplots(1, 3, figsize=(18, 5))
    for lab, m, col in samples:
        med = np.array([np.median(a1[m & (t >= a) & (t < b)]) if (m & (t >= a) & (t < b)).sum() >= 30 else np.nan
                        for a, b in zip(tb[:-1], tb[1:])])
        err = np.array([1.2533 * np.std(a1[m & (t >= a) & (t < b)]) / np.sqrt((m & (t >= a) & (t < b)).sum())
                        if (m & (t >= a) & (t < b)).sum() >= 30 else np.nan for a, b in zip(tb[:-1], tb[1:])])
        ok = np.isfinite(med)
        x0 = np.concatenate([[0.3], -L * (tk[1:-1] - T_GATE) / (T_CATH - T_GATE)])
        fit = least_squares(lambda p_: ((model(p_)[0] - med) / err)[ok], x0,
                            bounds=([0.05] + [-L] * 5, [2.0] + [0.0] * 5))
        J = fit.jac
        try:
            cov = np.linalg.inv(J.T @ J)
            perr = np.sqrt(np.diag(cov))
        except np.linalg.LinAlgError:
            perr = np.full(len(fit.x), np.nan)
        zk = np.concatenate([[0.0], fit.x[1:], [-L]])
        zke = np.concatenate([[0.0], perr[1:], [0.0]])
        v = -np.diff(zk) / np.diff(tk)
        ve = np.sqrt(zke[1:] ** 2 + zke[:-1] ** 2) / np.diff(tk)
        chi2 = float(np.sum(fit.fun ** 2))
        res[lab] = dict(n=int(m.sum()), eps_s1=round(float(fit.x[0]), 3), node_z=[round(float(q), 2) for q in zk],
                        node_z_err=[round(float(q), 2) for q in zke], segment_velocity=[round(float(q), 3) for q in v],
                        segment_velocity_err=[round(float(q), 3) for q in ve], chi2=round(chi2, 1), ndf=int(ok.sum() - 6))
        tm = 0.5 * (tk[1:] + tk[:-1])
        ax[0].errorbar(tm, v, ve, fmt="o-", ms=4, lw=0.8, color=col, label=f"{lab} (χ² {chi2:.0f}/{ok.sum() - 6})")
        ax[1].errorbar(tk, zk - (-L * (tk - T_GATE) / (T_CATH - T_GATE)), zke, fmt="o-", ms=4, lw=0.8, color=col, label=lab)
        if lab.startswith("photopeak, all") or lab.startswith("all Cs S1"):
            ax[2].errorbar(tcb, med, err, fmt="o", ms=3, color=col, label=f"{lab}: data")
            ax[2].plot(tcb, model(fit.x)[0], "-", color=col, lw=1)
    ax[0].axhline(L / (T_CATH - T_GATE), color="0.5", lw=0.8, label="uniform field")
    ax[0].set(xlabel="drift time [µs]", ylabel="drift velocity per segment [mm/µs]", title="Drift velocity (6 segments)")
    ax[1].axhline(0, color="0.5", lw=0.8)
    ax[1].set(xlabel="drift time [µs]", ylabel="z − z(uniform) at the nodes [mm]", title="Depth deviation from a uniform field")
    ax[2].set(xlabel="drift time [µs]", ylabel="median S1 AFT (LED gains)", title="Data and fitted model")
    for a in ax:
        a.legend(fontsize=6.5)
    fig.suptitle("Cs-137, Δ750 V, r < 15 mm; z(t) piecewise linear, nodes every 6.2 µs, z(gate) = 0, z(cathode) = −51.8 mm", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "drift_profile.png", dpi=120)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    for lab, _, _ in samples:
        v = res[lab]
        print(f"{lab:32s} n {v['n']:6d} eps {v['eps_s1']:.3f} chi2 {v['chi2']}/{v['ndf']}")
        print("     v  ", v["segment_velocity"], "±", v["segment_velocity_err"])
        print("     z  ", v["node_z"], "±", v["node_z_err"])


if __name__ == "__main__":
    main()
