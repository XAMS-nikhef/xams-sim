#!/usr/bin/env python3
"""2D maps of the S2 area fraction top (AFT): simulation vs data (follow-up of the central dip, step 7/8).

Simulation: AFT versus the generated S2 position, from the photon records of the 81 fit_s2 points (geometry v4,
pooled: ~6e7 detected photons), data frame x_data = -x_sim, same 1.5 mm grid as the data.
Data: analysis_SR2026.2/outputs/aft_maps.npz (studies/aft_maps.py on stbc-i2, read-only, central v4): no-source AFT
per S2 size class on x-y and on the raw asymmetries u-v, event counts, and the Cs-137 photopeak cS2 yield map.

    python tools/aft_maps.py  ->  results/aft_maps/ (aft_maps.png, yield_map.png, summary.json; sim cache sim_xy.npz)
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
from read_output import read  # noqa: E402

OUT = ROOT / "results" / "aft_maps"
DATA = ROOT.parent / "notebooks" / "analysis_SR2026.2" / "outputs" / "aft_maps.npz"
TOP = (1, 2, 3, 4)


def sim_maps(edges):
    cache = OUT / "sim_xy.npz"
    if cache.exists():
        c = np.load(cache)
        if np.array_equal(c["edges"], edges):
            return c["top"], c["bot"], c["u"], c["v"]
    idx = json.load(open(ROOT / "run" / "scans" / "fit_s2" / "points.json"))
    n = len(edges) - 1
    T, B, U, V = (np.zeros((n, n)) for _ in range(4))
    for p in idx["points"]:
        for q in p["parts"]:
            rec = read(ROOT / "run" / "scans" / "fit_s2" / q["file"])[0]
            x, y, s = -rec["x0"], rec["y0"], rec["sensor"]
            t = np.isin(s, TOP)
            T += np.histogram2d(x[t], y[t], bins=[edges, edges])[0]
            B += np.histogram2d(x[s == 0], y[s == 0], bins=[edges, edges])[0]
            # sector weights for the expected raw asymmetries (data u along +x: ch1/ch3 positive)
            wu = np.where(np.isin(s, (1, 3)), 1.0, -1.0)
            wv = np.where(np.isin(s, (1, 2)), 1.0, -1.0)
            U += np.histogram2d(x[t], y[t], bins=[edges, edges], weights=wu[t])[0]
            V += np.histogram2d(x[t], y[t], bins=[edges, edges], weights=wv[t])[0]
    np.savez(cache, edges=edges, top=T, bot=B, u=U, v=V)
    return T, B, U, V


def grid_median(a, b, val, ea, eb, nmin=10):
    ia, ib = np.digitize(a, ea) - 1, np.digitize(b, eb) - 1
    na, nb = len(ea) - 1, len(eb) - 1
    ok = (ia >= 0) & (ia < na) & (ib >= 0) & (ib < nb)
    key = ia[ok] * nb + ib[ok]
    v = val[ok]
    o = np.argsort(key, kind="stable")
    key, v = key[o], v[o]
    med = np.full(na * nb, np.nan)
    cnt = np.bincount(key, minlength=na * nb)
    st = np.concatenate([[0], np.cumsum(cnt)])
    for k in np.nonzero(cnt >= nmin)[0]:
        med[k] = np.median(v[st[k]:st[k + 1]])
    return med.reshape(na, nb), cnt.reshape(na, nb)


def show(ax, m, edges, title, cmap="viridis", vmin=None, vmax=None, label="", circle=25):
    im = ax.pcolormesh(edges, edges, m.T, cmap=cmap, vmin=vmin, vmax=vmax, shading="flat")
    if circle:
        ph = np.linspace(0, 2 * np.pi, 200)
        ax.plot(circle * np.cos(ph), circle * np.sin(ph), "w--", lw=0.6)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=9)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.03, label=label)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = np.load(DATA)
    sizes = D["sizes"]
    xy = np.arange(-27.5, 27.6, 2.5)              # re-binned from the event arrays (1.5 mm too sparse for small S2s)
    uv = np.linspace(-1, 1, 26)
    ev = {k[6:]: D[k] for k in D.files if k.startswith("bg_ev_")}
    ev_aft = ev["top"] / (ev["top"] + ev["bot"])
    cs = {k[6:]: D[k] for k in D.files if k.startswith("cs_ev_")}
    T, B, U, V = sim_maps(xy)
    with np.errstate(invalid="ignore", divide="ignore"):
        sim_aft = T / (T + B)
        sim_aft[(T + B) < 2000] = np.nan
    xc = 0.5 * (xy[1:] + xy[:-1])
    R = np.hypot(*np.meshgrid(xc, xc, indexing="ij"))
    ring = (R > 7.5) & (R < 12.5)
    centre = R < 2.5
    odds = lambda a: a / (1 - a)  # noqa: E731
    summary = dict(sim_centre_over_ring=float(np.nanmean(sim_aft[centre]) / np.nanmean(sim_aft[ring])), classes={})

    ns = len(sizes)
    fig, ax = plt.subplots(ns, 4, figsize=(18, 4.2 * ns))
    for k, (lo, hi) in enumerate(sizes):
        m = (ev["s2"] >= lo) & (ev["s2"] < hi)
        a, n = grid_median(ev["x"][m], ev["y"][m], ev_aft[m], xy, xy)
        auv, _ = grid_median(ev["u"][m], ev["v"][m], ev_aft[m], uv, uv)
        eps = np.nanmedian(odds(a)[ring] / odds(sim_aft)[ring])          # top/bottom scale in the ring
        ratio = odds(a) / (eps * odds(sim_aft))
        lab = f"{lo / 1e3:.0f}–{hi / 1e3:.0f} kPE"
        show(ax[k, 0], a, xy, f"data AFT(x, y), no source, {lab}", vmin=0.35, vmax=0.85, label="AFT")
        show(ax[k, 1], n, xy, f"events per 2.5 mm cell, {lab}", cmap="magma", label="events")
        show(ax[k, 2], ratio, xy, f"data / sim top-bottom ratio (÷ ε = {eps:.2f})", cmap="RdBu_r", vmin=0.6, vmax=1.4,
             label="ratio")
        show(ax[k, 3], auv, uv, f"data AFT(u, v) raw asymmetries, {lab}", vmin=0.35, vmax=0.85, label="AFT", circle=0)
        ax[k, 3].set(xlabel="u", ylabel="v")
        for j in range(3):
            ax[k, j].set(xlabel="x [mm]", ylabel="y [mm]")
        cuv = 0.5 * (uv[1:] + uv[:-1])
        RU = np.hypot(*np.meshgrid(cuv, cuv, indexing="ij"))
        summary["classes"][lab] = dict(
            eps=float(eps), n=int(n.sum()),
            centre_over_ring=float(np.nanmean(a[centre]) / np.nanmean(a[ring])),
            ratio_centre=float(np.nanmean(ratio[centre])),
            ratio_rms_r_lt_22=float(np.nanstd(ratio[R < 22])),
            density_centre_over_ring=float(n[centre].mean() / n[ring].mean()),
            aft_uv_centre=float(np.nanmean(auv[RU < 0.06])), aft_uv_ring=float(np.nanmean(auv[(RU > 0.2) & (RU < 0.4)])))
    fig.tight_layout()
    fig.savefig(OUT / "aft_maps.png", dpi=110)

    # simulation map alone + Cs yield maps
    fig, ax = plt.subplots(1, 4, figsize=(18, 4.4))
    show(ax[0], sim_aft, xy, "simulation AFT(x, y) (81 fit points pooled)", vmin=0.5, vmax=0.68, label="AFT")
    cs2_ev = cs["ctop"] + cs["cbot"]
    cs_aft_map, cs_n = grid_median(cs["x"], cs["y"], cs["ctop"] / cs2_ev, xy, xy)
    cs, _ = grid_median(cs["x"], cs["y"], cs2_ev, xy, xy)
    ref = np.nanmedian(cs[ring])
    show(ax[1], cs / ref, xy, "Cs-137 photopeak: cS2 ÷ ring (7.5–12.5 mm)", cmap="RdBu_r", vmin=0.6, vmax=1.4, label="rel. yield")
    show(ax[2], cs_aft_map, xy, "Cs-137 photopeak: AFT(x, y)", vmin=0.2, vmax=0.4, label="AFT")
    show(ax[3], cs_n, xy, "Cs-137 photopeak: events per cell", cmap="magma", label="events")
    for a_ in ax:
        a_.set(xlabel="x [mm]", ylabel="y [mm]")
    fig.tight_layout()
    fig.savefig(OUT / "yield_map.png", dpi=110)
    summary["cs_yield_centre_over_ring"] = float(np.nanmean(cs[centre]) / ref)
    summary["cs_yield_quadrants"] = {q: float(np.nanmedian((cs / ref)[m & (R < 22)])) for q, m in (
        ("x>0,y>0", (xc[:, None] > 0) & (xc[None, :] > 0)), ("x<0,y>0", (xc[:, None] < 0) & (xc[None, :] > 0)),
        ("x<0,y<0", (xc[:, None] < 0) & (xc[None, :] < 0)), ("x>0,y<0", (xc[:, None] > 0) & (xc[None, :] < 0)))}
    # event density and AFT versus r per size class (+ Cs photopeak)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.4))
    re_ = np.arange(0, 25.1, 1.25)
    rc = 0.5 * (re_[1:] + re_[:-1])
    area = np.pi * (re_[1:] ** 2 - re_[:-1] ** 2)
    rev = np.hypot(ev["x"], ev["y"])
    summary["density_vs_r"] = {}
    for k, (lo, hi) in enumerate(sizes):
        m = (ev["s2"] >= lo) & (ev["s2"] < hi)
        h = np.histogram(rev[m], re_)[0] / area
        h = h / np.mean(h[(rc > 7.5) & (rc < 12.5)])
        lab = f"{lo / 1e3:.0f}–{hi / 1e3:.0f} kPE"
        ax[0].plot(rc, h, "o-", ms=3, label=f"no source {lab}")
        summary["density_vs_r"][lab] = h.round(3).tolist()
    rcs = np.hypot(cs_x := D["cs_ev_x"], D["cs_ev_y"])
    h = np.histogram(rcs, re_)[0] / area
    ax[0].plot(rc, h / np.mean(h[(rc > 7.5) & (rc < 12.5)]), "k^--", ms=3, label="Cs-137 photopeak")
    ax[0].set(xlabel="r [mm] (v4 position)", ylabel="events per mm² ÷ ring 7.5–12.5 mm", yscale="log",
              title="event density versus r")
    ax[0].legend(fontsize=7)
    for k, (lo, hi) in enumerate(sizes):
        m = (ev["s2"] >= lo) & (ev["s2"] < hi)
        med = [np.median(ev_aft[m & (rev >= a_) & (rev < b_)]) if (m & (rev >= a_) & (rev < b_)).sum() > 15 else np.nan
               for a_, b_ in zip(re_[:-1], re_[1:])]
        ax[1].plot(rc, med, "o-", ms=3, label=f"{lo / 1e3:.0f}–{hi / 1e3:.0f} kPE")
    ax[1].set(xlabel="r [mm]", ylabel="median AFT (LED gains)", title="AFT versus r, no source, single scatters")
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "density_vs_r.png", dpi=120)
    json.dump(summary, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
