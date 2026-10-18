#!/usr/bin/env python3
"""Plot the (r, z) plane through the first SiPM from the COMSOL model (<data>/efield/comsol/maps_rz.npz):
|E| map with equipotentials and electron drift lines, full TPC and a zoom on the SiPM. r > 0 runs from the axis to the
SiPM (azimuth phi1 in cases.yaml), r < 0 to the opposite wall (no SiPM there). By the mirror symmetry of the SiPM hole
about this plane the field has no component out of the plane, so drift lines that start in it stay in it.

Drift lines: electrons move along -E (steps of 0.05 mm, bilinear interpolation), started on a grid of (r, z) points;
a line ends at the liquid surface region above the gate (z > 0: good), in the PTFE / SiPM hole (|r| > 31 mm: lost to
the wall or the SiPM) or at the cathode.

    python efield/comsol/plot_rz.py [case ...]   ->  <data>/efield/comsol/rz_<case>.png, drift_<case>.json
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from scipy.interpolate import RegularGridInterpolator  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
from xamssim.config import DATA  # noqa: E402  (outputs: ../simulations/data)
OUT = DATA / "efield" / "comsol"
R_IN, Z_C = 31.0, -51.8


def drift(fr, fz, r0, z0, step=0.05, nmax=40000):
    path = [(r0, z0)]
    r, z = r0, z0
    for _ in range(nmax):
        try:
            er, ez = float(fr((r, z))), float(fz((r, z)))
        except ValueError:
            return np.array(path), "outside"
        n = np.hypot(er, ez)
        if not np.isfinite(n) or n == 0:
            return np.array(path), "stuck"
        r, z = r - step * er / n, z - step * ez / n
        path.append((r, z))
        if z > 0.0:
            return np.array(path), "gate"
        if abs(r) > R_IN:
            return np.array(path), "wall"
        if z < Z_C:
            return np.array(path), "cathode"
    return np.array(path), "maxsteps"


def main():
    C = yaml.safe_load(open(ROOT / "efield" / "cases.yaml"))
    sp = yaml.safe_load(open(ROOT / "config" / "geometry.yaml"))["sipms"]
    M = np.load(OUT / "maps_rz.npz")
    r, z = M["r"], M["z"]
    names = sys.argv[1:] or sorted({k.rsplit("_", 1)[0] for k in M.files if k.endswith("_V")})
    for n in names:
        V, Er, Ez = M[f"{n}_V"], M[f"{n}_Er"], M[f"{n}_Ez"]
        E = np.hypot(Er, Ez) / 100                      # V/cm
        fr = RegularGridInterpolator((r, z), np.nan_to_num(Er), bounds_error=True)
        fz = RegularGridInterpolator((r, z), np.nan_to_num(Ez), bounds_error=True)
        c = C["cases"][n]
        enom = (c["G"] - c["C"]) / 5.18
        fig, ax = plt.subplots(1, 2, figsize=(16, 8.2), gridspec_kw={"width_ratios": [1.45, 1]})
        res = {"case": n, "note": c.get("note", ""), "drift_field_nominal_V_cm": round(enom, 1), "lines": []}
        starts = [(r0, z0) for z0 in np.arange(-50, -1, 3.0) for r0 in (-29.5, -27, -24, -20, -12, 0, 12, 20, 24, 27, 29.5)]
        zs = sp["z_mm"][0]
        starts += [(r0, z0) for z0 in np.arange(zs - 8, zs + 8.1, 0.5) for r0 in (29.0, 30.0, 30.6)]
        for k, (a, zoom) in enumerate(zip(ax, (None, (22, 33, zs - 9, zs + 9)))):
            vmax = 2.5 * enom if enom > 0 else E[np.isfinite(E)].max()
            im = a.pcolormesh(r, z, E.T, cmap="viridis", vmin=0, vmax=vmax, shading="auto")
            Vf = np.where(np.isfinite(V), V, np.nan)
            lev = np.arange(np.floor(np.nanmin(Vf) / 100) * 100, np.nanmax(Vf) + 1, 100 if k == 0 else 25)
            a.contour(r, z, Vf.T, levels=lev, colors="w", linewidths=0.35, alpha=0.7)
            plt.colorbar(im, ax=a, fraction=0.04, pad=0.02, label="|E| [V/cm]")
            for (r0, z0) in (starts[: 17 * 11] if k == 0 else starts[17 * 11:]):
                p, end = drift(fr, fz, r0, z0)
                col = {"gate": "w", "wall": "r", "cathode": "orange"}.get(end, "m")
                a.plot(p[:, 0], p[:, 1], "-", color=col, lw=0.6, alpha=0.9)
                if k == 1 or True:
                    res["lines"].append({"r0": r0, "z0": round(z0, 2), "end": end, "r_end": round(float(p[-1, 0]), 2),
                                         "z_end": round(float(p[-1, 1]), 2)})
            # outlines: PTFE wall, SiPM hole, rings, meshes
            for s in (-1, 1):
                a.fill_between([s * 31, s * 36], -50.925, 0, color="0.85", alpha=0.25, lw=0)
            a.add_patch(plt.Rectangle((31, zs - 1.5), 1.0, 3.0, fill=False, ec="c", lw=1.0))
            a.plot([32, 32], [zs - 1.5, zs + 1.5], "c-", lw=2.5)
            for zr in (-10.625, -20.425, -30.225, -40.025):
                for s in (-1, 1):
                    a.add_patch(plt.Rectangle((min(s * 36, s * 46.3), zr - 0.9), 10.3, 1.8, fc="#b87333", ec="none"))
            for zm in (0, -51.8, 8):
                a.axhline(zm, color="k", lw=0.8, ls="--")
            a.set(xlabel="r [mm]  (r > 0: towards the SiPM at %g°; r < 0: opposite side)" % sp["azimuth_deg"][0], ylabel="z [mm]")
            if zoom:
                a.set_xlim(zoom[0], zoom[1]); a.set_ylim(zoom[2], zoom[3]); a.set_aspect("equal")
                a.set_title("zoom on the SiPM (cyan: grounded plane, 1 mm deep hole)")
            else:
                a.set_xlim(-37, 37); a.set_ylim(-56, 10); a.set_aspect("equal")
                a.set_title(f"{n}: {c.get('note', '')} — nominal drift field {enom:.0f} V/cm\n"
                            "drift lines: white = reach the gate, red = end on wall / SiPM, orange = cathode")
        ends = [l["end"] for l in res["lines"]]
        res["fraction_lost"] = {e: round(ends.count(e) / len(ends), 3) for e in set(ends)}
        fig.tight_layout()
        fig.savefig(OUT / f"rz_{n}.png", dpi=130)
        plt.close(fig)
        json.dump(res, open(OUT / f"drift_{n}.json", "w"), indent=1)
        sipm_lines = [l for l in res["lines"] if l["r0"] >= 29]
        lost = [l for l in sipm_lines if l["end"] != "gate"]
        print(f"{n}: written rz_{n}.png; near-SiPM starts (r0 >= 29 mm): {len(lost)}/{len(sipm_lines)} not reaching the gate")


if __name__ == "__main__":
    main()
