#!/usr/bin/env python3
"""Plot one mesh cell (gate or cathode) from the COMSOL log of run_cell.sh: plane through the hole centre and across a
bar, mirrored over three cells. |E| (log colour scale), equipotentials, and electron drift lines (along -E) started
on a fine row of points far from the foil; a line ends on a bar (red) or passes the foil (white). For the cathode, lines
are started both above (drift region) and below (reverse region).

    python efield/comsol/plot_cell.py gate|cathode  ->  results/efield/comsol/cell_<electrode>_<case>.png, cell_<electrode>.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402
from scipy.interpolate import RegularGridInterpolator  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "efield" / "comsol" / "build"
OUT = ROOT / "results" / "efield" / "comsol"


def unfold(x, h):
    """map any x to the quarter-cell coordinate [0, h] and the sign of E_x there"""
    p = 2 * h
    u = np.mod(x, p)
    s = 1.0
    if u > h:
        u, s = p - u, -1.0
    return u, s


def main():
    el = sys.argv[1]
    meta = yaml.safe_load(open(BUILD / f"XAMS_cell_{el}.yaml"))
    h, w, t = meta["half_pitch"], meta["bar_width"], meta["foil_thickness"]
    rows = defaultdict(list)
    for line in open(BUILD / f"cell_{el}.log"):
        if line.startswith("MAP "):
            q = line.split()
            rows[q[1]].append([float(v) for v in q[2:]])
    summary = {}
    for n, rr in rows.items():
        a = np.array(rr)
        x, z = np.unique(a[:, 0].round(5)), np.unique(a[:, 1].round(5))
        V, Ex, Ez = (a[:, k].reshape(len(x), len(z)) for k in (2, 3, 4))
        fx = RegularGridInterpolator((x, z), np.nan_to_num(Ex), bounds_error=False, fill_value=0.0)
        fz = RegularGridInterpolator((x, z), np.nan_to_num(Ez), bounds_error=False, fill_value=0.0)
        bar = np.isnan(V)

        za, ax0 = meta.get("anode_z", 8.0), meta.get("anode_offset_x", 0.0)

        def on_bar(xx, zz):
            u, _ = unfold(xx, h)
            if abs(zz) < t / 2 and u > h - w / 2:
                return True
            if meta.get("stack") and abs(zz - za) < t / 2:
                return u < w / 2 if ax0 else u > h - w / 2     # anode bar centres at x = 0 (shifted) or x = h (aligned), mod pitch
            return False

        def drift(x0, z0, zstop_hi, zstop_lo, step=0.004, nmax=20000):
            P = [(x0, z0)]
            xx, zz = x0, z0
            for _ in range(nmax):
                u, s = unfold(xx, h)
                ex, ez = s * float(fx((u, zz))), float(fz((u, zz)))
                nn = np.hypot(ex, ez)
                if nn == 0:
                    return np.array(P), "stuck"
                xx, zz = xx - step * ex / nn, zz - step * ez / nn
                P.append((xx, zz))
                if on_bar(xx, zz):
                    if meta.get("stack") and zz > za / 2:
                        return np.array(P), ("anode_from_above" if P[-2][1] > za else "anode_from_below")
                    return np.array(P), "bar"
                if zz >= zstop_hi:
                    return np.array(P), "up"
                if zz <= zstop_lo:
                    return np.array(P), "down"
            return np.array(P), "max"

        # mirrored picture over 3 cells: x from -3h to 3h (hole centres at 0, +-2h)
        X = np.concatenate([-x[::-1], x[1:]])
        Xf = np.concatenate([X - 2 * h, X[1:] + 0, X[1:] + 2 * h])
        Xf = np.unique(np.concatenate([X - 2 * h, X, X + 2 * h]))
        Ef = np.empty((len(Xf), len(z)))
        Vf = np.empty((len(Xf), len(z)))
        for i, xx in enumerate(Xf):
            u, _ = unfold(xx, h)
            k = int(round(u / 0.01))
            k = min(k, len(x) - 1)
            Ef[i] = np.hypot(Ex[k], Ez[k]) / 100
            Vf[i] = V[k]
        c = meta["cases"][n]
        fig, ax = plt.subplots(1, 2, figsize=(15, 7.5), gridspec_kw={"width_ratios": [1, 1]})
        res = {}
        for k, a_ in enumerate(ax):
            zl = (meta["z0"], meta["z1"]) if k == 0 else ((meta.get("anode_z", 8) - 1.5, meta.get("anode_z", 8) + 1.5) if meta.get("stack") else (-0.6, 0.6))
            im = a_.pcolormesh(Xf, z, np.ma.masked_invalid(Ef).T, cmap="viridis", shading="auto",
                               norm=LogNorm(vmin=max(np.nanmin(Ef[Ef > 0]), 10), vmax=np.nanmax(Ef)))
            lev = np.linspace(np.nanmin(Vf), np.nanmax(Vf), 60 if k == 0 else 160)
            a_.contour(Xf, z, Vf.T, levels=lev, colors="w", linewidths=0.3, alpha=0.6)
            plt.colorbar(im, ax=a_, fraction=0.035, pad=0.02, label="|E| [V/cm]")
            for cx in (-2 * h, 0, 2 * h):
                for sx in (-1, 1):
                    a_.add_patch(plt.Rectangle((cx + sx * h - w / 2, -t / 2), w, t, fc="0.6", ec="k", lw=0.4))
            if meta.get("stack"):
                for cxa in np.arange(-4 * h, 4.01 * h, 2 * h) + (0.0 if ax0 else h):
                    a_.add_patch(plt.Rectangle((cxa - w / 2, za - t / 2), w, t, fc="gold", ec="k", lw=0.4))
            if meta.get("stack"):
                a_.axhline(meta["level"], color="c", lw=0.8, ls="--")
                starts = [(x0, -3.5) for x0 in np.linspace(-3 * h, 3 * h, 61)]
                ends_hi, ends_lo = (meta["z1"] - 0.05, meta["z0"])
            elif el == "gate":
                a_.axhline(meta["level"], color="c", lw=0.8, ls="--")
                starts = [(x0, -3.5 if k == 0 else -0.55) for x0 in np.linspace(-3 * h, 3 * h, 61)]
                ends_hi, ends_lo = (meta["z1"] - 0.05, meta["z0"]) if k == 0 else (0.55, -0.6)
            else:
                starts = [(x0, 3.5 if k == 0 else 0.55) for x0 in np.linspace(-3 * h, 3 * h, 41)]
                starts += [(x0, -3.5 if k == 0 else -0.55) for x0 in np.linspace(-3 * h, 3 * h, 41)]
                ends_hi, ends_lo = (meta["z1"], meta["z0"]) if k == 0 else (0.6, -0.6)
            cnt = defaultdict(int)
            gas_len, el_ph = [], []
            for (x0, z0_) in starts:
                P, end = drift(x0, z0_, ends_hi, ends_lo, step=0.004 if not meta.get("stack") else 0.006, nmax=20000 if not meta.get("stack") else 60000)
                cnt[f"{'above' if z0_ > 0 else 'below'}->{end}"] += 1
                colr = {"bar": "r", "anode_from_above": "orange", "anode_from_below": "w"}.get(end, "w")
                a_.plot(P[:, 0], P[:, 1], "-", color=colr, lw=0.6)
                if meta.get("stack") and k == 0:
                    g_ = P[:, 1] > meta["level"]
                    dl = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))[g_[1:]] / 10          # cm
                    gas_len.append(float(dl.sum()) * 10)
                    # electroluminescence: photons/cm = 140 E[kV/cm] - 116 p[bar] (Monteiro et al.), p = 2 bar assumed
                    Eg = np.array([np.hypot(*(lambda u_s: (u_s[1] * float(fx((u_s[0], zq))), float(fz((u_s[0], zq)))))(unfold(xq, h)))
                                   for xq, zq in P[1:][g_[1:]]]) / 1e5                    # kV/cm
                    el_ph.append(float(np.sum(np.clip(140 * Eg - 116 * 2.0, 0, None) * dl)))
            if gas_len:
                res["gas_path_mm"] = {"median": round(float(np.median(gas_len)), 3), "min": round(min(gas_len), 3),
                                      "max": round(max(gas_len), 3), "rms_over_mean": round(float(np.std(gas_len) / np.mean(gas_len)), 4)}
                res["el_photons_per_electron_p2bar"] = {"mean": round(float(np.mean(el_ph)), 1), "rms_over_mean": round(float(np.std(el_ph) / np.mean(el_ph)), 4)}
            res["full" if k == 0 else "zoom"] = dict(cnt)
            a_.set(xlim=(-3 * h, 3 * h), ylim=zl, xlabel="x [mm] (plane through the hole centres, across the bars)", ylabel="z [mm] (0 = foil)")
            if k == 1:
                a_.set_aspect("equal")
        ttl = (f"gate + anode cell (anode {'shifted by half a pitch in x' if meta.get('anode_offset_x') else 'aligned with the gate'}): "
               "liquid surface (cyan) at +4 mm, top screen at +18 mm; white = ends on the anode from below, orange = passes an anode hole and "
               "lands on the anode from above") if meta.get("stack") else ("gate cell: drift region below, liquid surface (cyan) at +%.0f mm, anode plane at +8 mm" % meta["level"]) if el == "gate" \
            else "cathode cell: drift region above, reverse field down to the bottom screen at −7.8 mm"
        if meta.get("stack"):
            fig.suptitle(f"{n}: {c['note']} — gate {c['Vel']:.0f} V, anode {c['Va']:.0f} V, top screen {c['Vtop']:.0f} V\n"
                         f"anode {'shifted by half a pitch in x' if meta.get('anode_offset_x') else 'aligned with the gate'}; liquid surface (cyan) at +4 mm; "
                         "drift lines: white = land on the anode from below, orange = pass an anode hole and land on it from above", fontsize=10)
        else:
            fig.suptitle(f"{n}: {c['note']} — V_bottom {c['Vbot']:.0f} V, {el} {c['Vel']:.0f} V, V_top {c['Vtop']:.0f} V\n{ttl}; "
                         "electron drift lines: white = pass, red = end on a bar", fontsize=10)
        fig.tight_layout()
        fig.savefig(OUT / f"cell_{el}_{n}.png", dpi=125)
        plt.close(fig)
        Ed_below = float(np.nanmedian(np.hypot(Ex[:, 5], Ez[:, 5]))) / 100
        Ed_above = float(np.nanmedian(np.hypot(Ex[:, -5], Ez[:, -5]))) / 100
        summary[n] = {"note": c["note"], "E_far_below_V_cm": round(Ed_below, 1), "E_far_above_V_cm": round(Ed_above, 1),
                      "E_max_V_cm": round(float(np.nanmax(np.hypot(Ex, Ez))) / 100, 0), "drift_line_ends": res}
        print(n, json.dumps(summary[n]))
    json.dump(summary, open(OUT / f"cell_{el}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
