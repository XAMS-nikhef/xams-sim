#!/usr/bin/env python3
"""S3 check of the micro-physics chain (docs/xams_sim_plan.md): input, fuse clustering, NEST yields.

On the S2 run `s2_cs137_raised` (Cs-137 at r = 130 mm, z = -26 mm, state cmb50), processed with `xamssim chain`:
  1. where the energy goes: raw Geant4 deposits per xenon region (drift region, liquid above the gate, below the
     cathode, liquid outside the field cage, gas); all but the liquid outside the field cage are simulated volumes;
  2. clusters per event and event classes for events with energy in the drift region and for the photopeak (total
     energy in the four volumes 662 keV): single scatter (SS, one cluster with electrons, nothing below the cathode),
     multiple scatter (MS), gamma-X (energy also below the cathode); clusters in the volumes with electrons (drift
     region, liquid above the gate, gas) count as scatters;
     SS also after merging drift clusters closer than dz = 1 / 3 mm (what an S2 resolution would see);
  3. sensitivity of the photopeak SS fraction to the clustering: lineage time threshold and gamma distance threshold,
     DBSCAN cluster size (first 10^6 decays);
  4. fuse NEST yields against standalone nestpy (means) at 100, 145, 500 V/cm, 662 keV, beta and gamma models;
  5. S1 / S2 (photons / electrons) anticorrelation of photopeak events at the local field.

    xamssim chain config/runs/s2_cs137_raised.yaml --target quanta     (first; ~5 min)
    python validation/s3_microphysics_check.py   ->  results/s3_microphysics/ (s3_microphysics.png, summary.json)
"""
import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from xamssim import chain, g4io  # noqa: E402
from xamssim.config import resolve  # noqa: E402

RUN = ROOT / "config" / "runs" / "s2_cs137_raised.yaml"
OUT = ROOT / "results" / "s3_microphysics"
E_PEAK, PEAK_WIN = 661.7, 5.0          # keV; photopeak window on the summed cluster energy
E_MIN = 1.0                            # keV; clusters below this are ignored in the classes
SENS_EVENTS = 1_000_000                # decays used for the sensitivity scans


# ---------------------------------------------------------------- 1. raw deposits per region
def regions(res):
    v = chain.volumes(res)
    r_fc, z_g, z_c, z_b, z_l = (v["xenonnt_sensitive_volume_radius"] * 10, v["xenonnt_z_gate_mesh"] * 10,
                                v["xenonnt_z_cathode"] * 10, v["xenonnt_z_bottom_pmts"] * 10, v["xenonnt_z_lxe"] * 10)
    h, d, ev = g4io.read(ROOT / "run" / "g4" / RUN.stem, mmap=True)
    r, z, e = np.hypot(d["x"], d["y"]), np.asarray(d["z"]), np.asarray(d["edep"], dtype=float)
    inside = r < r_fc
    reg = {
        "drift region": inside & (z > z_c) & (z < z_g),
        "liquid above gate": inside & (z >= z_g) & (z < z_l),
        "below cathode": inside & (z <= z_c) & (z > z_b),
        "liquid outside field cage": ~inside & (z < z_l),
        "gas": z >= z_l,
    }
    tot = e.sum()
    out = {k: dict(energy_fraction=round(float(e[m].sum() / tot), 4),
                   events=int(len(np.unique(np.asarray(d["event"])[m])))) for k, m in reg.items()}
    out["_n_decays"] = int(len(ev))
    return out


# ---------------------------------------------------------------- 2. event classes from clusters
def load_clusters(st, rid):
    return st.get_array(rid, ("clustered_interactions", "volume_properties"))


def classify(c, merge_dz_cm=(0.1, 0.3)):
    """Event classes from clusters (eventid, ed, z, vol_id). Volumes with electrons (S2): drift region (1), gas (3),
    above gate (4); below the cathode (2) gives light only. Clusters outside the volumes (vol_id 0) are invisible."""
    c = c[(c["ed"] > E_MIN) & (c["vol_id"] > 0)]
    ev = np.unique(c["eventid"])
    idx = np.searchsorted(ev, c["eventid"])
    n = len(ev)
    s2 = np.isin(c["vol_id"], [1, 3, 4])
    w = lambda m: np.bincount(idx, weights=c["ed"] * m, minlength=n)  # noqa: E731
    e_drift, e_s2, e_nos2 = w(c["vol_id"] == 1), w(s2), w(c["vol_id"] == 2)
    n_s2 = np.bincount(idx, weights=s2, minlength=n).astype(int)
    fast = np.bincount(idx, weights=np.isin(c["vol_id"], [3, 4]), minlength=n) > 0     # cluster above gate or in gas
    # S2-volume clusters per event after merging in z (S2 resolution)
    merged = {}
    cs = c[s2]
    cs = cs[np.lexsort((cs["z"], cs["eventid"]))]
    for dz in merge_dz_cm:
        new = np.ones(len(cs), bool)
        new[1:] = (cs["eventid"][1:] != cs["eventid"][:-1]) | (np.diff(cs["z"]) > dz)
        merged[dz] = np.bincount(np.searchsorted(ev, cs["eventid"]), weights=new, minlength=n).astype(int)
    has_drift = e_drift > 0
    gx = has_drift & (e_nos2 > E_MIN)
    peak = np.abs(e_s2 + e_nos2 - E_PEAK) < PEAK_WIN

    def fr(sel):
        k = max(sel.sum(), 1)
        res = dict(events=int(sel.sum()),
                   SS=float(((n_s2 == 1) & ~gx & sel).sum() / k),
                   MS=float(((n_s2 > 1) & ~gx & sel).sum() / k),
                   gamma_X=float((gx & sel).sum() / k),
                   with_above_gate_or_gas_cluster=float((fast & sel).sum() / k))
        for dz, m in merged.items():
            res[f"SS_dz{dz * 10:g}mm"] = float(((m == 1) & ~gx & sel).sum() / k)
        return res
    return dict(drift=fr(has_drift), photopeak=fr(has_drift & peak),
                clusters_per_drift_event=float(n_s2[has_drift].mean()),
                n_drift=n_s2, has_drift=has_drift, peak=peak, gx=gx, fast=fast, ev=ev)


# ---------------------------------------------------------------- 3. sensitivity
def sensitivity():
    scans = [("lineage", "time_threshold", [1, 10, 100, 1000], "ns"),
             ("lineage", "gamma_distance_threshold", [0.0, 0.05, 0.2, 0.5], "cm"),
             ("dbscan", "micro_separation", [0.005, 0.05, 0.1, 0.3], "cm")]
    out = []
    for clus, opt, vals, unit in scans:
        for v in vals:
            res = resolve(RUN)
            res.run["physics"] = {**(res.run.get("physics") or {}), "clustering": clus}
            st, rid = _context_for(res, entry_stop=SENS_EVENTS, **{opt: v})
            k = classify(load_clusters(st, rid))
            out.append(dict(clustering=clus, option=opt, value=v, unit=unit,
                            clusters_per_drift_event=round(k["clusters_per_drift_event"], 3),
                            **{f"photopeak_{a}": round(b, 4) for a, b in k["photopeak"].items() if a != "events"},
                            photopeak_events=k["photopeak"]["events"]))
            print(f"  {clus:7s} {opt:24s} {v:>7g} {unit:2s}  clusters/evt {out[-1]['clusters_per_drift_event']:.2f}  "
                  f"peak SS {out[-1]['photopeak_SS']:.3f}  SS(3 mm) {out[-1]['photopeak_SS_dz3mm']:.3f}  "
                  f"gX {out[-1]['photopeak_gamma_X']:.3f}")
    return out


def _context_for(res, **overrides):
    """chain.context for a modified Resolved (sensitivity scans change physics.clustering)."""
    import strax
    cfg = chain.settings(res, chain.g4_dir(res))      # clustering options follow res.run["physics"]
    cfg.update(overrides)
    st = strax.Context(storage=[strax.DataDirectory(str(chain.STORE))],
                       register=chain.plugins(res.run["physics"]["clustering"]), config=cfg)
    st.set_context_config({"check_available": ()})
    return st, res.run_key()


# ---------------------------------------------------------------- 4. yields vs standalone nestpy
def yields(st, rid, density, n=3000):
    import nestpy
    plug = st.get_single_plugin(rid, "quanta")
    nc = nestpy.NESTcalc(nestpy.VDetector())
    rows = []
    for model, name in ((8, "beta"), (7, "gamma")):
        for f in (100.0, 145.0, 500.0):
            q = np.array([plug.get_quanta(E_PEAK, model, f, 0, 0, True, density) for _ in range(n)], float)
            y = nc.GetYields(interaction=nestpy.INTERACTION_TYPE(model), energy=E_PEAK, drift_field=f, density=density)
            rows.append(dict(model=name, field_V_cm=f,
                             fuse_photons=round(q[:, 0].mean(), 1), fuse_photons_err=round(q[:, 0].std() / np.sqrt(n), 1),
                             fuse_electrons=round(q[:, 1].mean(), 1), fuse_electrons_err=round(q[:, 1].std() / np.sqrt(n), 1),
                             nestpy_photons=round(y.PhotonYield, 1), nestpy_electrons=round(y.ElectronYield, 1),
                             fuse_photons_sd=round(q[:, 0].std(), 1), fuse_electrons_sd=round(q[:, 1].std(), 1),
                             corr=round(float(np.corrcoef(q[:, 0], q[:, 1])[0, 1]), 3)))
            r = rows[-1]
            print(f"  {name:5s} {f:5.0f} V/cm  photons fuse {r['fuse_photons']:8.1f} ± {r['fuse_photons_err']:4.1f} "
                  f"nestpy {r['nestpy_photons']:8.1f}   electrons fuse {r['fuse_electrons']:8.1f} ± "
                  f"{r['fuse_electrons_err']:4.1f} nestpy {r['nestpy_electrons']:8.1f}   corr {r['corr']}")
    return rows


# ---------------------------------------------------------------- 5. anticorrelation
def anticorrelation(st, rid, k):
    s = st.get_array(rid, "microphysics_summary")
    s = s[(s["vol_id"] == 1) & (s["ed"] > E_MIN)]      # events with drift-region clusters only (below)
    ev = k["ev"]
    sel_ev = ev[k["has_drift"] & k["peak"] & ~k["gx"] & ~k["fast"]]
    m = np.isin(s["eventid"], sel_ev)
    s = s[m]
    u, idx = np.unique(s["eventid"], return_inverse=True)
    ph = np.bincount(idx, weights=s["photons"])
    el = np.bincount(idx, weights=s["electrons"])
    ncl = np.bincount(idx)
    fld = np.bincount(idx, weights=s["e_field"] * s["ed"]) / np.bincount(idx, weights=s["ed"])
    return dict(ph=ph, el=el, ncl=ncl, field=fld)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = resolve(RUN)
    density = res.materials["materials"]["liquid_xenon"]["density_g_cm3"]
    summ = {"run": RUN.name, "state": res.state_name, "run_key": res.run_key(),
            "physics": chain.physics(res), "volumes_cm": chain.volumes(res)}

    print("1. raw deposits per region")
    summ["regions"] = regions(res)
    for k, v in summ["regions"].items():
        if not k.startswith("_"):
            print(f"  {k:28s} energy {v['energy_fraction']:.3f}  events {v['events']}")

    print("2. clusters and event classes (full run)")
    st, rid = chain.context(RUN)
    k = classify(load_clusters(st, rid))
    summ["classes"] = {a: k[a] for a in ("drift", "photopeak", "clusters_per_drift_event")}
    print(f"  {json.dumps(summ['classes'], indent=1)}")

    print("3. sensitivity (first %d decays)" % SENS_EVENTS)
    summ["sensitivity"] = sensitivity()

    print("4. yields vs nestpy (662 keV)")
    summ["yields"] = yields(st, rid, density)

    print("5. anticorrelation")
    a = anticorrelation(st, rid, k)
    ss = a["ncl"] == 1
    summ["anticorrelation"] = dict(
        events=int(len(a["ph"])), single_cluster=int(ss.sum()),
        corr_all=round(float(np.corrcoef(a["ph"], a["el"])[0, 1]), 3),
        corr_single_cluster=round(float(np.corrcoef(a["ph"][ss], a["el"][ss])[0, 1]), 3),
        photons_mean_single=round(float(a["ph"][ss].mean()), 1), electrons_mean_single=round(float(a["el"][ss].mean()), 1),
        photons_mean_multi=round(float(a["ph"][~ss].mean()), 1), electrons_mean_multi=round(float(a["el"][~ss].mean()), 1),
        sum_quanta_sd_over_mean=round(float((a["ph"] + a["el"]).std() / (a["ph"] + a["el"]).mean()), 4),
        photons_sd_over_mean=round(float(a["ph"].std() / a["ph"].mean()), 4),
        electrons_sd_over_mean=round(float(a["el"].std() / a["el"].mean()), 4),
        field_median_V_cm=round(float(np.median(a["field"])), 1))
    print(f"  {summ['anticorrelation']}")

    # ------------------------------------------------------------ figure
    fig, ax = plt.subplots(2, 2, figsize=(12, 9.5))
    # (a) regions
    names = [n for n in summ["regions"] if not n.startswith("_")]
    ax[0, 0].barh(names, [summ["regions"][n]["energy_fraction"] for n in names], color="tab:blue")
    ax[0, 0].set_xlabel("fraction of the energy deposited in xenon")
    ax[0, 0].set_title("Geant4 deposits per region (outside the field cage: not simulated)")
    ax[0, 0].invert_yaxis()
    # (b) cluster multiplicity
    nd = k["n_drift"][k["has_drift"]]
    pk = k["n_drift"][k["has_drift"] & k["peak"]]
    b = np.arange(0.5, 12.5)
    ax[0, 1].hist(nd, bins=b, histtype="step", density=True, label=f"energy in drift region ({len(nd)} events)")
    ax[0, 1].hist(pk, bins=b, histtype="step", density=True, label=f"photopeak ({len(pk)} events)")
    ax[0, 1].set_yscale("log")
    ax[0, 1].set_xlabel("clusters with electrons per event (drift, above gate, gas; lineage)")
    ax[0, 1].set_ylabel("fraction of events")
    p = summ["classes"]["photopeak"]
    ax[0, 1].set_title(f"photopeak: SS {p['SS']:.2f}, MS {p['MS']:.2f}, γ-X {p['gamma_X']:.2f}; "
                       f"SS(dz<3 mm merged) {p['SS_dz3mm']:.2f}", fontsize=10)
    ax[0, 1].legend()
    # (c) sensitivity
    for (clus, opt), mk in zip({(r["clustering"], r["option"]) for r in summ["sensitivity"]}, "osd"):
        rows = [r for r in summ["sensitivity"] if r["clustering"] == clus and r["option"] == opt]
        x = np.arange(len(rows))
        ax[1, 0].plot(x, [r["photopeak_SS"] for r in rows], mk + "-", label=f"{clus}: {opt} (SS)")
        ax[1, 0].plot(x, [r["photopeak_SS_dz3mm"] for r in rows], mk + "--", alpha=0.6, label=f"{clus}: {opt} (SS, 3 mm)")
        for xi, r in zip(x, rows):
            ax[1, 0].annotate(f"{r['value']:g}", (xi, r["photopeak_SS"]), fontsize=7, xytext=(3, 3),
                              textcoords="offset points")
    ax[1, 0].set_xticks(range(4))
    ax[1, 0].set_xticklabels(["1st", "2nd", "3rd", "4th"])
    ax[1, 0].set_xlabel("setting (values annotated; ns / cm)")
    ax[1, 0].set_ylabel("photopeak single-scatter fraction")
    ax[1, 0].set_title(f"clustering sensitivity (first {SENS_EVENTS:.0e} decays)")
    ax[1, 0].legend(fontsize=7)
    # (d) anticorrelation
    ax[1, 1].scatter(a["el"][~ss], a["ph"][~ss], s=2, alpha=0.3, label="photopeak, several drift clusters")
    ax[1, 1].scatter(a["el"][ss], a["ph"][ss], s=2, alpha=0.3, label="photopeak, one drift cluster")
    ax[1, 1].set_xlabel("electrons")
    ax[1, 1].set_ylabel("photons")
    ac = summ["anticorrelation"]
    ax[1, 1].set_title(f"662 keV, {ac['field_median_V_cm']:.0f} V/cm: corr {ac['corr_all']:.2f}; "
                       f"σ/μ ph {ac['photons_sd_over_mean']:.3f}, e {ac['electrons_sd_over_mean']:.3f}, "
                       f"sum {ac['sum_quanta_sd_over_mean']:.3f}", fontsize=10)
    ax[1, 1].legend(markerscale=4)
    fig.suptitle(f"S3 micro-physics check — {RUN.stem}, state {res.state_name}")
    fig.tight_layout()
    fig.savefig(OUT / "s3_microphysics.png", dpi=130)
    with open(OUT / "summary.json", "w") as f:
        json.dump(summ, f, indent=1)
    print("written", OUT)


if __name__ == "__main__":
    main()
