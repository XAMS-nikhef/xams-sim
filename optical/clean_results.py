#!/usr/bin/env python3
"""Clean-data results: joint optical fit (no source + Cs-137 photopeak, same optics, ε free per sample) and the
relative top/bottom efficiencies ε versus S2 size per sample.

Inputs: results/clean_fit_none/ and results/clean_fit_photopeak/ (optical/step8_fit.py on the clean targets
optical/targets/data_2026-10-11_clean.json and data_2026-10-11_photopeak_clean.json), the fit_s2 scan (best point) and the
clean targets (S2 AFT versus S2 size for no source, Na-22, Cs-137).
ε is defined on the odds: AFT_data / (1 - AFT_data) = ε · AFT_sim / (1 - AFT_sim).

    python optical/clean_results.py  ->  results/clean_joint/ (summary.json, profiles.png, efficiencies.png)
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
sys.path.insert(0, str(ROOT / "optical"))
import step8_fit as S  # noqa: E402

OUT = ROOT / "results" / "clean_joint"
NAMES = ("PTFE R", "PTFE specular", "steel R", "Rayleigh [cm]")
KEYS = ("optics.ptfe_in_liquid.reflectivity", "optics.ptfe_in_liquid.specular_fraction",
        "optics.stainless_steel_reflectivity", "optics.lxe.rayleigh_length_cm")
odds = lambda a: a / (1 - a)  # noqa: E731


def table(name):
    return {tuple(r[k] for k in NAMES): r for r in csv.DictReader(open(ROOT / "results" / name / "fit_table.csv"))}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    A, B = table("clean_fit_none"), table("clean_fit_photopeak")
    ndf = {s: json.load(open(ROOT / "results" / s / "summary.json"))["ndf"] for s in ("clean_fit_none", "clean_fit_photopeak")}
    rows = sorted(((float(A[k]["chi2"]) + float(B[k]["chi2"]), k) for k in A), key=lambda x: x[0])
    c0, kb = rows[0]
    prof = {}
    for i, n in enumerate(NAMES):
        vals = sorted({k[i] for k in A}, key=float)
        prof[n] = {v: round(min(c for c, k in rows if k[i] == v) - c0, 1) for v in vals}
    best = dict(zip(NAMES, map(float, kb)))
    res = dict(best=best, chi2_joint=round(c0, 1),
               ndf_joint=int(sum(sum(v.values()) for v in ndf.values()) - 2 * 2),
               none=dict(eps_s2=float(A[kb]["eps_s2"]), eps_s1=float(A[kb]["eps_s1"]), chi2=float(A[kb]["chi2"]),
                         chi2_s2r=float(A[kb]["chi2_s2r"]), chi2_s1z=float(A[kb]["chi2_s1z"]), chi2_uv=float(A[kb]["chi2_uv"]), ndf=ndf["clean_fit_none"]),
               photopeak=dict(eps_s2=float(B[kb]["eps_s2"]), eps_s1=float(B[kb]["eps_s1"]), chi2=float(B[kb]["chi2"]),
                              chi2_s2r=float(B[kb]["chi2_s2r"]), chi2_s1z=float(B[kb]["chi2_s1z"]), chi2_uv=float(B[kb]["chi2_uv"]),
                              ndf=ndf["clean_fit_photopeak"]),
               profiles=prof, top5=[dict(zip(NAMES, map(float, k)), chi2=round(c, 1)) for c, k in rows[:5]])
    fig, ax = plt.subplots(figsize=(6, 4.2))
    for n, st in zip(NAMES, ("o-", "s-", "^-", "d-")):
        ax.plot(range(3), list(prof[n].values()), st, label=f"{n}: " + " / ".join(prof[n].keys()))
    ax.set(xticks=[0, 1, 2], xticklabels=["low", "middle", "high"], ylabel="Δχ² (joint, profiled)",
           title="Joint fit: clean no source + Cs-137 photopeak")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "profiles.png", dpi=130)

    # ε versus S2 size, best optics; simulation AFT over r < 25 mm weighted with the data's r distribution
    idx = json.load(open(ROOT / "run" / "scans" / "fit_s2" / "points.json"))
    p = [q for q in idx["points"] if all(abs(q["params"][k] - v) < 1e-9 for k, v in zip(KEYS, best.values()))][0]
    rec = S.point_records("fit_s2", p)
    rec = rec[np.isin(rec["sensor"], (0, 1, 2, 3, 4))]
    rs, top = np.hypot(rec["x0"], rec["y0"]), np.isin(rec["sensor"], (1, 2, 3, 4))
    D = json.load(open(ROOT / "optical" / "targets" / "data_2026-10-11_clean.json"))
    re_ = np.array(D["edges"]["r"])
    sim_r = np.array([top[(rs >= a) & (rs < b)].mean() for a, b in zip(re_[:-1], re_[1:])])
    w = np.array(D["none"]["s2_aft_vs_r_n"], float)            # r distribution of the data (no source, 3-20 kPE)
    sim25 = float(np.sum(sim_r * w) / w.sum())
    se = np.array(D["edges"]["s2"])
    sc = np.sqrt(se[1:] * se[:-1])
    res["sim_aft_r25"] = sim25
    res["eps_vs_size"] = {}
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    for k, lab, col in (("none", "no source", "k"), ("na22", "Na-22", "C1"), ("cs137", "Cs-137", "C3")):
        a = np.array([np.nan if v is None else v for v in D[k]["s2_aft_vs_size_led"]])
        ae = np.array([np.nan if v is None else v for v in D[k]["s2_aft_vs_size_led_err"]])
        eps = odds(a) / odds(sim25)
        eerr = eps * ae / (a * (1 - a))
        plateau = float(np.nanmean(eps[se[:-1] >= 2e4]))
        res["eps_vs_size"][lab] = dict(s2_bins=se.tolist(), eps=[round(float(v), 3) for v in eps],
                                       eps_err=[round(float(v), 3) for v in eerr], plateau=round(plateau, 3),
                                       shape=[round(float(v), 3) for v in eps / plateau])
        ax[0].errorbar(sc, eps, eerr, fmt="o", color=col, label=f"{lab} (plateau {plateau:.2f})")
        ax[1].errorbar(sc, eps / plateau, eerr / plateau, fmt="o", color=col, label=lab)
    ax[0].set(xscale="log", xlabel="S2 [PE]", ylabel="ε = data odds ÷ simulated odds", title="Relative top/bottom efficiency ε")
    ax[1].set(xscale="log", xlabel="S2 [PE]", ylabel="ε ÷ plateau (S2 > 20 kPE)", title="Signal-size factor (same for all samples)")
    for a_ in ax:
        a_.axhline(1, color="0.6", lw=0.6)
        a_.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "efficiencies.png", dpi=130)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "eps_vs_size"}, indent=1))
    for lab, v in res["eps_vs_size"].items():
        print(lab, "eps", v["eps"], "plateau", v["plateau"], "shape", v["shape"])


if __name__ == "__main__":
    main()
