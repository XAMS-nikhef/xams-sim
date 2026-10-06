#!/usr/bin/env python3
"""Step 6: first physics results from the production scans (scans/s2_optics, s2_rayleigh, s1_optics).

    python tools/step6_results.py            # figures + results/step6/summary.json

Figures (results/step6/):
  s2_topfraction.png    S2 top fraction vs PTFE reflectivity, per steel reflectivity, per liquid level
  s2_lce.png            S2 light collection (detected / emitted) top and bottom, same grid
  s2_rayleigh.png       S2 top fraction vs Rayleigh length, per PTFE specular fraction
  s2_vs_r.png           S2 top fraction vs radius of the S2 (reference point, three levels)
  s2_sectors.png        share of each top-PMT sector vs S2 position (reference point)
  s1_vs_z.png           S1 top fraction and light collection vs z (2 mm slices), per PTFE reflectivity
  losses.png            where the photons end (S2 and S1, reference point)
Checks: every point split in two halves of its parts (independent seeds) must agree within statistics.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from read_output import read  # noqa: E402
from scan_data import load, top_fraction  # noqa: E402

OUT = ROOT / "results" / "step6"
TOP = (1, 2, 3, 4)
PTFE = "optics.ptfe_in_liquid.reflectivity"
STEEL = "optics.stainless_steel_reflectivity"
RAYL = "optics.lxe.rayleigh_length_cm"
SPEC = "optics.ptfe_in_liquid.specular_fraction"


def opt(p, path):
    """value of a config path for this point (scan parameter or the config default)"""
    if path in p["params"]:
        return p["params"][path]
    v = p["config_json"]
    for k in path.split("."):
        v = v[k]
    return v


def level(p):
    return p["config_json"]["liquid"]["level_above_gate_mm"]


def lce(p):
    rec = p["rec"]
    n = p["n_photons"]
    return np.isin(rec["sensor"], TOP).sum() / n, (rec["sensor"] == 0).sum() / n, np.isin(rec["sensor"], (6, 7)).sum() / n


def halves(name):
    """top fraction of the first and second half of the parts of each point (independent seeds)"""
    d = ROOT / "run" / "scans" / name
    idx = json.load(open(d / "points.json"))
    worst = 0.0
    for p in idx["points"]:
        k = len(p["parts"]) // 2
        f = []
        for parts in (p["parts"][:k], p["parts"][k:]):
            rec = np.concatenate([read(d / q["file"])[0] for q in parts])
            f.append(top_fraction(rec))
        pull = (f[0][0] - f[1][0]) / np.hypot(f[0][1], f[1][1])
        worst = max(worst, abs(pull))
    return worst


def category(code, vol):
    if code == 2:
        return "bulk absorption (LXe)"
    if code == 4:
        return "escaped"
    if code == 1:
        return "detected"
    if vol in ("TopPMTSector", "BottomPMTCathode", "SiPM"):
        return "photocathode, not converted (1 - QE)"
    if vol.endswith("Foil"):
        return f"mesh foil: {vol[:-4]}"
    if vol == "CopperRing":
        return "copper field-shaping rings"
    if vol.endswith("Ring") or vol.endswith("Rim"):
        return "mesh rings (+ foil rim)"
    if vol == "PTFE":
        return "PTFE"
    if vol == "Bucket":
        return "PTFE bucket"
    if vol == "Vessel":
        return "cryostat vessel (steel)"
    if vol.endswith("Frame") or vol.endswith("Body") or vol.endswith("Window") or vol.endswith("DeadCross"):
        return "PMT frame / body"
    if vol == "World":
        return "leaves the TPC region"
    return f"other: {vol}"


def losses(p):
    out = defaultdict(int)
    for (code, vol), n in p["tally"].items():
        out[category(code, vol)] += n
    rec = p["rec"]
    out.pop("detected", None)
    out["detected top PMT"] = int(np.isin(rec["sensor"], TOP).sum())
    out["detected bottom PMT"] = int((rec["sensor"] == 0).sum())
    out["detected SiPMs"] = int(np.isin(rec["sensor"], (6, 7)).sum())
    return {k: v / p["n_photons"] for k, v in out.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}

    # ---------------------------------------------------------------- S2: level x PTFE x steel
    s2 = load("s2_optics")
    pts = s2["points"]
    levels = sorted({level(p) for p in pts})
    ptfes = sorted({opt(p, PTFE) for p in pts})
    steels = sorted({opt(p, STEEL) for p in pts})
    fig, axs = plt.subplots(1, len(levels), figsize=(4.2 * len(levels), 3.8), sharey=True)
    fig2, axs2 = plt.subplots(1, len(levels), figsize=(4.2 * len(levels), 3.8), sharey=True)
    table = []
    for ax, ax2, lv in zip(axs, axs2, levels):
        for st, col in zip(steels, ("C0", "C1", "C2")):
            sel = sorted([p for p in pts if level(p) == lv and opt(p, STEEL) == st], key=lambda p: opt(p, PTFE))
            tf = [top_fraction(p["rec"]) for p in sel]
            ce = [lce(p) for p in sel]
            x = [opt(p, PTFE) for p in sel]
            ax.errorbar(x, [t[0] for t in tf], [t[1] for t in tf], marker="o", color=col, label=f"steel R = {st}")
            ax2.plot(x, [c[0] for c in ce], "o-", color=col, label=f"top, steel R = {st}")
            ax2.plot(x, [c[1] for c in ce], "s--", color=col, label=f"bottom, steel R = {st}")
            for p, t, c in zip(sel, tf, ce):
                table.append(dict(level=lv, ptfe=opt(p, PTFE), steel=st, top_fraction=t[0], err=t[1],
                                  lce_top=c[0], lce_bottom=c[1], lce_sipm=c[2]))
        ax.axhspan(0.50, 0.54, color="grey", alpha=0.25, label="data, low load (~0.52)")
        ax.set_title(f"liquid level {lv} mm above gate")
        ax.set_xlabel("PTFE reflectivity (liquid)")
        ax2.set_title(f"liquid level {lv} mm above gate")
        ax2.set_xlabel("PTFE reflectivity (liquid)")
    axs[0].set_ylabel("S2 top fraction")
    axs[0].legend(fontsize=7)
    axs2[0].set_ylabel("detected / emitted (QE 0.33 included)")
    axs2[0].legend(fontsize=6)
    fig.suptitle("S2 top fraction (S2 uniform in the gas gap, r < 30 mm)")
    fig2.suptitle("S2 light collection efficiency")
    fig.tight_layout()
    fig2.tight_layout()
    fig.savefig(OUT / "s2_topfraction.png", dpi=130)
    fig2.savefig(OUT / "s2_lce.png", dpi=130)
    summary["s2_optics"] = table
    summary["s2_optics_half_split_worst_pull"] = halves("s2_optics")

    # reference point: middle optics at each level
    ref = {lv: next(p for p in pts if level(p) == lv and opt(p, PTFE) == ptfes[1] and opt(p, STEEL) == steels[1])
           for lv in levels}

    # S2 top fraction vs r
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    edges = np.arange(0, 31, 2.5)
    rc = 0.5 * (edges[1:] + edges[:-1])
    summary["s2_vs_r"] = {}
    for lv, p in ref.items():
        rec = p["rec"]
        r = np.hypot(rec["x0"], rec["y0"])
        tf = [top_fraction(rec[(r >= a) & (r < b)]) for a, b in zip(edges[:-1], edges[1:])]
        ax.errorbar(rc, [t[0] for t in tf], [t[1] for t in tf], marker="o", ms=3, label=f"level {lv} mm")
        summary["s2_vs_r"][lv] = [t[0] for t in tf]
    ax.set_xlabel("S2 radius r [mm]")
    ax.set_ylabel("S2 top fraction")
    ax.set_title(f"S2 top fraction vs r (PTFE R {ptfes[1]}, steel R {steels[1]})", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "s2_vs_r.png", dpi=130)

    # top-PMT sector pattern vs S2 position (level 4 reference)
    p = ref[max(levels)]
    rec = p["rec"][np.isin(p["rec"]["sensor"], TOP)]
    b = np.linspace(-30, 30, 31)
    tot, _, _ = np.histogram2d(rec["x0"], rec["y0"], bins=[b, b])
    fig, axs = plt.subplots(1, 4, figsize=(15, 3.8))
    for s, ax in zip(TOP, axs):
        h, _, _ = np.histogram2d(rec["x0"][rec["sensor"] == s], rec["y0"][rec["sensor"] == s], bins=[b, b])
        with np.errstate(invalid="ignore", divide="ignore"):
            fr = h / tot
        im = ax.imshow(fr.T, origin="lower", extent=[-30, 30, -30, 30], vmin=0, vmax=1, cmap="viridis")
        ax.add_patch(plt.Circle((0, 0), 30, fill=False, color="w", lw=0.8))
        ax.set_title(f"sector {['I', 'II', 'III', 'IV'][s - 1]} (ch{s}) share of top light", fontsize=9)
        ax.set_xlabel("x [mm]")
    axs[0].set_ylabel("y [mm]")
    fig.colorbar(im, ax=axs, shrink=0.8)
    fig.suptitle(f"top-PMT sector pattern vs S2 position (level {max(levels)} mm)")
    fig.savefig(OUT / "s2_sectors.png", dpi=130, bbox_inches="tight")
    # central and edge share of the own sector
    rr = np.hypot(rec["x0"], rec["y0"])
    summary["s2_sector_share_centre_r_lt_2mm"] = {int(s): float((rec["sensor"][rr < 2] == s).mean()) for s in TOP}

    # ---------------------------------------------------------------- S2: Rayleigh x specular
    sr = load("s2_rayleigh")
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    summary["s2_rayleigh"] = []
    for sp in sorted({opt(p, SPEC) for p in sr["points"]}):
        sel = sorted([p for p in sr["points"] if opt(p, SPEC) == sp], key=lambda p: opt(p, RAYL))
        tf = [top_fraction(p["rec"]) for p in sel]
        ax.errorbar([opt(p, RAYL) for p in sel], [t[0] for t in tf], [t[1] for t in tf], marker="o",
                    label=f"PTFE specular fraction {sp}")
        for p, t in zip(sel, tf):
            summary["s2_rayleigh"].append(dict(rayleigh_cm=opt(p, RAYL), specular=sp, top_fraction=t[0], err=t[1]))
    ax.set_xlabel("Rayleigh scattering length in LXe [cm]")
    ax.set_ylabel("S2 top fraction")
    ax.set_title("level 4 mm, PTFE R 0.945, steel R 0.35", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "s2_rayleigh.png", dpi=130)
    summary["s2_rayleigh_half_split_worst_pull"] = halves("s2_rayleigh")

    # ---------------------------------------------------------------- S1 vs z
    s1 = load("s1_optics")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8))
    ze = np.arange(-52, 0.1, 2)
    zc = 0.5 * (ze[1:] + ze[:-1])
    summary["s1_vs_z"] = {}
    for p in sorted(s1["points"], key=lambda p: opt(p, PTFE)):
        rec = p["rec"]
        n_per = p["n_photons"] * np.diff(np.clip(ze, -51.715, -0.085)) / (51.715 - 0.085)
        tf, top, bot = [], [], []
        for i, (a, b2) in enumerate(zip(ze[:-1], ze[1:])):
            sel = rec[(rec["z0"] >= a) & (rec["z0"] < b2)]
            tf.append(top_fraction(sel))
            top.append(np.isin(sel["sensor"], TOP).sum() / n_per[i])
            bot.append((sel["sensor"] == 0).sum() / n_per[i])
        a1.errorbar(zc, [t[0] for t in tf], [t[1] for t in tf], marker="o", ms=3, label=f"PTFE R {opt(p, PTFE)}")
        a2.plot(zc, top, "o-", ms=3, label=f"top, PTFE R {opt(p, PTFE)}")
        a2.plot(zc, bot, "s--", ms=3, label=f"bottom, PTFE R {opt(p, PTFE)}")
        summary["s1_vs_z"][opt(p, PTFE)] = dict(z=zc.tolist(), top_fraction=[t[0] for t in tf], lce_top=top,
                                                 lce_bottom=bot, top_fraction_all=top_fraction(rec)[0],
                                                 lce_all=float(np.isin(rec["sensor"], (0,) + TOP).sum() / p["n_photons"]))
    a1.set_xlabel("S1 depth z [mm] (gate 0, cathode −51.8)")
    a1.set_ylabel("S1 top fraction")
    a1.legend(fontsize=8)
    a2.set_xlabel("S1 depth z [mm]")
    a2.set_ylabel("detected / emitted (QE 0.33 included)")
    a2.legend(fontsize=7)
    fig.suptitle("S1 light (uniform in the drift region, r < 30 mm, level 4 mm, steel R 0.35)")
    fig.tight_layout()
    fig.savefig(OUT / "s1_vs_z.png", dpi=130)
    summary["s1_half_split_worst_pull"] = halves("s1_optics")

    # ---------------------------------------------------------------- where the light ends
    s1ref = next(p for p in s1["points"] if opt(p, PTFE) == ptfes[1])
    l2, l1 = losses(ref[max(levels)]), losses(s1ref)
    keys = sorted(set(l2) | set(l1), key=lambda k: -(l2.get(k, 0) + l1.get(k, 0)))
    fig, ax = plt.subplots(figsize=(8, 0.35 * len(keys) + 1.2))
    y = np.arange(len(keys))
    ax.barh(y - 0.2, [l2.get(k, 0) for k in keys], 0.4, label="S2 (gas gap)")
    ax.barh(y + 0.2, [l1.get(k, 0) for k in keys], 0.4, label="S1 (drift region)")
    ax.set_yticks(y, keys, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("fraction of emitted photons")
    ax.set_title(f"where the photons end (level {max(levels)} mm, PTFE R {ptfes[1]}, steel R {steels[1]})", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "losses.png", dpi=130)
    summary["losses_s2"], summary["losses_s1"] = l2, l1

    json.dump(summary, open(OUT / "summary.json", "w"), indent=1, default=float)
    print(json.dumps({k: v for k, v in summary.items() if "pull" in k}, indent=1))
    print("written to", OUT)


if __name__ == "__main__":
    main()
