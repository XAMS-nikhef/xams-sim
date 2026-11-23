"""The run-document summary (dashboard run page) and its backfill for older simulated runs (files only)."""
import json
from pathlib import Path

import pytest

from xamssim import amstrax_io, rundb
from xamssim.config import ROOT, resolve

RUN = ROOT / "config" / "runs" / "cs137_r900_001.yaml"


def test_summary_of_a_run():
    res = resolve(RUN)
    s = amstrax_io.run_summary(res)
    st, v = s["state"], s["voltages [V]"]
    assert st["state"] == res.state_name and st["HV case"] == res.state["hv_case"]
    assert v["A"] == res.hv_case["A"] and v["G"] == res.hv_case["G"] and v["C"] == res.hv_case["C"]
    assert st["ΔV anode − gate [V]"] == res.hv_case["A"] - res.hv_case["G"]
    z = {m["name"]: m["z_mm"] for m in res.geometry["meshes"]}
    assert st["drift field [V/cm]"] == pytest.approx((v["G"] - v["C"]) / ((z["gate"] - z["cathode"]) / 10), abs=0.1)
    assert st["extraction field, gas [kV/cm]"] > st["extraction field, liquid [kV/cm]"] > 0
    assert s["source"]["source"] == res.source_name
    json.dumps(s)                                                        # storable as it is


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(amstrax_io, "STORE", tmp_path)
    monkeypatch.setattr(rundb, "collection", lambda: None)
    return tmp_path


def _doc(store, n, **x):
    doc = {"number": n, "name": f"{n:06d}", "tags": ["simulation"], "comments": [{"comment": "keep me"}],
           "xamssim": {"run_key": "k", "corrections": {"truth": {"elife": 1.0}}, **x}}
    (store / f"{n:06d}-metadata.json").write_text(json.dumps(doc))
    return doc


def _load(store, n):
    return json.loads((store / f"{n:06d}-metadata.json").read_text())


def test_backfill(store):
    res = resolve(RUN)
    ok = _doc(store, 990001, run_file=str(RUN), state=res.state_name, condition=amstrax_io.condition(res))
    _doc(store, 990002, run_file=str(RUN), state=res.state_name, condition="0000changed0")
    _doc(store, 990003, run_file="/nowhere/run.yaml", state=res.state_name)
    _doc(store, 990004, run_file=str(RUN), state=res.state_name, summary={"state": {"x": 1}})
    log = []
    dry = amstrax_io.backfill_summary([990001, 990002, 990003, 990004], log=log.append)
    assert dry["written"] == [990001] and dry["has"] == [990004] and set(dry["skipped"]) == {990002, 990003}
    assert "summary" not in _load(store, 990001)["xamssim"]              # dry run: nothing written
    amstrax_io.backfill_summary([990001, 990002], write=True, log=log.append)
    d = _load(store, 990001)
    assert d["xamssim"]["summary"]["voltages [V]"]["A"] == res.hv_case["A"]
    assert "backfilled" in d["xamssim"]["summary"]
    assert d["comments"] == ok["comments"] and d["xamssim"]["corrections"] == ok["xamssim"]["corrections"]
    assert "summary" not in _load(store, 990002)["xamssim"]              # condition changed: left alone
