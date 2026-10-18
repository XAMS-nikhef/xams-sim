#!/usr/bin/env python3
"""What if the anode mesh is rotated by 120 deg (= 30 deg for a square mesh) relative to the gate?
Scans anode_rotation_s2 / _s1 (anode at 29.4 deg = as now, 149.4 deg = +120 deg; level 4 mm, middle optics).

    python optical/anode_rotation.py  ->  results/anode_rotation/ (README.md, summary.json, anode_rotation.png)
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
from scan_data import load, top_fraction  # noqa: E402

OUT = ROOT / "results" / "anode_rotation"
TOP = (1, 2, 3, 4)
ANG = "meshes.1.angle_to_anodes_deg"
LAB = {29.4: "anode as now (29.4°, aligned with the gate)", 149.4: "anode rotated by 120° (149.4°)"}


def fine_contrast(rec, n, half=10.0, step=1.0):
    """relative RMS of the top-light collection in 1 mm cells of the central 20 x 20 mm, beyond Poisson"""
    e = np.arange(-half, half + step / 2, step)
    top = rec[np.isin(rec["sensor"], TOP)]
    kt, _, _ = np.histogram2d(top["x0"], top["y0"], [e, e])
    emitted = n * step * step / (np.pi * 30.0 ** 2)          # uniform source over r < 30 mm
    lce = kt / emitted
    rel = lce.std() / lce.mean()
    poisson = 1 / np.sqrt(kt.mean())
    return float(np.sqrt(max(rel ** 2 - poisson ** 2, 0))), float(rel), float(poisson), lce


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s2, s1 = load("anode_rotation_s2"), load("anode_rotation_s1")
    res = {}
    fig, ax = plt.subplots(2, 2, figsize=(11, 8))
    edges = np.arange(0, 30.1, 2.5)
    rc = 0.5 * (edges[1:] + edges[:-1])
    ze = np.arange(-52, 0.1, 4)
    zc = 0.5 * (ze[1:] + ze[:-1])
    for p, q, col in zip(sorted(s2["points"], key=lambda p: p["params"][ANG]),
                         sorted(s1["points"], key=lambda p: p["params"][ANG]), ("C0", "C3")):
        a = p["params"][ANG]
        r2, n2, r1, n1 = p["rec"], p["n_photons"], q["rec"], q["n_photons"]
        f2, e2 = top_fraction(r2)
        f1, e1 = top_fraction(r1)
        contrast, rel, pois, lce = fine_contrast(r2, n2)
        r = np.hypot(r2["x0"], r2["y0"])
        tr = np.array([top_fraction(r2[(r >= lo) & (r < hi)]) for lo, hi in zip(edges[:-1], edges[1:])])
        z = r1["z0"]
        tz = np.array([top_fraction(r1[(z >= lo) & (z < hi)]) for lo, hi in zip(ze[:-1], ze[1:])])
        top = r2[np.isin(r2["sensor"], TOP)]
        u = np.where(np.isin(top["sensor"], (1, 3)), 1.0, -1.0)
        pe = np.arange(-24, 24.1, 2)
        pcen = 0.5 * (pe[1:] + pe[:-1])
        m = np.abs(top["y0"]) < 3
        nu, _ = np.histogram(-top["x0"][m], pe)
        uu = np.histogram(-top["x0"][m], pe, weights=u[m])[0] / nu
        ue = np.sqrt((1 - uu ** 2) / nu)
        res[str(a)] = dict(
            s2_top_fraction=f2, s2_err=e2,
            s2_lce_top=float(np.isin(r2["sensor"], TOP).sum() / n2), s2_lce_bottom=float((r2["sensor"] == 0).sum() / n2),
            s1_top_fraction=f1, s1_err=e1,
            s1_lce_top=float(np.isin(r1["sensor"], TOP).sum() / n1), s1_lce_bottom=float((r1["sensor"] == 0).sum() / n1),
            anode_foil_absorbed_s2=sum(v for (c, vol), v in p["tally"].items() if vol == "anodeFoil") / n2,
            fine_structure_rel_rms=contrast, fine_rel_rms_total=rel, fine_poisson=pois)
        lab = LAB[a]
        ax[0, 0].fill_between(rc, tr[:, 0] - tr[:, 1], tr[:, 0] + tr[:, 1], color=col, alpha=0.4, lw=0, label=lab)
        ax[0, 1].fill_between(zc, tz[:, 0] - tz[:, 1], tz[:, 0] + tz[:, 1], color=col, alpha=0.4, lw=0, label=lab)
        ax[1, 0].fill_between(pcen, uu - ue, uu + ue, color=col, alpha=0.4, lw=0, label=lab)
        if a > 100:
            im = ax[1, 1].imshow(lce.T, origin="lower", extent=[-10, 10, -10, 10], cmap="viridis")
            fig.colorbar(im, ax=ax[1, 1], label="top-PMT light collection")
    ax[0, 0].set(xlabel="S2 radius r [mm]", ylabel="S2 top fraction", title="S2 top fraction vs r")
    ax[0, 1].set(xlabel="S1 depth z [mm]", ylabel="S1 top fraction", title="S1 top fraction vs z")
    ax[1, 0].set(xlabel="x [mm] (data frame)", ylabel="u", title="top-sector asymmetry u(x)")
    ax[1, 1].set(xlabel="x [mm]", ylabel="y [mm]", title="top light per S2 position, rotated anode (1 mm cells)")
    for a in ax.flat[:3]:
        a.legend(fontsize=7)
    fig.suptitle("Anode mesh rotated by 120° (= 30° for a square mesh) relative to the gate (simulation, ±1σ bands)")
    fig.tight_layout()
    fig.savefig(OUT / "anode_rotation.png", dpi=130)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
