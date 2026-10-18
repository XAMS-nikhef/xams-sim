"""Tests of the xams-sim configuration: every run and state resolves, map keys behave as input hashes."""
import copy
from pathlib import Path

import pytest

from xamssim import config, maps

RUNS = sorted((config.CONFIG / "runs").glob("*.yaml"))
STATES = sorted(p.stem for p in (config.CONFIG / "states").glob("*.yaml"))


@pytest.mark.parametrize("run", RUNS, ids=lambda p: p.stem)
def test_runs_resolve(run):
    res = config.resolve(run)
    assert set(res.map_keys()) == set(maps.KINDS)
    assert len(res.run_key()) == 12


@pytest.mark.parametrize("state", STATES)
def test_states_resolve(state):
    res = config.resolve_state(state)
    assert res.hv_case["G"] is not None


def test_keys_depend_only_on_their_inputs():
    a = config.resolve(RUNS[0])
    b = copy.deepcopy(a)
    b.hv_case = {**b.hv_case, "BS": b.hv_case["BS"] - 100}           # bottom screen: field yes, light maps no
    ka, kb = a.map_keys(), b.map_keys()
    assert ka["field"] != kb["field"] and ka["drift"] != kb["drift"]
    assert ka["s1_light"] == kb["s1_light"] and ka["s2_pattern"] == kb["s2_pattern"]
    assert ka["extraction_el"] == kb["extraction_el"]
    c = copy.deepcopy(a)
    c.materials["optics"]["lxe"]["rayleigh_length_cm"] = [99, 100]   # optics: light maps yes, field no
    kc = c.map_keys()
    assert kc["s1_light"] != ka["s1_light"] and kc["field"] == ka["field"]


def test_bad_run_rejected(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text("state: cmb50\nsource: cs137_raised\nn_events: 10\nseed: 1\nstop_after: banana\n")
    with pytest.raises(config.ConfigError):
        config.resolve(p)
    p.write_text("state: nosuchstate\nsource: cs137_raised\nn_events: 10\nseed: 1\n")
    with pytest.raises(config.ConfigError):
        config.resolve(p)
    p.write_text("state: cmb50\nsource: cs137_raised\nn_events: 10\nseed: 1\nextra: 3\n")
    with pytest.raises(config.ConfigError):
        config.resolve(p)


def test_needed_maps_follow_stop_after():
    assert maps.needed("geant4_interactions") == []
    assert maps.needed("quanta") == ["field", "drift", "mesh_cells"]
    assert set(maps.needed("raw_records")) == set(maps.KINDS)


def test_register_and_find(tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "MAPS", tmp_path)
    monkeypatch.setattr(maps, "MANIFEST", tmp_path / "manifest.json")
    res = config.resolve(RUNS[0])
    (tmp_path / "field").mkdir()
    (tmp_path / "field" / "f.npz").write_bytes(b"x")
    maps.register(res, "field", ["field/f.npz"], producer_version="test")
    rows = {r["kind"]: r for r in maps.status(res)}
    assert rows["field"]["present"] and not rows["drift"]["present"]


def test_materials_single_source():
    geo, mat = config.load_materials_and_geometry()
    assert "optics" not in geo and "optics" in mat
    for part in ("mesh_common", "field_shaping_rings", "cryostat_vessel", "ptfe_cylinder", "ptfe_bucket", "pmt_ptfe"):
        assert geo[part]["material"] in mat["materials"]
    lxe = mat["materials"]["liquid_xenon"]
    assert lxe["density_g_cm3"] == pytest.approx(2.8748) and lxe["temperature_k"] == 175.0
