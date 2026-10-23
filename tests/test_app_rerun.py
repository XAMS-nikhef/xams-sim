"""S11: the app's rerun plan (next free number in the private / production block, new run file with supersedes) and
the DAQ settings table."""
import pytest

from xamssim import amstrax_io, compose

RUN = "# test\nrun_number: {n}\ntags: [test]\nstate: sept\nsource: cs137_sept_middrift\nn_events: 1000\nseed: 1\n"


@pytest.fixture
def studies(tmp_path, monkeypatch):
    runs = tmp_path / "study" / "runs"
    runs.mkdir(parents=True)
    from xamssim import runid
    monkeypatch.setattr(compose, "STUDIES", tmp_path)
    monkeypatch.setattr(runid, "STUDIES", tmp_path)
    monkeypatch.setattr(runid, "PROV", tmp_path / "provenance")
    monkeypatch.setattr(runid, "DATA", tmp_path)
    monkeypatch.setattr(amstrax_io, "STORE", tmp_path / "store")
    return runs


def plan_for(monkeypatch, runs, n, name="a"):
    f = runs / f"{name}.yaml"
    f.write_text(RUN.format(n=n))
    rec = {"run_file": str(f), "run": {"run_number": n}}
    monkeypatch.setattr(compose, "records", lambda run_id: [(f, rec)])
    monkeypatch.setattr(compose, "outdated_reasons", lambda rec: ["maps changed: drift"])
    return compose.rerun_plan(name)


def test_private_and_production_numbers(studies, monkeypatch):
    (studies / "other.yaml").write_text(RUN.format(n=990007))
    p = plan_for(monkeypatch, studies, 990002)
    assert p["new"] == 990008 and p["private"] and p["dst"].endswith("a_r2.yaml")
    assert "run_number: 990008\nsupersedes: 990002" in p["text"] and p["text"].count("run_number") == 1
    q = plan_for(monkeypatch, studies, 900203, name="b")
    assert q["new"] is None and not q["private"]            # production: the number comes at submission
    assert "run_number" not in q["text"] and "supersedes: 900203" in q["text"]


def test_rerun_needs_submit_switch(studies, monkeypatch):
    plan_for(monkeypatch, studies, 990002)
    monkeypatch.delenv("XAMSSIM_WEB_SUBMIT", raising=False)
    with pytest.raises(PermissionError, match="XAMSSIM_WEB_SUBMIT"):
        compose.rerun("a")
    assert not (studies / "a_r2.yaml").exists()


def test_daq_settings():
    rec = {"settings": {"spe_resolution": [0.4], "xams_daq": {
        "digitizer": {"model": "V1725", "dt_ns": 4, "bits": 14, "record_length": 110, "pre_trigger_samples": 32,
                      "min_pulse_samples": 80, "spe_templates": "spe_templates.npz"},
        "channels": {"1": {"light": "top1", "raw": "raw_records", "polarity": "negative", "threshold": 20,
                           "baseline": 15900, "noise": 2.4, "gain": 54.8, "post_samples": 30},
                     "0": {"light": "bottom", "raw": "raw_records", "polarity": "negative", "threshold": 60,
                           "baseline": 15896, "noise": 2.9, "gain": 12.5, "post_samples": 30}},
        "scintillation": {"singlet_ns": 3.1, "triplet_ns": 24.0, "singlet_fraction": 0.25}, "pmt_transit_spread_ns": 2.0}}}
    d = compose.daq_settings(rec)
    assert [c["channel"] for c in d["channels"]] == [0, 1] and d["digitizer"]["sampling [ns]"] == 4
    assert compose.daq_settings({"settings": {}}) is None
