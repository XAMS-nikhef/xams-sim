"""S10: per-run corrections of simulated runs in their run document (truth, calibrated, by condition)."""
import json

import mongomock
import pytest
import strax

from xamssim import amstrax_io, corrections, rundb
from xamssim.config import ConfigError

TRUTH = {"elife": 159000.0, "drift_time_gate": 3904.0, "drift_time_cathode": 37238.0, "gain_to_pe_array": [0.08] * 8}


def write(store, number, state="sept", condition="c1", tags=("simulation",), **x):
    doc = {"number": number, "name": f"{number:06d}", "tags": list(tags),
           "xamssim": {"state": state, "condition": condition, "run_key": "k", "corrections": {"truth": TRUTH}, **x}}
    (store / f"{number:06d}-metadata.json").write_text(json.dumps(doc))


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(amstrax_io, "STORE", tmp_path)
    monkeypatch.setattr(rundb, "collection", lambda: None)            # private: files only
    return tmp_path


def test_select_and_calibrate(store):
    write(store, 990001)
    write(store, 990002, tags=("simulation", "scan"))
    write(store, 990003, state="cmb50", condition="c2")
    assert corrections.runs() == [990001, 990002, 990003]
    assert corrections.runs(state="sept") == [990001, 990002]
    assert corrections.runs(tag="scan") == [990002]
    assert corrections.runs((990002, 990003)) == [990002, 990003]

    cal = {"elife": 151200.0, "drift_time_gate": 4416.0, "method": "elife fit + drift edges"}
    assert corrections.set_calibrated(cal, 990001, [990001, 990002], log=lambda *a: None) == 2
    c = corrections.corrections(corrections.load(990002))
    assert c["calibrated"]["elife"] == 151200.0 and c["calibrated"]["version"] == 1
    assert c["calibrated"]["from_run"] == 990001 and c["calibrated"]["method"] == "elife fit + drift edges"
    assert c["truth"] == TRUTH and c["history"] == []

    corrections.set_calibrated({"elife": 152000.0}, 990001, [990001], log=lambda *a: None)
    c = corrections.corrections(corrections.load(990001))
    assert c["calibrated"]["version"] == 2 and c["history"][0]["elife"] == 151200.0

    with pytest.raises(ConfigError, match="another condition"):          # cmb50 is not sept
        corrections.set_calibrated(cal, 990001, [990003], log=lambda *a: None)
    with pytest.raises(ConfigError, match="expected some of"):
        corrections.set_calibrated({"lifetime": 1.0}, 990001, [990001], log=lambda *a: None)


def test_dry_run_and_production(store, monkeypatch):
    write(store, 900301)
    col = mongomock.MongoClient()["run"]["runs_mc"]
    col.insert_one({"number": 900301, "xamssim": {"corrections": {"truth": TRUTH}}})
    corrections.set_calibrated({"elife": 150000.0}, 900301, [900301], dry_run=True, log=lambda *a: None)
    assert "calibrated" not in corrections.corrections(corrections.load(900301))
    monkeypatch.setattr(rundb, "collection", lambda: col)
    corrections.set_calibrated({"elife": 150000.0}, 900301, [900301], log=lambda *a: None)
    assert col.find_one({"number": 900301})["xamssim"]["corrections"]["calibrated"]["elife"] == 150000.0
    assert corrections.corrections(corrections.load(900301))["calibrated"]["version"] == 1


def test_old_documents(store):
    (store / "990009-metadata.json").write_text(json.dumps({"number": 990009, "xamssim": {"truth": TRUTH}}))
    assert corrections.corrections(corrections.load(990009))["truth"] == TRUTH
    with pytest.raises(ConfigError, match="no xamssim.condition"):
        corrections.set_calibrated({"elife": 1.0}, 990009, [990009], log=lambda *a: None)
    write(store, 990010)
    with pytest.raises(ConfigError, match="no condition"):
        corrections.set_calibrated({"elife": 1.0}, 990010, [990009, 990010], log=lambda *a: None)


def test_run_number_is_one_simulation(tmp_path):
    sf = strax.DataDirectory(str(tmp_path), provide_run_metadata=True)
    old = {"number": 990001, "xamssim": {"run_key": "k1", "corrections": {
        "truth": TRUTH, "calibrated": {"elife": 1.0, "version": 1}, "history": []}}}
    sf.write_run_metadata("990001", old)
    doc = {"number": 990001, "xamssim": {"run_key": "k1", "corrections": {"truth": TRUTH}}}
    amstrax_io._keep_calibration(sf, "990001", doc)                  # the same simulation: calibrations kept
    assert doc["xamssim"]["corrections"]["calibrated"]["version"] == 1
    with pytest.raises(ConfigError, match="new run number"):         # another simulation under the same number
        amstrax_io._keep_calibration(sf, "990001", {"number": 990001, "xamssim": {"run_key": "k2", "corrections": {}}})
    amstrax_io._keep_calibration(sf, "990002", dict(doc))             # a new run: nothing to keep
