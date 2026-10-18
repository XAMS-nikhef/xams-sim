#!/usr/bin/env python3
"""S2 check of the Geant4 particle mode (docs/xams_sim_plan.md): Cs-137 energy deposits in the XAMS TPC.

Per event the energy deposited in the drift region (liquid xenon, r < 31 mm, cathode -51.8 mm < z < gate 0) is summed:
  - spectrum: photopeak (662 keV), Compton edge (expected 477 keV), photopeak fraction;
  - depth profile of photopeak events (energy-weighted mean z of the event's drift-region deposits), r < 22 mm;
  - comparison with the September data (SR-2026.2 Cs-137, Δ750 V): photopeak events with the clean cuts of
    optical/spread_map.py, z from the drift time (gate 1.15 µs, cathode 38.2 µs), r < 22 mm. The September source height
    was not recorded; simulated heights at 100 mm from the axis are compared by shape.
Uses runs made with `xamssim g4 config/runs/s2_*.yaml`.

    python validation/s2_particle_check.py   ->  results/s2_particle/ (s2_particle.png, summary.json)
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "optical"))
from xamssim import g4io  # noqa: E402

OUT = ROOT / "results" / "s2_particle"
RUNS = [("s2_cs137_raised", "raised: z −26 mm (short-fill plan)"), ("s2_cs137_r100_cathode", "cathode level: z −52 mm"),
        ("s2_cs137_r100_below", "30 mm below cathode: z −82 mm")]
DATA = ROOT.parent / "measurements" / "analysis_SR2026.2" / "outputs" / "s2_channels.npz"
R_TPC, Z_GATE, Z_CATH = 31.0, 0.0, -51.8
ZB = np.arange(-52, 0.1, 2.0)


def per_event(run):
    h, d, ev = g4io.read(ROOT / "run" / "g4" / run / "deposits")
    r = np.hypot(d["x"], d["y"])
    m = (r < R_TPC) & (d["z"] > Z_CATH) & (d["z"] < Z_GATE)
    dd = d[m]
    n = len(ev)
    e = np.bincount(dd["event"], weights=dd["edep"], minlength=n)
    ez = np.bincount(dd["event"], weights=dd["edep"] * dd["z"], minlength=n)
    ex = np.bincount(dd["event"], weights=dd["edep"] * dd["x"], minlength=n)
    ey = np.bincount(dd["event"], weights=dd["edep"] * dd["y"], minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        z, x, y = ez / e, ex / e, ey / e
    return dict(h=h, e=e, z=z, r=np.hypot(x, y), n=n)


def data_profile():
    if not DATA.exists():
        return None
    from s1cut_spectrum import s1_consistent
    D = np.load(DATA)
    g = {k: D[f"cs137_{k}"] for k in ("x", "y", "drift_time", "s2_area", "s1_area", "s1_aft_led", "s2_range_50p_area", "cs1")}
    t = g["drift_time"] / 1e3
    r = np.hypot(g["x"], g["y"])
    z = -51.8 * (t - 1.15) / (38.2 - 1.15)
    a1, s1 = g["s1_aft_led"], g["s1_area"]
    wg = np.sqrt(np.clip(g["s2_range_50p_area"] ** 2 - 3600 * t, 0, None))
    band = np.load(DATA.parent / "aft_maps.npz")["cs_cs1_band"]
    clean = (s1 >= 20) & (a1 > 0) & (a1 < 1) & (t > 3) & (wg > 450) & s1_consistent(t, a1, s1, (g["s2_area"] > 2e4) & (r < 18))
    pk = clean & (g["cs1"] > band[0]) & (g["cs1"] < band[1]) & (r < 22)
    return z[pk]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 3, figsize=(17, 5))
    res = {"definition": "drift region: LXe, r < 31 mm, -51.8 < z < 0 mm; photopeak: E >= 655 keV; depth: energy-weighted z, r < 22 mm"}
    eb = np.arange(0, 720, 5)
    dz = data_profile()
    for k, (run, lab) in enumerate(RUNS):
        p = per_event(run)
        e = p["e"]
        hit = e > 0
        pk = e >= 655
        hist, _ = np.histogram(e[hit], eb)
        ax[0].step(eb[:-1], hist / hist.sum(), where="post", color=f"C{k}", label=lab)
        # Compton edge: steepest fall of the smoothed spectrum between 400 and 600 keV
        c = 0.5 * (eb[1:] + eb[:-1])
        sm = np.convolve(hist, np.ones(3) / 3, mode="same").astype(float)
        sel = (c > 400) & (c < 600)
        edge = float(c[sel][np.argmin(np.gradient(sm)[sel])])
        prof, _ = np.histogram(p["z"][pk & (p["r"] < 22)], ZB)
        ax[1].step(ZB[:-1], prof / prof.sum(), where="post", color=f"C{k}", label=lab)
        res[run] = dict(label=lab, decays=p["n"], events_with_tpc_deposit=int(hit.sum()), photopeak_events=int(pk.sum()),
                        photopeak_fraction=round(float(pk.sum() / hit.sum()), 4), compton_edge_keV=edge,
                        photopeak_per_1e6_decays=round(1e6 * float(pk.sum()) / p["n"], 1),
                        photopeak_depth_median_mm=round(float(np.nanmedian(p["z"][pk & (p["r"] < 22)])), 1))
        if dz is not None:
            # shape comparison with data in the range the data cover well (z < -4 mm, above the cathode pile-up)
            rng = (ZB[:-1] > -48) & (ZB[:-1] < -4)
            hd, _ = np.histogram(dz, ZB)
            a, b = prof[rng].astype(float), hd[rng].astype(float)
            a, b = a / a.sum(), b / b.sum()
            chi2 = float(np.sum((a - b) ** 2 / (a / max(prof[rng].sum(), 1) + b / max(hd[rng].sum(), 1) + 1e-12)))
            res[run]["shape_chi2_vs_sept_data"] = round(chi2, 1)
            res[run]["shape_ndf"] = int(rng.sum() - 1)
    ax[0].axvline(477.3, color="0.5", ls=":", lw=1)
    ax[0].text(480, ax[0].get_ylim()[1] * 0.5, "Compton edge 477 keV", fontsize=7, color="0.4")
    ax[0].set(xlabel="energy in the drift region [keV]", ylabel="fraction of events with a deposit", yscale="log",
              title="Cs-137: energy deposited in the drift region")
    ax[0].legend(fontsize=7)
    if dz is not None:
        hd, _ = np.histogram(dz, ZB)
        ax[1].errorbar(0.5 * (ZB[1:] + ZB[:-1]), hd / hd.sum(), np.sqrt(hd) / hd.sum(), fmt="ko", ms=3, label=f"data Sept (Cs, clean, n={len(dz)})")
        res["sept_data"] = dict(n=int(len(dz)), median_z_mm=round(float(np.median(dz)), 1))
    ax[1].set(xlabel="z [mm] (gate 0, cathode −51.8)", ylabel="normalised", title="photopeak events: depth (r < 22 mm)")
    ax[1].legend(fontsize=7)
    # photopeak rate per height
    xs = [res[r]["photopeak_per_1e6_decays"] for r, _ in RUNS]
    ax[2].bar(range(len(RUNS)), xs, color=[f"C{k}" for k in range(len(RUNS))])
    ax[2].set_xticks(range(len(RUNS)), [lab.split(":")[0] for _, lab in RUNS], fontsize=8)
    ax[2].set(ylabel="photopeak events in the drift region per 10⁶ decays", title="source height vs photopeak rate (r = 100 mm)")
    fig.tight_layout()
    fig.savefig(OUT / "s2_particle.png", dpi=120)
    json.dump(res, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
