"""Run numbers as the identity of a simulation: automatic private number, one run file = one number = one simulation."""
import json
from types import SimpleNamespace

import pytest

from xamssim import amstrax_io, runid
from xamssim.config import ConfigError

RUN = "# a test run\n\nstate: sept\nsource: cs137_sept_middrift\nn_events: 10\nseed: 1\n"


@pytest.fixture
def area(tmp_path, monkeypatch):
    (tmp_path / "study" / "runs").mkdir(parents=True)
    monkeypatch.setattr(runid, "STUDIES", tmp_path)
    monkeypatch.setattr(runid, "ROOT", tmp_path / "no_repo")
    monkeypatch.setattr(runid, "DATA", tmp_path / "data")
    monkeypatch.setattr(runid, "PROV", tmp_path / "data" / "provenance")
    monkeypatch.setattr(amstrax_io, "STORE", None)
    from xamssim import rundb
    monkeypatch.setattr(rundb, "configured", lambda: False)
    return tmp_path / "study" / "runs"


def res(path, key="k1"):
    return SimpleNamespace(run=runid.load_yaml(path), run_path=path, run_key=lambda: key)


def prov(rid, run_file, key="k1"):
    d = runid.PROV / rid
    d.mkdir(parents=True, exist_ok=True)
    (d / "20261023T000000_x.json").write_text(json.dumps({"run_file": str(run_file), "run_key": key}))


def test_ensure_number(area):
    f = area / "a.yaml"
    f.write_text(RUN)
    assert runid.ensure_number(f) == 990001                       # first private number
    text = f.read_text()
    assert text.startswith("# a test run\n\nrun_number: 990001") and runid.number_of(f) == 990001
    assert runid.ensure_number(f) == 990001                       # unchanged the second time
    g = area / "b.yaml"
    g.write_text(RUN)
    assert runid.ensure_number(g) == 990002


class Col:
    """A fake run.runs_mc with a unique index on number."""

    def __init__(self, numbers=(), run_file=""):
        self.docs = {n: {"number": n, "xamssim": {"run_file": run_file}} for n in numbers}

    def find(self, q, proj=None):
        return list(self.docs.values())

    def find_one(self, q, proj=None, sort=None):
        if "number" in q and isinstance(q["number"], int):
            return self.docs.get(q["number"])
        lo, hi = q["number"]["$gte"], q["number"]["$lte"]
        ns = [n for n in self.docs if lo <= n <= hi]
        return self.docs[max(ns)] if ns else None

    def insert_one(self, doc):
        from pymongo.errors import DuplicateKeyError
        if doc["number"] in self.docs:
            raise DuplicateKeyError("dup")
        self.docs[doc["number"]] = doc


def test_private_numbers_are_free(area, capsys):
    f, g = area / "a.yaml", area / "b.yaml"
    f.write_text("run_number: 990005\n" + RUN)
    g.write_text("run_number: 990005\n" + RUN)                      # the same number in two run files: allowed
    assert runid.check_identity(res(f)) == "990005"
    prov("990005", g)                                              # made from the other run file: replaced
    (runid.DATA / "g4" / "990005").mkdir(parents=True)
    assert runid.check_identity(res(f)) == "990005"
    assert not (runid.PROV / "990005").exists() and not (runid.DATA / "g4" / "990005").exists()
    prov("990005", f, key="k1")
    assert runid.check_identity(res(f, key="k2")) == "990005"      # changed settings: replaced
    assert "replaced" in capsys.readouterr().out
    h = area / "c.yaml"
    h.write_text("run_number: 900005\n" + RUN)                      # a production number in a private run
    with pytest.raises(ConfigError, match="private runs use"):
        runid.check_identity(res(h))


def test_production_identity(area, monkeypatch):
    from xamssim import rundb
    f = area / "a.yaml"
    f.write_text("run_number: 900004\n" + RUN)
    col = Col([900004], run_file=str(f.resolve()))
    monkeypatch.setattr(rundb, "configured", lambda: True)
    monkeypatch.setattr(rundb, "collection", lambda: col)
    assert runid.check_identity(res(f)) == "900004"
    prov("900004", f, key="k1")
    with pytest.raises(ConfigError, match="a changed run is a new run"):
        runid.check_identity(res(f, key="k2"))
    g = area / "b.yaml"
    g.write_text("run_number: 900007\n" + RUN)                      # not in the run database
    with pytest.raises(ConfigError, match="not in run.runs_mc"):
        runid.check_identity(res(g))
    h = area / "c.yaml"
    h.write_text("run_number: 990007\n" + RUN)
    with pytest.raises(ConfigError, match="not a production number"):
        runid.check_identity(res(h))


def test_production_numbers(area, monkeypatch):
    """Production numbers are reserved in run.runs_mc: highest + 1 (900001 when empty); a lost race takes the next."""
    from xamssim import rundb
    col = Col()
    monkeypatch.setattr(rundb, "configured", lambda: True)
    monkeypatch.setattr(rundb, "collection", lambda: col)
    f = area / "a.yaml"
    f.write_text(RUN)
    assert runid.ensure_number(f) == 900001 and "(production)" in f.read_text()
    assert col.docs[900001]["mode"] == "simulation (reserved)"
    col.docs[900002] = {"number": 900002}                             # another submission took 900002 meanwhile
    orig = col.find_one
    calls = []

    def stale_find_one(q, proj=None, sort=None):                     # first look still sees 900001 as the highest
        calls.append(1)
        return col.docs[900001] if len(calls) == 1 else orig(q, proj, sort)
    col.find_one = stale_find_one
    g = area / "b.yaml"
    g.write_text(RUN)
    assert runid.ensure_number(g) == 900003
    h = area / "c.yaml"
    h.write_text(RUN)
    assert runid.ensure_number(h, production=False) == 990001
