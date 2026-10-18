"""Tests of the Geant4 particle-mode helpers (no Geant4 run needed)."""
import json

import numpy as np
import pytest

from xamssim import config, g4bin, g4io, particle


def test_isotope_za():
    assert particle.isotope_za("Cs-137") == (55, 137)
    assert particle.isotope_za("Co60") == (27, 60)
    assert particle.isotope_za("Kr-83m") == (36, 83)
    with pytest.raises(config.ConfigError):
        particle.isotope_za("caesium")


def test_source_config():
    res = config.resolve(config.CONFIG / "runs" / "s2_cs137_raised.yaml")
    s = particle.source_config(res)
    assert s["type"] == "isotope" and (s["Z"], s["A"]) == (55, 137) and len(s["position_mm"]) == 3
    res.source = {**res.source, "position_mm": None}
    with pytest.raises(config.ConfigError):
        particle.source_config(res)
    res.source = {"isotope": "Cs-137", "type": "isotope", "position_mm": [0, 100, -26], "direction": "cone"}
    with pytest.raises(config.ConfigError):     # cone only for gamma sources
        particle.source_config(res)


def test_g4io_roundtrip(tmp_path):
    ddt = [("event", "<i4"), ("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("t", "<f8"), ("edep", "<f4"), ("particle", "<i2"),
           ("parent_particle", "<i2"), ("track", "<i4"), ("parent", "<i4"), ("creaproc", "<i2"), ("edproc", "<i2"), ("volume", "<i2")]
    edt = [("event", "<i4"), ("x_pri", "<f4"), ("y_pri", "<f4"), ("z_pri", "<f4"), ("n_deposits", "<i4"), ("edep_lxe", "<f4"), ("edep_gxe", "<f4")]
    d = np.zeros(3, dtype=ddt)
    d["event"], d["edep"], d["particle"] = [0, 0, 1], [100, 200, 662], [1, 1, 2]
    e = np.zeros(2, dtype=edt)
    e["event"], e["n_deposits"] = [0, 1], [2, 1]
    d.tofile(tmp_path / "deposits.bin")
    e.tofile(tmp_path / "deposits.events.bin")
    h = {"deposit_dtype": ddt, "event_dtype": edt, "deposit_record_bytes": np.dtype(ddt).itemsize,
         "event_record_bytes": np.dtype(edt).itemsize, "files": {"deposits": str(tmp_path / "deposits.bin")},
         "codes": {"particle": ["none", "e-", "gamma"]}, "counts": {"deposits": 3, "events": 2}}
    (tmp_path / "deposits.json").write_text(json.dumps(h))
    hh, dd, ee = g4io.read(tmp_path)
    assert len(dd) == 3 and len(ee) == 2 and dd["edep"].sum() == pytest.approx(962)
    assert list(g4io.names(hh, "particle", dd["particle"])) == ["e-", "e-", "gamma"]
    assert g4io.code(hh, "particle", "gamma") == 2 and g4io.code(hh, "particle", "alpha") == -1
    # the binary layout matches the C++ structs (packed): 46 and 28 bytes (as written by xamsg4)
    assert np.dtype(ddt).itemsize == 46 and np.dtype(edt).itemsize == 28


def test_g4bin_wraps_outside_g4_env(monkeypatch):
    if not g4bin.XAMSG4.exists():
        pytest.skip("xamsg4 not built")
    monkeypatch.delenv("G4LEDATA", raising=False)
    cmd = g4bin.command(["-m", "particle"])
    assert cmd[1:5] == ["run", "-n", g4bin.G4_ENV, "--no-capture-output"] and cmd[-2:] == ["-m", "particle"]
    assert cmd[5].endswith("/g4/build/xamsg4")
