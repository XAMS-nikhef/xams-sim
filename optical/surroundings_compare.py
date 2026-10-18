#!/usr/bin/env python3
"""Geometry v4 (PTFE holders around the PMTs; TPC in the PTFE bucket in the steel vessel) vs v3 (absorbing world around the TPC): one parameter point
(level 4 mm, PTFE R 0.95, specular 0.1, steel R 0.35, Rayleigh 45 cm) for s2 and s1. v3 = that point of the step-8 fit
scans (fit_s2, fit_s1), v4 = optical/scans/check_v4_s2.yaml, check_v4_s1.yaml.

    python optical/surroundings_compare.py  ->  results/surroundings/{compare.png, summary.json}
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
from scan_data import TOP, load, top_fraction  # noqa: E402
from step6_results import losses  # noqa: E402

REF = {"optics.ptfe_in_liquid.reflectivity": 0.95, "optics.ptfe_in_liquid.specular_fraction": 0.1,
       "optics.stainless_steel_reflectivity": 0.35, "optics.lxe.rayleigh_length_cm": 45}
OUT = ROOT / "results" / "surroundings"


def v3_point(name):
    return next(p for p in load(name)["points"] if all(p["params"].get(k) == v for k, v in REF.items()))


def ratio_vs(rec, x, edges, n_emitted):
    """top fraction and top / bottom light collection (per emitted photon) in bins of x"""
    t = np.histogram(x[np.isin(rec["sensor"], TOP)], edges)[0].astype(float)
    b = np.histogram(x[rec["sensor"] == 0], edges)[0].astype(float)
    f = t / (t + b)
    return f, np.sqrt(f * (1 - f) / (t + b)), t / n_emitted, b / n_emitted


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for src, a in (("s2", ax[0]), ("s1", ax[1])):
        pts = {"v3 (no surroundings)": v3_point(f"fit_{src}"), "v4 (PMT PTFE, bucket, vessel)": load(f"check_v4_{src}")["points"][0]}
        summary[src] = {}
        for i, (lab, p) in enumerate(pts.items()):
            rec, n = p["rec"], p["n_photons"]
            f, fe = top_fraction(rec)
            L = losses(p)
            summary[src][lab] = dict(n_photons=n, top_fraction=round(f, 4), top_fraction_err=round(fe, 4),
                                     lce_top=round(L["detected top PMT"], 4), lce_bottom=round(L["detected bottom PMT"], 4),
                                     losses={k: round(v, 4) for k, v in sorted(L.items(), key=lambda kv: -kv[1])})
            if src == "s2":
                e = np.arange(0, 30.1, 2.5)
                x = np.hypot(rec["x0"], rec["y0"])
                xl = "r [mm]"
            else:
                e = np.arange(-50, 4.1, 4.0)
                x = rec["z0"]
                xl = "z [mm]"
            c = 0.5 * (e[1:] + e[:-1])
            fr, fre, _, _ = ratio_vs(rec, x, e, n)
            a.fill_between(c, fr - fre, fr + fre, color=f"C{i}", alpha=0.4, lw=0, label=f"{lab}: {f:.3f}")
            a.set(xlabel=xl, ylabel="top fraction (detected)", title=f"{src.upper()} top fraction")
        a.legend(fontsize=8)
    # losses s2: where the photons end
    cats = sorted({k for v in summary["s2"].values() for k in v["losses"]},
                  key=lambda k: -max(v["losses"].get(k, 0) for v in summary["s2"].values()))
    y = np.arange(len(cats))
    for i, (lab, v) in enumerate(summary["s2"].items()):
        ax[2].barh(y + (0.2 if i == 0 else -0.2), [v["losses"].get(k, 0) for k in cats], 0.4, color=f"C{i}", label=lab)
    ax[2].set_yticks(y, cats, fontsize=7)
    ax[2].invert_yaxis()
    ax[2].set(xlabel="fraction of emitted S2 photons", title="S2: where the photons end")
    ax[2].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "compare.png", dpi=130)
    json.dump(summary, open(OUT / "summary.json", "w"), indent=1)
    for src, d in summary.items():
        for lab, v in d.items():
            print(src, lab, "top fraction", v["top_fraction"], "+-", v["top_fraction_err"], "LCE top", v["lce_top"],
                  "bottom", v["lce_bottom"])
    print(json.dumps({lab: v["losses"] for lab, v in summary["s2"].items()}, indent=1))


if __name__ == "__main__":
    main()
