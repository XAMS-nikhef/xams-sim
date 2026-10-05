#!/usr/bin/env python3
"""Step 8: fit the free optical parameters to the data targets, and test an insensitive cross on the top PMT.

    python tools/step8_fit.py   ->  results/step8/ (summary.json, fit_table.csv, figures)

Data (targets/data_2026-10-05.json, no-source runs, LED gains): S2 area fraction top vs r (S2 3-20 kPE), S1 area
fraction top vs z (S1 > 20 PE), top-array asymmetries u(x), v(y). Simulation: scans fit_s2 / fit_s1 (81 points: PTFE R
x PTFE specular x steel R x Rayleigh length, level 4 mm) binned exactly like the data.
Per grid point two efficiency factors are fitted: eps_S2 and eps_S1 multiply the top/bottom odds AFT/(1-AFT)
(QE ratio top/bottom, times the top-PMT small-signal / load efficiency); the optical parameters are then constrained
by the SHAPES: S2 vs r (r >= 5 mm; the central dip is treated separately), S1 vs z, u(x), v(y).
chi2 uses the simulation statistical error plus a systematic floor per observable (SYS below); absolute chi2 values
depend on that choice, differences between grid points are what matter.
"""
import csv
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

OUT = ROOT / "results" / "step8"
SCANS = ROOT / "run" / "scans"
TOP = np.array([1, 2, 3, 4])
SYS = {"s2r": 0.010, "s1z": 0.004, "uv": 0.010}      # systematic floors (absolute)
PARAMS = ["optics.ptfe_in_liquid.reflectivity", "optics.ptfe_in_liquid.specular_fraction",
          "optics.stainless_steel_reflectivity", "optics.lxe.rayleigh_length_cm"]
SHORT = {PARAMS[0]: "PTFE R", PARAMS[1]: "PTFE specular", PARAMS[2]: "steel R", PARAMS[3]: "Rayleigh [cm]"}


def arr(x):
    return np.array([np.nan if v is None else v for v in x], float)


def point_records(name, p):
    return np.concatenate([read(SCANS / name / q["file"])[0] for q in p["parts"]])


def frac(k, n):
    with np.errstate(invalid="ignore", divide="ignore"):
        f = k / n
        return f, np.sqrt(f * (1 - f) / n)


def bin_s2(rec, ed):
    """S2 observables in the data bins and frame (x_data = -x_sim): AFT vs r, u(x), v(y), each with errors"""
    pm = np.isin(rec["sensor"], np.append(TOP, 0))
    d = rec[pm]
    x, y = -d["x0"], d["y0"]
    r = np.hypot(x, y)
    istop = np.isin(d["sensor"], TOP)
    re = np.asarray(ed["r"])
    kt, _ = np.histogram(r[istop], re)
    n, _ = np.histogram(r, re)
    aft, aft_e = frac(kt, n)
    t = d[istop]
    xt, yt = -t["x0"], t["y0"]
    su = np.where(np.isin(t["sensor"], (1, 3)), 1.0, -1.0)
    sv = np.where(np.isin(t["sensor"], (1, 2)), 1.0, -1.0)
    pe = np.asarray(ed["pos"])
    mu = np.abs(yt) < 3
    mv = np.abs(xt) < 3
    nu, _ = np.histogram(xt[mu], pe)
    nv, _ = np.histogram(yt[mv], pe)
    with np.errstate(invalid="ignore", divide="ignore"):
        u = np.histogram(xt[mu], pe, weights=su[mu])[0] / nu
        v = np.histogram(yt[mv], pe, weights=sv[mv])[0] / nv
    return dict(aft=aft, aft_e=aft_e, u=u, u_e=np.sqrt(np.maximum(1 - u ** 2, 1e-6) / nu), v=v,
                v_e=np.sqrt(np.maximum(1 - v ** 2, 1e-6) / nv))


def bin_s1(rec, ed):
    d = rec[np.isin(rec["sensor"], np.append(TOP, 0)) & (np.hypot(rec["x0"], rec["y0"]) < 25)]
    ze = np.asarray(ed["z"])
    kt, _ = np.histogram(d["z0"][np.isin(d["sensor"], TOP)], ze)
    n, _ = np.histogram(d["z0"], ze)
    aft, aft_e = frac(kt, n)
    return dict(aft=aft, aft_e=aft_e)


def scale(a, eps):
    o = eps * a / (1 - a)
    return o / (1 + o)


def fit_eps(model, err, data, mask):
    """best eps (log grid) for AFT data vs model; returns eps, chi2"""
    best = (1.0, np.inf)
    for e in np.exp(np.linspace(np.log(0.2), np.log(5), 801)):
        c = np.nansum((((scale(model, e) - data) / err) ** 2)[mask])
        if c < best[1]:
            best = (e, c)
    return best


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = json.load(open(ROOT / "targets" / "data_2026-10-05.json"))
    ed, dn = D["edges"], D["none"]
    d_s2r, d_s1z = arr(dn["s2_aft_vs_r_led"]), arr(dn["s1_aft_vs_z_led"])
    d_u, d_v = arr(dn["u_vs_x"]), arr(dn["v_vs_y"])
    rc = 0.5 * (np.asarray(ed["r"])[1:] + np.asarray(ed["r"])[:-1])
    zc = 0.5 * (np.asarray(ed["z"])[1:] + np.asarray(ed["z"])[:-1])
    pc = 0.5 * (np.asarray(ed["pos"])[1:] + np.asarray(ed["pos"])[:-1])
    m_s2r = (rc >= 5) & np.isfinite(d_s2r)
    m_s1z = (zc < -4) & np.isfinite(d_s1z)          # last slice (gate) excluded: events above the gate in the data
    m_u, m_v = np.isfinite(d_u), np.isfinite(d_v)

    idx2 = json.load(open(SCANS / "fit_s2" / "points.json"))["points"]
    idx1 = json.load(open(SCANS / "fit_s1" / "points.json"))["points"]
    key = lambda p: tuple(p["params"][k] for k in PARAMS)  # noqa: E731
    s1_by = {key(p): p for p in idx1}
    rows, store = [], {}
    for i, p in enumerate(idx2):
        k = key(p)
        b2 = bin_s2(point_records("fit_s2", p), ed)
        b1 = bin_s1(point_records("fit_s1", s1_by[k]), ed)
        e2 = np.hypot(b2["aft_e"], SYS["s2r"])
        eps2, c2 = fit_eps(b2["aft"], e2, d_s2r, m_s2r)
        e1 = np.hypot(b1["aft_e"], SYS["s1z"])
        eps1, c1 = fit_eps(b1["aft"], e1, d_s1z, m_s1z)
        cu = np.nansum((((b2["u"] - d_u) / np.hypot(b2["u_e"], SYS["uv"])) ** 2)[m_u])
        cv = np.nansum((((b2["v"] - d_v) / np.hypot(b2["v_e"], SYS["uv"])) ** 2)[m_v])
        rows.append(dict(zip([SHORT[q] for q in PARAMS], k), eps_s2=eps2, eps_s1=eps1, chi2_s2r=c2, chi2_s1z=c1,
                         chi2_uv=cu + cv, chi2=c2 + c1 + cu + cv))
        store[k] = (b2, b1, eps2, eps1)
        print(f"{i + 1}/{len(idx2)} {k} eps_S2 {eps2:.3f} eps_S1 {eps1:.3f} chi2 {c2:.1f} {c1:.1f} {cu + cv:.1f}", flush=True)
    ndf = dict(s2r=int(m_s2r.sum()) - 1, s1z=int(m_s1z.sum()) - 1, uv=int(m_u.sum() + m_v.sum()))
    rows.sort(key=lambda r: r["chi2"])
    with open(OUT / "fit_table.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    best = rows[0]
    bk = tuple(best[SHORT[q]] for q in PARAMS)
    b2, b1, eps2, eps1 = store[bk]

    # profiles: minimum chi2 over the other parameters, per value of each parameter (total and per observable)
    prof = {}
    for q in PARAMS:
        prof[SHORT[q]] = {str(v): {c: min(r[c] for r in rows if r[SHORT[q]] == v) for c in ("chi2", "chi2_s2r", "chi2_s1z", "chi2_uv")}
                          for v in sorted({r[SHORT[q]] for r in rows})}

    # figure 1: best fit vs data
    fig, ax = plt.subplots(2, 2, figsize=(11, 8))
    a = ax[0, 0]
    a.errorbar(rc, scale(b2["aft"], eps2), b2["aft_e"], fmt="o-", color="C0", label=f"simulation × ε_S2 = {eps2:.2f}")
    a.plot(rc, d_s2r, "ks-", label="data, no source (3–20 kPE)")
    a.axvspan(0, 5, color="0.9", label="not in the fit (central dip)")
    a.set(xlabel="r [mm]", ylabel="S2 area fraction top", title="S2 vs r")
    a.legend(fontsize=7)
    a = ax[0, 1]
    a.errorbar(zc, scale(b1["aft"], eps1), b1["aft_e"], fmt="o-", color="C0", label=f"simulation × ε_S1 = {eps1:.2f}")
    a.plot(zc, d_s1z, "ks-", label="data, no source (S1 > 20 PE)")
    a.set(xlabel="z [mm]", ylabel="S1 area fraction top", title="S1 vs z")
    a.legend(fontsize=7)
    a = ax[1, 0]
    a.plot(pc, b2["u"], "o-", color="C0", ms=3, label="simulation u(x)")
    a.plot(pc, d_u, "ks-", ms=3, label="data u(x)")
    a.plot(pc, b2["v"], "o--", color="C2", ms=3, label="simulation v(y)")
    a.plot(pc, d_v, "k^--", ms=3, label="data v(y)")
    a.set(xlabel="position [mm]", ylabel="asymmetry", title="top-sector pattern")
    a.legend(fontsize=7)
    a = ax[1, 1]
    for j, q in enumerate(PARAMS):
        vs = sorted(prof[SHORT[q]], key=float)
        cmin = min(r["chi2"] for r in rows)
        a.plot(range(len(vs)), [prof[SHORT[q]][v]["chi2"] - cmin for v in vs], "o-", label=f"{SHORT[q]}: {', '.join(vs)}")
    a.set(xlabel="grid value (low → high)", ylabel="Δχ² (profiled)", title="profiles", xticks=[0, 1, 2])
    a.legend(fontsize=7)
    fig.suptitle("Step 8: best grid point " + ", ".join(f"{SHORT[q]} {v}" for q, v in zip(PARAMS, bk)), fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "best_fit.png", dpi=130)

    # dead cross
    dc = {}
    dcd = json.load(open(SCANS / "deadcross_s2" / "points.json"))["points"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for p in sorted(dcd, key=lambda p: p["params"]["pmt_common.top_dead_cross_mm"]):
        wv = p["params"]["pmt_common.top_dead_cross_mm"]
        b = bin_s2(point_records("deadcross_s2", p), ed)
        e = np.hypot(b["aft_e"], SYS["s2r"])
        eps, c = fit_eps(b["aft"], e, d_s2r, m_s2r)
        model = scale(b["aft"], eps)
        cu = np.nansum((((b["u"] - d_u) / np.hypot(b["u_e"], SYS["uv"])) ** 2)[m_u])
        cv = np.nansum((((b["v"] - d_v) / np.hypot(b["v_e"], SYS["uv"])) ** 2)[m_v])
        dc[str(wv)] = dict(eps=eps, aft_r=model.tolist(), centre_over_ring=float(model[:2].mean() / model[3:6].mean()),
                           chi2_s2r=c, chi2_uv=cu + cv)
        ax[0].plot(rc, model, "o-", ms=3, label=f"dead cross {wv} mm")
        ax[1].plot(pc, b["u"], "-", label=f"u(x), {wv} mm")
    ax[0].plot(rc, d_s2r, "ks-", label="data, no source")
    ax[0].set(xlabel="r [mm]", ylabel="S2 area fraction top", title="S2 vs r (each scaled with its ε_S2)")
    ax[0].legend(fontsize=7)
    ax[1].plot(pc, d_u, "ks", ms=3, label="data")
    ax[1].set(xlabel="x [mm]", ylabel="u", title="u(x) near the centre", xlim=(-12, 12), ylim=(-0.6, 0.6))
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "dead_cross.png", dpi=130)
    data_ratio = float(np.nanmean(d_s2r[:2]) / np.nanmean(d_s2r[3:6]))

    summary = dict(sys_floors=SYS, ndf=ndf, best=best, top5=rows[:5], profiles=prof,
                   eps_range_good=dict(s2=[min(r["eps_s2"] for r in rows[:10]), max(r["eps_s2"] for r in rows[:10])],
                                       s1=[min(r["eps_s1"] for r in rows[:10]), max(r["eps_s1"] for r in rows[:10])]),
                   dead_cross=dc, data_centre_over_ring=data_ratio)
    json.dump(summary, open(OUT / "summary.json", "w"), indent=1, default=float)
    print(json.dumps({k: summary[k] for k in ("ndf", "best", "eps_range_good", "data_centre_over_ring")}, indent=1, default=float))
    print(json.dumps(dc, default=float)[:1500])


if __name__ == "__main__":
    main()
