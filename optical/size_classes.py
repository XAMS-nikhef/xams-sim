#!/usr/bin/env python3
"""Best-fit optics (step 8: PTFE R 0.95, specular 0.1, steel R 0.2, Rayleigh 45 cm) against the S2 area fraction top
versus r of the no-source data per S2 size class, and of the Cs-137 photopeak; only the scale ε is fitted per sample.
Large S2s also split into y > 0 / y < 0 (event arrays of analysis_SR2026.2/outputs/aft_maps.npz).

    python optical/size_classes.py  ->  results/size_classes/ (summary.json, size_classes.png)
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
import step8_fit as S  # noqa: E402

OUT = ROOT / "results" / "size_classes"
BEST = {"optics.ptfe_in_liquid.reflectivity": 0.95, "optics.ptfe_in_liquid.specular_fraction": 0.1,
        "optics.stainless_steel_reflectivity": 0.2, "optics.lxe.rayleigh_length_cm": 45}
FLOOR = 0.010
odds = lambda a: a / (1 - a)  # noqa: E731


def fit_eps(d, de, sim, sime, mask):
    best = None
    for eps in np.linspace(0.1, 2.0, 3801):
        m = odds(sim) * eps
        model = m / (1 + m)
        c = np.nansum(((d - model) / np.sqrt(de ** 2 + FLOOR ** 2 + sime ** 2))[mask] ** 2)
        if best is None or c < best[1]:
            best = (float(eps), float(c), model)
    return best


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idx = json.load(open(ROOT / "run" / "scans" / "fit_s2" / "points.json"))
    p = [q for q in idx["points"] if all(abs(q["params"][k] - v) < 1e-9 for k, v in BEST.items())][0]
    rec = S.point_records("fit_s2", p)
    T = json.load(open(ROOT / "optical" / "targets" / "data_2026-10-05_single.json"))
    P = json.load(open(ROOT / "optical" / "targets" / "data_2026-10-09_photopeak.json"))["cs137"]
    ed = T["edges"]
    b = S.bin_s2(rec, ed)
    sim, sime = np.array(b["aft"], float), np.array(b["aft_e"], float)
    re_ = np.array(ed["r"])
    rc = 0.5 * (re_[1:] + re_[:-1])
    arr = lambda a: np.array([np.nan if v is None else v for v in a], float)  # noqa: E731
    samples = [(f"no source {k} PE", arr(v["aft"]), arr(v["err"])) for k, v in T["none"]["s2_aft_vs_r_by_size_led"].items()]
    samples.append(("Cs-137 photopeak", arr(P["s2_aft_vs_r_led"]), arr(P["s2_aft_vs_r_led_err"])))
    # large no-source S2s by y half, from the event arrays; simulation by the same y half
    D = np.load(ROOT.parent / "measurements" / "analysis_SR2026.2" / "outputs" / "aft_maps.npz")
    ev = {k[6:]: D[k] for k in D.files if k.startswith("bg_ev_")}
    aft = ev["top"] / (ev["top"] + ev["bot"])
    r = np.hypot(ev["x"], ev["y"])
    det = rec[np.isin(rec["sensor"], (0, 1, 2, 3, 4))]
    xs, ys = det["x0"], det["y0"]
    rs, top = np.hypot(xs, ys), np.isin(det["sensor"], (1, 2, 3, 4))
    half_sim = {}
    for lab, cond_d, cond_s in (("y > 0", ev["y"] > 0, ys > 0), ("y < 0", ev["y"] < 0, ys < 0)):
        m = (ev["s2"] >= 5e4) & cond_d
        d = np.array([np.median(aft[m & (r >= a) & (r < c)]) if (m & (r >= a) & (r < c)).sum() > 30 else np.nan
                      for a, c in zip(re_[:-1], re_[1:])])
        de = np.array([1.2533 * np.std(aft[m & (r >= a) & (r < c)]) / np.sqrt(max((m & (r >= a) & (r < c)).sum(), 1))
                       for a, c in zip(re_[:-1], re_[1:])])
        s = np.array([top[cond_s & (rs >= a) & (rs < c)].mean() for a, c in zip(re_[:-1], re_[1:])])
        half_sim[lab] = s
        samples.append((f"no source > 50 kPE, {lab}", d, de))
    res = {}
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    for k, (name, d, de) in enumerate(samples):
        sm = half_sim[name.split(", ")[1]] if name.endswith(("y > 0", "y < 0")) else sim
        mask = np.isfinite(d) & (rc >= 5)
        eps, chi2, model = fit_eps(d, de, sm, np.zeros_like(sm) if sm is not sim else sime, mask)
        res[name] = dict(eps=round(eps, 3), chi2_r_ge_5=round(chi2, 1), ndf=int(mask.sum() - 1),
                         centre_data_over_model=round(float(d[0] / model[0]), 3) if np.isfinite(d[0]) else None,
                         max_abs_residual_r_ge_5=round(float(np.nanmax(np.abs((d - model)[mask]))), 3))
        a = ax[0] if "y " not in name else ax[1]
        a.errorbar(rc, d / model, de / model, fmt="o-", ms=3, lw=0.8, label=f"{name} (ε {eps:.2f}, χ² {chi2:.0f}/{mask.sum() - 1})")
    for a, t in zip(ax, ("per S2 size class (azimuthal average)", "large no-source S2s by y half")):
        a.axhline(1, color="0.6", lw=0.6)
        a.set(xlabel="r [mm]", ylabel="data AFT ÷ model (best optics × ε)", title=t, ylim=(0.6, 1.4))
        a.legend(fontsize=6.5)
    fig.tight_layout()
    fig.savefig(OUT / "size_classes.png", dpi=120)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
