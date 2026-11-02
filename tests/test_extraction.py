"""Extraction model of a state (state key `extraction`; xamssim.elmap.extraction_curve) and EL maps re-extracted from
another map's liquid field without COMSOL."""
import copy

import numpy as np
import pytest

from xamssim import config, elmap, maps


def _res(spec=None):
    res = config.resolve_state("r900b_flip")
    if spec is not None:
        res.materials = config.with_extraction(res.materials, spec)
    return res


def test_nest_default_threshold():
    f = elmap.extraction_curve(_res())
    assert f(np.array([1.5]))[0] == 0.0                       # below the NEST threshold (~1.70 kV/cm)
    assert 0.0 < f(np.array([2.2]))[0] < f(np.array([3.0]))[0] <= 1.0


def test_nest_shift_moves_the_curve():
    nest = elmap.extraction_curve(_res())
    moved = elmap.extraction_curve(_res({"model": "nest", "shift_kV_cm": 0.3}))
    e = np.array([1.5, 1.7, 2.0, 2.5])
    assert np.allclose(moved(e), nest(e + 0.3))
    assert moved(np.array([1.6]))[0] > 0.0


def test_table():
    f = elmap.extraction_curve(_res({"model": "table", "E_liq_kV_cm": [1.4, 2.0, 3.0], "eff": [0.0, 0.4, 0.9]}))
    assert np.allclose(f(np.array([1.0, 1.7, 2.5, 5.0])), [0.0, 0.2, 0.65, 0.9])


@pytest.mark.parametrize("spec", ["magic", {"model": "table", "E_liq_kV_cm": [2, 1], "eff": [0, 1]},
                                  {"model": "table", "E_liq_kV_cm": [1, 2], "eff": [0, 1.5]},
                                  {"model": "nest", "offset": 0.1}])
def test_bad_specs_rejected(spec):
    with pytest.raises(ValueError):
        elmap.extraction_curve(_res(spec))


def test_extraction_changes_only_the_el_key():
    a, b = _res().map_keys(), _res({"model": "nest", "shift_kV_cm": 0.2}).map_keys()
    assert a["extraction_el"] != b["extraction_el"]
    assert {k: v for k, v in a.items() if k != "extraction_el"} == {k: v for k, v in b.items() if k != "extraction_el"}


def test_state_key_accepted(tmp_path):
    state = config.load_yaml(config._named("state", "r900b_flip"))
    state["extraction"] = {"model": "nest", "shift_kV_cm": 0.25}
    config.check(state, "state", "test")
    mat = config.with_extraction(copy.deepcopy(_res().materials), state["extraction"])
    assert mat["materials"]["liquid_xenon"]["transport"]["extraction"]["shift_kV_cm"] == 0.25


def test_reextracted_from_other_map(tmp_path, monkeypatch):
    for mod in (maps, elmap):
        monkeypatch.setattr(mod, "MAPS", tmp_path)
    monkeypatch.setattr(maps, "MANIFEST", tmp_path / "manifest.json")
    old = _res()
    e_liq = np.array([[1.5, 1.7], [1.9, 2.2]], np.float32)
    d = dict(u=np.array([0.0, 0.025]), ext_eff=elmap.extraction_curve(old)(e_liq), n_el=np.full((2, 2), 100.0),
             t_transit_us=np.full((2, 2), 1.9), e_liq_kV_cm=e_liq)
    rel = f"extraction_el/{old.map_keys()['extraction_el']}/{elmap.FILE}"
    (tmp_path / rel).parent.mkdir(parents=True)
    np.savez(tmp_path / rel, **d)
    maps.register(old, "extraction_el", [rel], producer_version="test")
    new = _res({"model": "nest", "shift_kV_cm": 0.3})
    out = elmap._reextracted_from_other_model(new, log=lambda *a: None)
    assert out is not None
    assert np.allclose(out["ext_eff"], elmap.extraction_curve(new)(e_liq))
    assert np.allclose(out["n_el"], 100.0) and np.allclose(out["t_transit_us"], 1.9)
    other_level = _res()
    other_level.state = {**other_level.state, "liquid_level_mm": 3.0}
    assert elmap._reextracted_from_other_model(other_level, log=lambda *a: None) is None
