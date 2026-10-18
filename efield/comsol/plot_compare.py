#!/usr/bin/env python3
"""Side-by-side (r, z) half-planes towards the SiPM for several cases (results/efield/comsol/maps_rz.npz): |E| and
electron drift lines (white: reach the gate, red: end on the wall / SiPM). Also the catchment: per start depth the
smallest start radius whose drift line ends on the wall / SiPM (fine radial scan).

    python efield/comsol/plot_compare.py cmb_m300 cmb_m100 cmb cmb_p100 cmb_p300 sept  ->  results/efield/comsol/compare_<first>_<last>.png
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

sys.path.insert(0, str(Path(__file__).parent))
from plot_rz import drift  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "efield" / "comsol"


def main():
    names = sys.argv[1:]
    C = yaml.safe_load(open(ROOT / "efield" / "cases.yaml"))
    zs = yaml.safe_load(open(ROOT / "config" / "geometry.yaml"))["sipms"]["z_mm"][0]
    M = np.load(OUT / "maps_rz.npz")
    r, z = M["r"], M["z"]
    fig, ax = plt.subplots(1, len(names), figsize=(3.6 * len(names), 7.2), sharey=True)
    res = {}
    for a, n in zip(np.atleast_1d(ax), names):
        Er, Ez = M[f"{n}_Er"], M[f"{n}_Ez"]
        E = np.hypot(Er, Ez) / 100
        fr = RegularGridInterpolator((r, z), np.nan_to_num(Er))
        fz = RegularGridInterpolator((r, z), np.nan_to_num(Ez))
        c = C["cases"][n]
        enom = (c["G"] - c["C"]) / 5.18
        a.pcolormesh(r, z, E.T, cmap="viridis", vmin=0, vmax=2.5 * enom, shading="auto")
        for z0 in np.arange(-50, -1, 2.5):
            for r0 in (12, 18, 22, 25, 27, 28.5, 29.5, 30.3):
                p, end = drift(fr, fz, r0, z0, step=0.05)
                a.plot(p[:, 0], p[:, 1], "-", color="w" if end == "gate" else "r", lw=0.55)
        # catchment edge: smallest r0 (0.25 mm scan) at each depth that ends on the wall / SiPM
        edge = {}
        for z0 in np.arange(-50, -1, 2.0):
            rr = [r0 for r0 in np.arange(10, 30.9, 0.25) if drift(fr, fz, r0, z0, step=0.1)[1] == "wall"]
            edge[round(float(z0), 1)] = round(float(min(rr)), 2) if rr else None
        res[n] = {"note": c.get("note", ""), "sipm_minus_local_V": c["SIPM"] - round((c["G"] + (c["C"] - c["G"]) * abs(zs) / 51.8)),
                  "catchment_min_r0_vs_z0": edge}
        ze = [k for k, v in edge.items() if v is not None]
        a.plot([edge[k] for k in ze], ze, "c--", lw=1.2)
        a.add_patch(plt.Rectangle((31, zs - 1.5), 1.0, 3.0, fill=False, ec="c", lw=1.0))
        a.axvspan(31, 36, color="0.85", alpha=0.3, lw=0)
        a.set(xlim=(10, 36), ylim=(-53, 2), xlabel="r [mm] (towards the SiPM)",
              title=f"{n}\nSiPM − local ≈ {res[n]['sipm_minus_local_V']:+d} V")
        a.set_aspect("equal")
    np.atleast_1d(ax)[0].set_ylabel("z [mm]")
    fig.suptitle("Drift lines near the SiPM (white: reach the gate, red: end on wall / SiPM; cyan dashed: catchment edge)", fontsize=10)
    fig.tight_layout()
    fn = OUT / f"compare_{names[0]}_{names[-1]}.png"
    fig.savefig(fn, dpi=120)
    json.dump(res, open(OUT / f"compare_{names[0]}_{names[-1]}.json", "w"), indent=1)
    for n, v in res.items():
        e = v["catchment_min_r0_vs_z0"]
        print(f"{n:9s} SiPM-local {v['sipm_minus_local_V']:+6d} V  catchment edge r0 at z0 = -45/-35/-25/-15/-5:",
              [e.get(k) for k in (-46.0, -36.0, -26.0, -16.0, -6.0)])
    print("written", fn)


if __name__ == "__main__":
    main()
