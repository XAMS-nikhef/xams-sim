"""S10: the simulation app's core (read-only part)."""
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
