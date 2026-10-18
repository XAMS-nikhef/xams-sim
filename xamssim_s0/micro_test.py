"""S0: run the fuse micro-physics chain offline with XAMS settings (synthetic Cs-137-like events, COMSOL CM-B field map)."""
import gzip, json, os, shutil, sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path  # noqa: E402
import numpy as np, pandas as pd, strax, straxen, fuse, nestpy  # noqa: E401,E402

# usage: python micro_test.py <work dir> [dbscan|lineage]   (work dir receives the map, the CSV and strax data)
OUT = os.path.abspath(sys.argv[1])
CLUSTERING = sys.argv[2] if len(sys.argv) > 2 else "lineage"
os.makedirs(OUT, exist_ok=True)
# 1. field map: COMSOL (r, z) plane of the CM-B case (-50 V margin), r >= 0 side, mm -> cm, V/m -> V/cm
M = np.load(Path(__file__).resolve().parents[1] / "results" / "efield" / "comsol" / "maps_rz.npz")
r, z = M["r"], M["z"]
k = r >= 0
E = np.hypot(M["cmb50_Er"], M["cmb50_Ez"])[k] / 100
E = np.nan_to_num(E)
fmap = {"coordinate_system": [["r", [float(r[k][0] / 10), float(r[k][-1] / 10), int(k.sum())]],
                              ["z", [float(z[0] / 10), float(z[-1] / 10), len(z)]]],
        "map": E.tolist(), "description": "XAMS COMSOL cmb50, |E| in V/cm, r/z in cm"}
mpath = os.path.join(OUT, "xams_efield_cmb50.json.gz")
with gzip.open(mpath, "wt") as f:
    json.dump(fmap, f)

# 2. synthetic events (mm, ns, keV)
rows = []
def steps(ev, trk, parent, ptype, crea, x0, y0, z0, etot, n=6, spread=0.3, t0=0.0):
    rng = np.random.default_rng(ev * 100 + trk)
    for i in range(n):
        d = rng.normal(0, spread, 3)
        rows.append(dict(eventid=ev, xp=x0 + d[0], yp=y0 + d[1], zp=z0 + d[2], time=t0 + 0.01 * i, ed=etot / n, type="e-",
                         trackid=trk, parenttype=ptype, parentid=parent, creaproc=crea, edproc="eIoni",
                         xp_pri=0.0, yp_pri=200.0, zp_pri=-26.0))
steps(0, 2, 1, "gamma", "phot", 5.0, 3.0, -25.0, 662.0)                       # photo-absorption, drift region
steps(1, 2, 1, "gamma", "compt", -8.0, 2.0, -12.0, 180.0)                     # Compton + photo-absorption, 2 sites
steps(1, 3, 1, "gamma", "phot", 10.0, -6.0, -40.0, 482.0, t0=0.1)
steps(2, 2, 1, "gamma", "compt", 4.0, 4.0, -30.0, 300.0)                      # gamma-X: one site in the TPC,
steps(2, 3, 1, "gamma", "phot", 2.0, 0.0, -57.0, 362.0, t0=0.1)               #   one below the cathode
steps(3, 2, 1, "gamma", "phot", 0.0, 5.0, 6.0, 662.0)                         # in the gas gap
pd.DataFrame(rows).to_csv(os.path.join(OUT, "synthetic_cs137.csv"), index=False)

# 3. context: only fuse micro-physics plugins, every XENON default overridden
import yaml  # noqa: E402
MAT = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config" / "materials.yaml"))["materials"]
store = os.path.join(OUT, "strax_data")
shutil.rmtree(store, ignore_errors=True)
clus = ([fuse.micro_physics.LineageClustering, fuse.micro_physics.MergeLineage] if CLUSTERING == "lineage"
        else [fuse.micro_physics.FindCluster, fuse.micro_physics.MergeCluster])
plugins = [fuse.micro_physics.ChunkInput, *clus,
           fuse.micro_physics.VolumeProperties, fuse.micro_physics.cuts_and_selections.VolumeSelection,
           fuse.micro_physics.cuts_and_selections.DefaultSimulation, fuse.micro_physics.ElectricField,
           fuse.micro_physics.NestYields, fuse.micro_physics.MicroPhysicsSummary]
cfg = dict(
    path=OUT, file_name="synthetic_cs137.csv", source_rate=10, n_interactions_per_chunk=1e5,
    micro_separation=0.05, micro_separation_time=10, tag_cluster_by="energy",   # 0.05 mm (= epix 0.005 cm)
    efield_map=f"itp_map://resource://{mpath}?fmt=json.gz&method=RegularGridInterpolator",
    nest_er_yields_parameters=-1, nest_nr_yields_parameters=-1, nest_width_parameters={},
    # XAMS volumes (cm): drift region gate -> cathode, r < 3.1; below the cathode down to the bottom PMT window; gas
    xenonnt_z_gate_mesh=0.0, xenonnt_z_cathode=-5.18, xenonnt_sensitive_volume_radius=3.1,
    xenonnt_z_bottom_pmts=-6.41, xenonnt_z_lxe=0.4, xenonnt_z_top_pmts=2.25,
    xenon_density_tpc=MAT["liquid_xenon"]["density_g_cm3"], xenon_density_below_cathode=MAT["liquid_xenon"]["density_g_cm3"],
    xenon_density_gas_phase=MAT["gas_xenon"]["density_g_cm3"],                  # config/materials.yaml (single source)
)
st = strax.Context(storage=[strax.DataDirectory(store)], register=plugins, config=cfg)
st.set_context_config({"check_available": ()})
d = st.get_array(f"s0_{CLUSTERING}", "microphysics_summary")
cols = [c for c in ("eventid", "x", "y", "z", "ed", "nestid", "vol_id", "create_S2", "e_field", "photons", "electrons", "excitons")
        if c in d.dtype.names]
print(pd.DataFrame(d[cols]).round(3).to_string())
cl = st.get_array(f"s0_{CLUSTERING}", "clustered_interactions")
print(f"\n{len(cl)} clusters from {len(rows)} steps in 4 events; in ROI: {len(d)}")
# 4. compare with standalone nestpy at the same field
nc = nestpy.NESTcalc(nestpy.VDetector())
for row in d[:3]:
    y = nc.GetYields(interaction=nestpy.INTERACTION_TYPE(int(row["nestid"])), energy=float(row["ed"]),
                     drift_field=float(row["e_field"]), density=MAT["liquid_xenon"]["density_g_cm3"])
    print(f"standalone NEST (mean yields) E={row['ed']:.0f} keV F={row['e_field']:.0f} V/cm: photons {y.PhotonYield:.0f}, "
          f"electrons {y.ElectronYield:.0f}  | fuse (with fluctuations): {row['photons']}, {row['electrons']}")
