#!/usr/bin/env python3
"""Interactive 3D view (plotly, HTML) of electron drift lines through an etched mesh (gate or cathode), from the M3 lines
that run_cell.sh writes with --map3d (quarter-cell field near the foil, mirrored to 3 x 3 cells; outside z +-2.5 mm the
field is taken as uniform). Mesh bars are drawn as grey blocks. Drift lines (electrons along -E) start on a regular grid:
  gate:    below the gate (z = -2.4 mm), coloured by the depth they reach -> all pass the holes (white/blue) or end on a bar (red)
  cathode: two layers above the cathode (z = +0.6 and +1.8 mm): lines that go up into the drift region (blue) and lines
           that are pulled down through the holes into the reverse region (red = lost for S2)

    python efield/comsol/plot_cell3d.py gate|cathode [case ...]  ->  results/efield/comsol/cell3d_<electrode>_<case>.html
"""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import yaml
from scipy.interpolate import RegularGridInterpolator

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "efield" / "comsol" / "build"
OUT = ROOT / "results" / "efield" / "comsol"


def fold(x, h):
    u = np.mod(x, 2 * h)
    return (2 * h - u, -1.0) if u > h else (u, 1.0)


def box_mesh(x0, x1, y0, y1, z0, z1):
    X = [x0, x1, x1, x0, x0, x1, x1, x0]
    Y = [y0, y0, y1, y1, y0, y0, y1, y1]
    Z = [z0, z0, z0, z0, z1, z1, z1, z1]
    i = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
    j = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4]
    k = [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7]
    return X, Y, Z, i, j, k


def main():
    el = sys.argv[1]
    meta = yaml.safe_load(open(BUILD / f"XAMS_cell_{el}.yaml"))
    h, w, t = meta["half_pitch"], meta["bar_width"], meta["foil_thickness"]
    data = defaultdict(list)
    for line in open(BUILD / f"cell_{el}.log"):
        if line.startswith("M3 "):
            q = line.split()
            data[q[1]].append([float(v) for v in q[2:]])
    names = sys.argv[2:] or list(data)
    for n in names:
        a = np.array(data[n])
        xs, ys, zs = (np.unique(a[:, k].round(5)) for k in range(3))
        sh = (len(xs), len(ys), len(zs))
        F = [RegularGridInterpolator((xs, ys, zs), np.nan_to_num(a[:, 3 + k].reshape(sh)), bounds_error=False, fill_value=None)
             for k in range(3)]
        Ebot = np.array([np.nanmean(a[:, 3 + k].reshape(sh)[:, :, 0]) for k in range(3)])
        Etop = np.array([np.nanmean(a[:, 3 + k].reshape(sh)[:, :, -1]) for k in range(3)])

        def field(x, y, z):
            if z <= zs[0]:
                return Ebot
            if z >= zs[-1]:
                return Etop
            u, sx = fold(x, h)
            v, sy = fold(y, h)
            p = (min(u, xs[-1]), min(v, ys[-1]), z)
            return np.array([sx * float(F[0](p)), sy * float(F[1](p)), float(F[2](p))])

        stack, za, ax0 = meta.get("stack"), meta.get("anode_z", 8.0), meta.get("anode_offset_x", 0.0)

        def on_bar(x, y, z):
            if abs(z) < t / 2 and (fold(x, h)[0] > h - w / 2 or fold(y, h)[0] > h - w / 2):
                return "gate"
            if stack and abs(z - za) < t / 2:
                ux = fold(x, h)[0]
                if (ux < w / 2 if ax0 else ux > h - w / 2) or fold(y, h)[0] > h - w / 2:
                    return "anode"
            return None

        def drift(p0, zlo, zhi, step=0.006, nmax=12000):
            P = [p0]
            p = np.array(p0, float)
            for _ in range(nmax):
                E = field(*p)
                nn = np.linalg.norm(E)
                if nn == 0:
                    return np.array(P), "stuck"
                p = p - step * E / nn
                P.append(p.copy())
                hit = on_bar(*p)
                if hit == "anode":
                    return np.array(P), ("anode_from_above" if P[-1][2] > za else "anode_from_below")
                if hit:
                    return np.array(P), "bar"
                if p[2] >= zhi:
                    return np.array(P), "up"
                if p[2] <= zlo:
                    return np.array(P), "down"
            return np.array(P), "max"

        fig = go.Figure()
        R = 3 * h
        for cx in (-2 * h, 0, 2 * h, ):
            pass
        # bars: lines along y at x = +-h, +-3h and along x at y = +-h, +-3h (only within |x|,|y| <= 3h)
        for c in (-3 * h, -h, h, 3 * h):
            for X, Y, Z, i, j, k in (box_mesh(c - w / 2, c + w / 2, -R, R, -t / 2, t / 2), box_mesh(-R, R, c - w / 2, c + w / 2, -t / 2, t / 2)):
                fig.add_trace(go.Mesh3d(x=X, y=Y, z=Z, i=i, j=j, k=k, color="silver", opacity=1.0, flatshading=True,
                                        showlegend=False, hoverinfo="skip"))
        cnt = defaultdict(int)
        if stack:
            for cx in (-4 * h, -2 * h, 0, 2 * h, 4 * h):
                ca = cx + (0.0 if ax0 else h)   # shifted anode: bar centres at x = 0 (mod pitch)
                if abs(ca) <= R:
                    X, Y, Z, i, j, k = box_mesh(ca - w / 2, ca + w / 2, -R, R, za - t / 2, za + t / 2)
                    fig.add_trace(go.Mesh3d(x=X, y=Y, z=Z, i=i, j=j, k=k, color="gold", opacity=1.0, flatshading=True, showlegend=False, hoverinfo="skip"))
            for c in (-3 * h, -h, h, 3 * h):
                X, Y, Z, i, j, k = box_mesh(-R, R, c - w / 2, c + w / 2, za - t / 2, za + t / 2)
                fig.add_trace(go.Mesh3d(x=X, y=Y, z=Z, i=i, j=j, k=k, color="gold", opacity=1.0, flatshading=True, showlegend=False, hoverinfo="skip"))
            starts = [(x, y, -2.4) for x in np.linspace(-2.6, 2.6, 13) for y in np.linspace(-2.6, 2.6, 13)]
            zlo, zhi = -2.5, za + 3.0
        elif el == "gate":
            starts = [(x, y, -2.4) for x in np.linspace(-2.6, 2.6, 21) for y in np.linspace(-2.6, 2.6, 21)]
            zlo, zhi = -2.5, 2.4
        else:
            starts = [(x, y, z) for z in (0.6, 1.8) for x in np.linspace(-2.6, 2.6, 15) for y in np.linspace(-2.6, 2.6, 15)]
            zlo, zhi = -2.4, 2.4
        col = {"up": "royalblue", "down": "crimson", "bar": "crimson", "stuck": "orange", "max": "orange",
               "anode_from_below": "deepskyblue", "anode_from_above": "orange"}
        groups = defaultdict(lambda: ([], [], []))
        for s in starts:
            P, end = drift(s, zlo, zhi)
            key = end if (el == "cathode" or stack) else ("bar" if end == "bar" else "up")
            cnt[f"z0={s[2]:+.1f} -> {end}"] += 1
            gx, gy, gz = groups[key]
            gx += list(P[:, 0]) + [None]
            gy += list(P[:, 1]) + [None]
            gz += list(P[:, 2]) + [None]
        label = {"up": "electrons drifting up (to the gas gap / into the drift region)", "down": "pulled down through the holes (lost)",
                 "bar": "ending on a gate bar", "stuck": "stuck in a zero-field point", "max": "not finished",
                 "anode_from_below": "landing on the anode from below", "anode_from_above": "through an anode hole, landing on the anode from above"}
        for key, (gx, gy, gz) in groups.items():
            fig.add_trace(go.Scatter3d(x=gx, y=gy, z=gz, mode="lines", line=dict(color=col[key], width=2.5), name=label[key]))
        c = meta["cases"][n]
        ttl = (f"gate + anode ({'anode shifted half a pitch in x' if ax0 else 'anode aligned with the gate'}), {n}: gate {c['Vel']:.0f} V, anode {c['Va']:.0f} V; liquid surface at +4 mm") if stack else (f"{el} mesh, {n}: {c['note']} — {el} {c['Vel']:.0f} V; "
               + ("drift region below, extraction above" if el == "gate" else "drift region above, reverse field below"))
        fig.update_layout(title=ttl, scene=dict(xaxis_title="x [mm]", yaxis_title="y [mm]", zaxis_title="z [mm] (0 = foil)",
                                                aspectmode="data", bgcolor="rgb(25,25,35)"),
                          paper_bgcolor="white", legend=dict(x=0, y=1), margin=dict(l=0, r=0, t=40, b=0))
        fn = OUT / f"cell3d_{el}_{n}.html"
        fig.write_html(fn, include_plotlyjs=True)
        print(n, dict(cnt), "->", fn)


if __name__ == "__main__":
    main()
