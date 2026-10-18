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


def flat_map(path, ez=-145.0, ex=0.0):
    """Synthetic 3D field map file (V/cm): uniform Ez, Ex growing with x."""
    x = np.linspace(-36, 36, 13)
    z = np.linspace(-65, 23, 23)
    X, _, _ = np.meshgrid(x, x, z, indexing="ij")
    f = np.zeros(X.shape, np.float32)
    np.savez(path, x=x, y=x, z=z, V=f, Ex=(ex * X / 36.0).astype(np.float32), Ey=f, Ez=f + ez)
    return path


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
    assert v["z_gate_cm"] == 0 and v["z_cathode_cm"] == pytest.approx(-5.18)
    assert v["r_field_cage_cm"] == pytest.approx(3.1)
    assert v["z_liquid_cm"] == pytest.approx(res.state["liquid_level_mm"] / 10)
    assert chain.physics(res)["clustering"] == "lineage"
    res.run["physics"] = {"clustering": "lineage", "bogus": 1}
    with pytest.raises(ConfigError):
        chain.physics(res)


def test_chain_end_to_end(tmp_path):
    pytest.importorskip("fuse")
    write_g4(tmp_path / "g4", ROWS, 6)
    st, rid = chain.context(config.ROOT / "config" / "runs" / "cs137_cmb50_001.yaml", g4_out=tmp_path / "g4",
                            store=tmp_path / "strax", xams_efield_map=str(flat_map(tmp_path / "f.npz")))
    s = st.get_array(rid, "microphysics_summary")
    assert set(s["eventid"]) == {0, 1, 2, 3, 4}                                # event 5: outside the field cage, dropped
    vol = dict(zip(s["eventid"], s["vol_id"]))
    assert sorted(s["vol_id"]) == [1, 1, 1, 2, 3, 4] and vol[3] == 4 and vol[4] == 3
    assert s[s["vol_id"] == 3]["xe_density"][0] < 0.1                          # gas density
    assert np.all(s[np.isin(s["vol_id"], [3, 4])]["electrons"] > 0)            # electrons kept above the gate and in gas
    assert np.allclose(s["e_field"], 145.0)
    drift = s[s["vol_id"] == 1]
    assert np.all(drift["electrons"] > 0) and np.all(drift["photons"] > 0)
    assert s[s["vol_id"] == 2]["electrons"][0] == 0                            # no S2 below the cathode
