"""S10: run documents of simulated runs into run.runs_mc (with a fake collection; no database)."""
import pytest

from xamssim import rundb
from xamssim.config import ConfigError


class FakeCollection:
    def __init__(self):
        self.docs = {}

    def find_one(self, q, projection=None):
        return self.docs.get(q["number"])

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["number"]] = doc

    def find(self, q, projection=None):
        lo, hi = q["number"]["$gte"], q["number"]["$lte"]
        return [d for n, d in self.docs.items() if lo <= n <= hi and ("tags" not in q or q["tags"] in d.get("tags", []))]

    def delete_many(self, q):
        for d in self.find(q):
            del self.docs[d["number"]]


def test_register_and_delete(monkeypatch):
    col = FakeCollection()
    monkeypatch.setattr(rundb, "collection", lambda: col)
    log = []
    doc = dict(number=900201, tags=["simulation", "test"], xamssim=dict(run_key="k1"))
    assert rundb.register(doc, log=log.append) and "added" in log[-1]
    assert rundb.register(dict(doc), log=log.append) and "updated" in log[-1]
    assert rundb.register(dict(doc, xamssim=dict(run_key="k2")), log=log.append) and "rerun" in log[-1]
    col.docs[900202] = dict(number=900202, tags=["simulation"])
    assert rundb.delete(tag="test", dry_run=True, log=log.append) == 1 and 900201 in col.docs
    assert rundb.delete(tag="test", dry_run=False, log=log.append) == 1 and 900201 not in col.docs and 900202 in col.docs


def test_only_mc_numbers(monkeypatch):
    monkeypatch.setattr(rundb, "collection", lambda: FakeCollection())
    with pytest.raises(ConfigError):
        rundb.register(dict(number=7719), log=lambda *a: None)
    with pytest.raises(ConfigError):
        rundb.delete((7000, 999999), log=lambda *a: None)


def test_no_account(monkeypatch, tmp_path):
    monkeypatch.setattr(rundb, "CONFIG_FILE", tmp_path / "none")
    assert not rundb.configured()
    msgs = []
    assert rundb.register(dict(number=900201), log=msgs.append) is False and "only as a file" in msgs[0]


def test_record_processing(monkeypatch):
    import mongomock
    col = mongomock.MongoClient()["run"]["runs_mc"]
    col.insert_one(dict(number=900201, data=[dict(type="live_data"), dict(type="event_info", lineage_hash="old")]))
    monkeypatch.setattr(rundb, "collection", lambda: col)
    entries = [dict(type="raw_records", location="/mc_raw_records"), dict(type="event_info", lineage_hash="new")]
    assert rundb.record_processing(900201, entries, "done", "v5", log=lambda *a: None)
    d = col.find_one({"number": 900201})
    assert sorted(e["type"] for e in d["data"]) == ["event_info", "live_data", "raw_records"]
    assert [e.get("lineage_hash") for e in d["data"] if e["type"] == "event_info"] == ["new"]
    assert d["processing_status"]["status"] == "done" and d["processing_history"][-1]["corrections_version"] == "v5"
    assert "made" in d["xamssim"]
