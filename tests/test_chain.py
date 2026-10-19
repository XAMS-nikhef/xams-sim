"""S3: input plugin, field-map export, chain settings, and a small end-to-end run through fuse."""
import json

import numpy as np
import pytest

from xamssim import chain, config, fieldmap
from xamssim.config import ConfigError

DDT = [("event", "<i4"), ("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("t", "<f8"), ("edep", "<f4"), ("particle", "<i2"),
       ("parent_particle", "<i2"), ("track", "<i4"), ("parent", "<i4"), ("creaproc", "<i2"), ("edproc", "<i2"), ("volume", "<i2")]
EDT = [("event", "<i4"), ("x_pri", "<f4"), ("y_pri", "<f4"), ("z_pri", "<f4"), ("n_deposits", "<i4"), ("edep_lxe", "<f4"),
       ("edep_gxe", "<f4")]
PARTICLES = ["none", "Cs137", "e-", "gamma"]
PROCESSES = ["primary", "RadioactiveDecay", "compt", "phot", "eIoni"]


def write_g4(path, rows, n_events):
    """rows: (event, x, y, z [mm], t, edep, particle, parent_particle, track, parent, creaproc, edproc)."""
    d = np.zeros(len(rows), dtype=DDT)
    for i, r in enumerate(rows):
        for k, v in zip([n for n, _ in DDT[:12]], r):
            d[k][i] = v
    e = np.zeros(n_events, dtype=EDT)
    e["event"] = np.arange(n_events)
    e["y_pri"], e["z_pri"] = 130.0, -26.0
    e["n_deposits"] = np.bincount(d["event"], minlength=n_events)
    path.mkdir(parents=True, exist_ok=True)
    d.tofile(path / "deposits.bin")
    e.tofile(path / "deposits.events.bin")
    h = {"deposit_dtype": DDT, "event_dtype": EDT, "deposit_record_bytes": 46, "event_record_bytes": 28,
         "files": {}, "codes": {"particle": PARTICLES, "process": PROCESSES},
         "counts": {"deposits": len(d), "events": n_events}}
    (path / "deposits.json").write_text(json.dumps(h))


# photo-absorption in the drift region (event 0), Compton + photo-absorption (event 1), deposit below the cathode (event 2),
# liquid between gate and surface (event 3, z = 2 mm), gas (event 4, z = 6 mm), outside the field cage (event 5, r = 40 mm)
ROWS = [(3, 3.0, 0.0, 2.0, 0.0, 100.0, 2, 3, 2, 1, 3, 4), (4, 0.0, 3.0, 6.0, 0.0, 50.0, 2, 3, 2, 1, 3, 4),
        (5, 40.0, 0.0, -20.0, 0.0, 200.0, 2, 3, 2, 1, 3, 4),
        (1, -8.0, 2.0, -12.0, 0.0, 180.0, 2, 3, 2, 1, 2, 4), (1, 10.0, -6.0, -40.0, 0.1, 481.7, 2, 3, 3, 1, 3, 4),
        (0, 5.0, 3.0, -25.0, 0.0, 661.7, 2, 3, 2, 1, 3, 4), (2, 0.0, 0.0, -56.0, 0.0, 300.0, 2, 1, 2, 1, 1, 4)]


def test_deposits_frame(tmp_path):
    from xamssim.plugins.input import deposits_frame
    write_g4(tmp_path / "g4", ROWS, 6)
    df, n = deposits_frame(tmp_path / "g4" / "deposits")
    assert n == 6 and list(df["eventid"]) == [0, 1, 1, 2, 3, 4, 5]             # sorted by event
    assert df["x"].iloc[0] == pytest.approx(0.5) and df["z"].iloc[0] == pytest.approx(-2.5)   # mm -> cm
    assert df["y_pri"].iloc[0] == pytest.approx(13.0)
    assert list(df["creaproc"])[:4] == ["phot", "compt", "phot", "RadioactiveDecayBase"]   # Geant4 11 name -> fuse's
    assert set(df["type"]) == {"e-"} and list(df["parenttype"])[:3] == ["gamma"] * 3
    assert df["trackid"].dtype == np.int32
    df2, _ = deposits_frame(tmp_path / "g4" / "deposits", entry_start=1, entry_stop=2)
    assert list(df2["eventid"]) == [1, 1]


def flat_map(path, ez=-145.0, ex=0.0, reverse_below=None):
    """Synthetic 3D field map file (V/cm): uniform Ez (optionally reversed below z = reverse_below mm), Ex ∝ x."""
    x = np.linspace(-36, 36, 13)
    z = np.linspace(-65, 23, 89)
    X, _, Z = np.meshgrid(x, x, z, indexing="ij")
    f = np.zeros(X.shape, np.float32)
    ezz = np.full(X.shape, ez, np.float32)
    if reverse_below is not None:
        ezz[Z < reverse_below] = -ez
    np.savez(path, x=x, y=x, z=z, V=f, Ex=(ex * X / 36.0).astype(np.float32), Ey=f, Ez=ezz)
    return path


def uniform_cells(path, geo, ez_gate=-145.0, ez_cathode=-145.0):
    """Synthetic mesh-cell fields without hole structure (uniform Ez): the composite field must equal the full field."""
    data = {}
    u = np.linspace(0, geo["pitch"] / 2, 14)
    for name, ez, (z0, z1) in (("gate", ez_gate, (-3.2, 3.98)), ("cathode", ez_cathode, (-3.6, 3.6))):
        z = np.linspace(z0, z1, 37)
        shape = (len(u), len(u), len(z))
        data.update({f"{name}_u": u, f"{name}_z": z, f"{name}_Ex": np.zeros(shape, np.float32),
                     f"{name}_Ey": np.zeros(shape, np.float32), f"{name}_Ez": np.full(shape, ez, np.float32),
                     f"{name}_mean": np.stack([np.zeros(len(z)), np.zeros(len(z)), np.full(len(z), ez)]).astype(np.float32)})
    np.savez(path, **data)
    return path


def test_composite_field(tmp_path):
    from xamssim import driftmap
    res = config.resolve(config.ROOT / "config" / "runs" / "cs137_cmb50_001.yaml")
    geo = driftmap.geometry_numbers(res)
    full = flat_map(tmp_path / "f.npz", ex=50.0)
    comp = driftmap._Composite(full, uniform_cells(tmp_path / "c.npz", geo), geo)
    plain = driftmap._Field(full)
    p = np.array([[1.0, 2.0, -0.4], [5.0, -3.0, -51.5], [10.0, 4.0, 1.5], [0.0, 0.0, -25.0]])
    assert np.allclose(comp(p), plain(p), atol=1e-3)                       # no hole structure -> the full field
    cell = comp.cells[0]                                                    # gate
    a, pt = geo["meshes"]["gate"]["angle"], geo["pitch"]
    def world(u, v, zl):                                                     # cell coordinates of hole (0, 0) -> world
        xm, ym = u + 0.5 * pt, v + 0.5 * pt
        return np.array([[np.cos(a) * xm - np.sin(a) * ym, np.sin(a) * xm + np.cos(a) * ym, geo["meshes"]["gate"]["z"] + zl]])
    assert not comp.on_bar(world(0.0, 0.0, 0.0))[0]                         # hole centre: free
    assert comp.on_bar(world(1.29, 0.0, 0.0))[0]                            # on the bar between two holes
    assert not comp.on_bar(world(1.29, 0.0, 0.5))[0]                        # above the foil
    u, v, zl, etched = cell.local(world(0.3, -0.2, 0.1))
    assert u[0] == pytest.approx(0.3) and v[0] == pytest.approx(-0.2) and etched[0]


def uniform_stack(e_liq=-3920.0, e_gas=-7600.0):
    """Synthetic gate + anode cell as xamssim.cellmap.read_cell returns it: uniform Ez [V/cm], liquid below z = 4 mm."""
    u = np.linspace(0, 1.3, 27)
    z = np.round(np.arange(3.4, 12.0 + 1e-9, 0.02), 4)
    ez = np.broadcast_to(np.where(z < 4.0, e_liq, e_gas), (len(u), len(u), len(z))).astype(np.float32)
    zero = np.zeros_like(ez)
    return dict(u=u, z=z, Ex=zero, Ey=zero, Ez=ez)


def test_el_map():
    from xamssim import elmap
    res = config.resolve(config.ROOT / "config" / "runs" / "cs137_cmb50_001.yaml")
    d = elmap.compute(res, cell=uniform_stack(), log=lambda *a: None)
    gm = elmap.gas_model(res)
    # at the hole centre the electron goes straight up through the anode hole to the top of the cell
    path = d["path_mm"][0, 0]
    assert d["end"][0, 0] == 2 and path == pytest.approx(12.0 - 4.01, abs=0.05)
    assert d["n_el"][0, 0] == pytest.approx((140 * 7.6 - 116 * gm["p_eq"]) * path / 10, rel=0.01)
    assert d["t_transit_us"][0, 0] == pytest.approx(path / gm["v_gas"], rel=0.01)
    q = d["t_q_us"][0, 0]
    assert np.all(np.diff(q) > 0) and q[9] == pytest.approx(0.5 * d["t_transit_us"][0, 0], rel=0.02)   # uniform light
    et, ee = elmap.extraction_table()
    assert d["ext_eff"][0, 0] == pytest.approx(np.interp(3.92 * gm["eps_ratio"], et, ee, left=0.0), rel=1e-6)
    assert d["end"][-1, 0] == 1                                            # under a bar: ends on the anode bar


def drift_map(tmp_path, res):
    """Coarse drift map of the synthetic field (drift region field 145 V/cm, reversed below the cathode)."""
    from xamssim import driftmap
    d = driftmap.compute(res, field_file=flat_map(tmp_path / "fd.npz", reverse_below=-51.8), cells_file=None,
                         dxy=2.0, dz=1.0, log=lambda *a: None)
    p = tmp_path / "drift.npz"
    np.savez(p, **d)
    return p, d


def test_drift_map(tmp_path):
    from xamssim import driftmap
    res = config.resolve(config.ROOT / "config" / "runs" / "cs137_cmb50_001.yaml")
    p, d = drift_map(tmp_path, res)
    m = driftmap.DriftMap(p)
    v = np.interp(145.0, *driftmap.velocity_table(res))                     # mm/µs
    t = m.at(0.0, 0.0, -40.0)["t_us"]
    assert t == pytest.approx((4.0 + 40.0) / v, rel=0.02)                   # straight up to the surface (level 4 mm)
    assert m(0.0, 0.0, -40.0, "end") == driftmap.SURFACE and m(0.0, 0.0, -40.0, "crossed")
    assert m(0.0, 0.0, 2.0, "end") == driftmap.SURFACE and not m(0.0, 0.0, 2.0, "crossed")   # above the gate
    assert m(0.0, 0.0, -56.0, "end") == driftmap.BOTTOM                    # below the cathode: down
    assert m(0.0, 0.0, 6.0, "end") == driftmap.GAS
    # a radial field pushes electrons from large radius into the wall
    pw = driftmap.compute(res, field_file=flat_map(tmp_path / "fw.npz", ex=-300.0), cells_file=None, dxy=2.0, dz=1.0,
                          log=lambda *a: None)
    xs, zs = pw["x"], pw["z"]
    assert pw["end"][np.argmin(abs(xs - 28)), np.argmin(abs(xs)), np.argmin(abs(zs + 40))] in (driftmap.WALL, driftmap.SIPM)


def test_g4_output_hash(tmp_path):
    import shutil
    from xamssim import g4io
    write_g4(tmp_path / "a", ROWS, 6)
    h = json.loads((tmp_path / "a" / "deposits.json").read_text())
    h["files"] = {"deposits": str(tmp_path / "a" / "deposits.bin")}
    h["info"] = {"config_json": json.dumps({"seed": 1, "xamssim": {"run": "/abs/path/run.yaml", "n_events": 6}}),
                 "config": str(tmp_path / "a" / "config.json")}
    (tmp_path / "a" / "deposits.json").write_text(json.dumps(h))
    shutil.copytree(tmp_path / "a", tmp_path / "moved")
    h2 = json.loads((tmp_path / "moved" / "deposits.json").read_text())
    h2["files"] = {"deposits": "/elsewhere/deposits.bin"}
    h2["info"]["config"] = "/elsewhere/config.json"
    (tmp_path / "moved" / "deposits.json").write_text(json.dumps(h2))
    assert g4io.output_hash(tmp_path / "a") == g4io.output_hash(tmp_path / "moved")      # paths do not count
    h2["info"]["config_json"] = json.dumps({"seed": 2, "xamssim": {"run": "/abs/path/run.yaml", "n_events": 6}})
    (tmp_path / "moved" / "deposits.json").write_text(json.dumps(h2))
    assert g4io.output_hash(tmp_path / "a") != g4io.output_hash(tmp_path / "moved")      # content does


def test_fieldmap_3d(tmp_path):
    m = fieldmap.FieldMap(flat_map(tmp_path / "f.npz", ez=-145.0, ex=100.0))
    assert m(0, 0, -25)[0] == pytest.approx(145.0)
    assert m(36, 0, -25)[0] == pytest.approx(np.hypot(145.0, 100.0), rel=1e-5)
    assert m(18, 5, -25, "Ex")[0] == pytest.approx(50.0, rel=1e-5)            # x matters, not only r
    assert m(-18, 5, -25, "Ex")[0] == pytest.approx(-50.0, rel=1e-5)
    assert m(100, 0, -200)[0] == pytest.approx(m(36, 0, -65)[0])               # outside: grid edge
    x, y, z = fieldmap.grid_axes(config.load_yaml(config.ROOT / "config" / "geometry.yaml"))
    assert x[0] == -36 and z[0] == pytest.approx(-64.1) and z[-1] <= 22.5


def test_volumes_and_physics():
    res = config.resolve(config.ROOT / "config" / "runs" / "cs137_cmb50_001.yaml")
    v = chain.volumes(res)
    assert set(v) == {"z_liquid_cm", "r_field_cage_cm"} and v["r_field_cage_cm"] == pytest.approx(3.1)
    assert v["z_liquid_cm"] == pytest.approx(res.state["liquid_level_mm"] / 10)
    assert chain.physics(res)["clustering"] == "lineage"
    res.run["physics"] = {"clustering": "lineage", "bogus": 1}
    with pytest.raises(ConfigError):
        chain.physics(res)


def test_chain_end_to_end(tmp_path):
    pytest.importorskip("fuse")
    write_g4(tmp_path / "g4", ROWS, 6)
    run = config.ROOT / "config" / "runs" / "cs137_cmb50_001.yaml"
    dpath, _ = drift_map(tmp_path, config.resolve(run))
    st, rid = chain.context(run, g4_out=tmp_path / "g4", store=tmp_path / "strax",
                            xams_efield_map=str(flat_map(tmp_path / "f.npz")), xams_drift_map=str(dpath),
                            electron_lifetime_us=300.0)                  # cmb50: lifetime not measured yet
    s = st.get_array(rid, "microphysics_summary")
    assert set(s["eventid"]) == {0, 1, 2, 3, 4}                                # event 5: outside the field cage, dropped
    vol = dict(zip(s["eventid"], s["vol_id"]))
    assert sorted(s["vol_id"]) == [1, 1, 1, 2, 3, 4] and vol[3] == 4 and vol[4] == 3
    assert s[s["vol_id"] == 3]["xe_density"][0] < 0.1                          # gas density
    assert np.all(s[np.isin(s["vol_id"], [3, 4])]["electrons"] > 0)            # electrons kept above the gate and in gas
    assert np.allclose(s["e_field"], 145.0)
    drift = s[s["vol_id"] == 1]
    assert np.all(drift["electrons"] > 0) and np.all(drift["photons"] > 0)
    # drift: electrons below the cathode go down (none at the surface); drift region: exp(-t / tau) survive
    dr = st.get_array(rid, "drifted_electrons")
    assert dr[s["vol_id"] == 2]["n_electron_interface"][0] == 0 and dr[s["vol_id"] == 2]["survival"][0] == 0
    tau = 300.0
    i = np.flatnonzero(s["vol_id"] == 1)[0]
    assert dr["survival"][i] == pytest.approx(np.exp(-dr["drift_time_mean"][i] / 1e3 / tau), rel=1e-3)
    assert 0 < dr["n_electron_interface"][i] <= s["electrons"][i]
    assert dr["drift_time_spread"][i] > 0
    # extraction and EL with a synthetic EL map
    from xamssim import elmap
    elp = tmp_path / "el.npz"
    np.savez(elp, **elmap.compute(config.resolve(run), cell=uniform_stack(), log=lambda *a: None))
    st3, _ = chain.context(run, g4_out=tmp_path / "g4", store=tmp_path / "strax",
                           xams_efield_map=str(flat_map(tmp_path / "f.npz")), xams_drift_map=str(dpath),
                           electron_lifetime_us=300.0, xams_el_map=str(elp))
    ex = st3.get_array(rid, "extracted_electrons")
    dr3 = st3.get_array(rid, "drifted_electrons")
    assert np.all(ex["n_electron_extracted"] <= dr3["n_electron_interface"])
    k = np.flatnonzero(dr3["n_electron_interface"] > 100)
    assert np.all(ex["n_s2_photons"][k] > 0) and np.all(ex["s2_width50"][k] > 0)
    # new Geant4 output for the same run file -> new lineage of everything downstream (not reused)
    key = st.key_for(rid, "clustered_interactions").lineage_hash
    write_g4(tmp_path / "g4", ROWS[:-1], 6)
    st2, _ = chain.context(run, g4_out=tmp_path / "g4", store=tmp_path / "strax",
                           xams_efield_map=str(flat_map(tmp_path / "f.npz")), xams_drift_map=str(dpath),
                           electron_lifetime_us=300.0)
    assert st2.key_for(rid, "clustered_interactions").lineage_hash != key
