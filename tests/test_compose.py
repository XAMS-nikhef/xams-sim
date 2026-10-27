"""S10: the simulation app's core (read-only part)."""
import pytest

from xamssim import compose


def _rec(**over):
    rec = dict(run_id="r", run_key="k", run_file="/x/runs/r.yaml", created="2026-10-21T10:00:00",
               run=dict(n_events=1000, seed=1, run_number=900101, stop_after="events"), state_name="sept",
               state=dict(liquid_level_mm=4.0, electron_lifetime_us=159, hv_case="sept"), source_name="cs",
               source=dict(isotope="Cs-137", position_mm=[0, 130, -120]), detector="xams2026",
               geometry=dict(meta=dict(version=5)), hv_case=dict(A=2500, G=-2500, C=-3250, BS=-1000, TS=-100),
               physics=dict(clustering="lineage"), settings=dict(electron_lifetime_us=159),
               maps=dict(field=dict(key="f1", present=True)), code=dict(commit="abcdef1234567"))
    rec.update(over)
    return rec


def test_how_far():
    assert compose._how_far({"xams_raw_records", "xams_events"}) == "waveforms"
    assert compose._how_far({"xams_events"}) == "events"
    assert compose._how_far(set()) == "Geant4 only"


def test_summary_and_compare(monkeypatch):
    s = compose.summary(_rec())
    assert s["voltages [V]"]["C"] == -3250 and s["source"]["position [mm]"] == [0, 130, -120]
    assert s["code"]["commit"] == "abcdef1234" and s["maps"]["field"] == "f1"
    other = _rec(hv_case=dict(A=2503, G=303, C=-215, BS=-65, TS=0), state_name="cmb50")
    monkeypatch.setattr(compose, "records", lambda r: [(None, _rec() if r == "a" else other)])
    rows = compose.compare("a", "b")
    assert ("hv_case", "C", -3250, -215) in rows and ("state_name", "", "sept", "cmb50") in rows
    assert all(sec != "run" for sec, *_ in rows)


def test_optics_table_labels_known_keys_first_and_keeps_the_rest():
    t = compose.optics_table({"lxe": {"rayleigh_length_cm": 45, "refractive_index": 1.69},
                              "ptfe_in_liquid": {"reflectivity": 0.95}, "new_thing": 3})
    keys = list(t)
    assert keys[:3] == ["LXe refractive index", "LXe Rayleigh length [cm]", "PTFE reflectivity, liquid"]
    assert t["LXe Rayleigh length [cm]"] == 45 and t["new_thing"] == 3


def test_map_figures_cover_both_optical_maps():
    assert set(compose.MAP_FIGURES) == set(compose.OPTICAL_KINDS) | {"s1_outer"}   # s1_outer: shown with its light key


def test_nest_figures_registered_and_tag():
    rows = [r for row in compose.FIGURE_ROWS for r in row]
    assert "nest" in compose.FIGURES and rows.index("nest") > rows.index("field_axis")    # after the field tiles
    assert "nest_photopeak" in compose.RESULT_FIGURES
    assert compose._nest_tag({}) == "NEST defaults"
    assert compose._nest_tag({"widths": {"A_ER": 0.08}}) == "A_ER 0.08"
    assert "yield parameters set" in compose._nest_tag({"er_yields": [1.0] * 10})
    assert compose.LINES_KEV["Cs-137"] == pytest.approx(661.657)


def test_map_figure_cache_when_map_folder_read_only(tmp_path, monkeypatch):
    """A private app may not write next to the central maps: the figure goes to its own cache."""
    import matplotlib.pyplot as plt
    maps = tmp_path / "maps" / "s1_light" / "abc"
    maps.mkdir(parents=True)
    (maps / "s1.npz").write_bytes(b"")
    maps.chmod(0o555)
    try:
        monkeypatch.setattr(compose, "DATA", tmp_path / "data")
        monkeypatch.setattr(compose, "_map_file", lambda kind, key: maps / "s1.npz")
        monkeypatch.setitem(compose.MAP_FIGURES, "s1_light", ("S1 light", lambda key: plt.figure()))
        out = compose.map_figure("s1_light", "abc")
        assert out == tmp_path / "data" / "cache" / "map_figures" / "s1_light" / "abc" / f"s1_light_v{compose.MAP_FIGURE_VERSION}.png"
        assert out.exists() and compose.map_figure("s1_light", "abc") == out            # found again, not remade
    finally:
        maps.chmod(0o755)
