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
    geo, mat = config.load_materials_and_geometry("xams2026")
    assert "optics" not in geo and "optics" in mat
    for part in ("mesh_common", "field_shaping_rings", "cryostat_vessel", "ptfe_cylinder", "ptfe_bucket", "pmt_ptfe"):
        assert geo[part]["material"] in mat["materials"]
    lxe = mat["materials"]["liquid_xenon"]
    assert lxe["density_g_cm3"] == pytest.approx(2.8748) and lxe["temperature_k"] == 175.0


def test_list_runs():
    """xamssim list: collects without error; a filter that matches nothing gives no runs, but the map overview."""
    from xamssim import listing
    d = listing.collect("no-such-run-id")
    assert d["runs"] == [] and "sept" in d["maps"]["states"]


def test_list_remove(tmp_path, monkeypatch):
    """xamssim list --delete: removes the old folders, refuses anything outside the data folder."""
    import pytest
    from xamssim import listing
    monkeypatch.setattr(listing, "DATA", tmp_path)
    old = tmp_path / "strax" / "run-x-abc"
    old.mkdir(parents=True)
    (old / "chunk").write_text("x")
    listing.remove([dict(kind="strax", path=old, size=1)])
    assert not old.exists()
    with pytest.raises(RuntimeError):
        listing.remove([dict(kind="strax", path=tmp_path.parent / "elsewhere", size=1)])


def test_particle_is_current(tmp_path):
    """xamssim particle skips Geant4 only for complete output with the same Geant4 key, events and seed."""
    import json
    from xamssim import particle
    res = config.resolve(config.ROOT / "config" / "runs" / "cs137_cmb50_001.yaml")
    assert not particle.is_current(res, tmp_path, 10, 1)                    # nothing there
    (tmp_path / "config.json").write_text(json.dumps({"xamssim": {"g4_key": res.g4_key(), "n_events": 10, "seed": 1}}))
    assert not particle.is_current(res, tmp_path, 10, 1)                    # incomplete: no deposits.json
    (tmp_path / "deposits.json").write_text(json.dumps({"counts": {"events": 10}}))
    assert particle.is_current(res, tmp_path, 10, 1)
    assert not particle.is_current(res, tmp_path, 20, 1) and not particle.is_current(res, tmp_path, 10, 2)


def test_list_run_pattern(monkeypatch):
    """--run: shell wildcards against the whole run id."""
    from xamssim import listing
    monkeypatch.setattr(listing, "strax_products", lambda: {"example_a": [], "example_b": [], "s4_x": []})
    monkeypatch.setattr(listing, "G4", config.DATA / "no-such-folder")
    ids = lambda p: [r["id"] for r in listing.collect(p)["runs"]]          # noqa: E731
    assert ids("example*") == ["example_a", "example_b"]
    assert ids("example") == [] and ids("example_a") == ["example_a"] and ids("*_?") == ["example_a", "example_b", "s4_x"]


def test_list_old_items_all():
    """--delete: only old data; --delete --all: everything of the selected runs, never maps."""
    from xamssim import listing
    d = {"runs": [{"g4": {"key": "a", "size": 1, "dir": "g"}, "g4_key_now": "a",
                   "products": [{"state": "current", "dir": "c", "size": 1}, {"state": "old", "dir": "o", "size": 1},
                                {"state": "?", "dir": "q", "size": 1}]}],
         "maps": {"old": [{"kind": "drift", "key": "k", "state": "s", "created": "", "size": 1, "files": ["drift/k/f"]}]}}
    assert sorted(str(i["path"]) for i in listing.old_items(d, maps=False)) == ["o"]
    assert sorted(str(i["path"]) for i in listing.old_items(d, maps=False, everything=True)) == ["c", "g", "o", "q"]
    assert any(i["kind"] == "map" for i in listing.old_items(d))


def test_detectors():
    """A state names its detector; the geometry comes from config/detectors/<detector>/ with its hole pattern read in;
    an unknown detector is an error."""
    import copy as _copy
    res = config.resolve_state("sept")
    assert res.detector == "xams2026" and res.geometry_path.parent.name == "xams2026"
    assert len(res.geometry["mesh_common"]["holes"]) == 456
    with pytest.raises(config.ConfigError):
        config.load_geometry("no_such_detector")
    other = _copy.deepcopy(res.geometry)
    other["mesh_common"]["holes"] = other["mesh_common"]["holes"][:-1]
    assert config.geometry_hash(other) != config.geometry_hash(res.geometry)    # the holes are part of the geometry


def test_stale_code_warning(tmp_path, monkeypatch, capsys):
    """A source file newer than the import time is reported (a kernel still running old code)."""
    import os
    import time
    import xamssim
    f = xamssim._PKG / "config.py"
    monkeypatch.setattr(xamssim, "_LOADED", time.time() - 10)
    os.utime(f, None)                                             # touch: now newer than the (faked) import time
    assert "xamssim/config.py" in xamssim.changed_since_import()
    assert xamssim.warn_if_stale() and "Restart the kernel" in capsys.readouterr().out
