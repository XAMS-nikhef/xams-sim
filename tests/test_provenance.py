"""Provenance: one file per distinct chain run, readable later, with the differences to the configuration now."""
import json

from xamssim import provenance


def test_write_dedupe_and_diff(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "PROV", tmp_path)
    rec = dict(run_id="r", run_key="k1", run={"n_events": 10, "seed": 1}, products={"p": {"lineage_hash": "abc"}},
               geometry={"meshes": [{"name": "gate", "z_mm": 0.0}]}, code={"commit": "c1"})
    f1 = provenance.write(dict(rec))
    assert provenance.write(dict(rec)) == f1                         # same content: no second file
    rec2 = dict(rec, products={"p": {"lineage_hash": "def"}})
    f2 = provenance.write(rec2)
    assert f2 != f1 and len(provenance.entries("r")) == 2
    assert json.loads(f1.read_text())["products"]["p"]["lineage_hash"] == "abc"
    d = provenance.diff({"geometry": {"a": 1, "b": [0] * 20}}, {"geometry": {"a": 2, "b": [1] * 20}})
    assert ("geometry.a", 1, 2) in d and any(k == "geometry.b" for k, _, _ in d)
