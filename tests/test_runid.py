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


def test_identity(area):
    f, g = area / "a.yaml", area / "b.yaml"
    f.write_text("run_number: 990005\n" + RUN)
    assert runid.check_identity(res(f)) == "990005"
    g.write_text("run_number: 990005\n" + RUN)                      # the same number in two run files
    with pytest.raises(ConfigError, match="also used by"):
        runid.check_identity(res(f))
    g.write_text("run_number: 990006\n" + RUN)
    prov("990006", f)                                              # 990006 was made from another run file
    with pytest.raises(ConfigError, match="was made from"):
        runid.check_identity(res(g))
    prov("990005", f, key="k1")
    with pytest.raises(ConfigError, match="other settings"):        # same number, changed settings
        runid.check_identity(res(f, key="k2"))
    h = area / "c.yaml"
    h.write_text("run_number: 990007\n" + RUN)
    prov("990004", h)                                              # this run file was run before as 990004
    with pytest.raises(ConfigError, match="run before as run 990004"):
        runid.check_identity(res(h))


def test_production_numbers(area, monkeypatch):
    """Production account: the last production number + 1 (run.runs_mc and the files), 900001 after a clean start."""
    from xamssim import rundb

    class Col:
        def __init__(self, numbers):
            self.numbers = numbers

        def find(self, q, proj):
            return [{"number": n} for n in self.numbers]

    monkeypatch.setattr(rundb, "configured", lambda: True)
    monkeypatch.setattr(rundb, "collection", lambda: Col([]))
    f = area / "a.yaml"
    f.write_text(RUN)
    assert runid.ensure_number(f) == 900001 and "(production)" in f.read_text()
    monkeypatch.setattr(rundb, "collection", lambda: Col([900001, 900002, 990004]))   # private numbers do not count
    g = area / "b.yaml"
    g.write_text(RUN)
    assert runid.ensure_number(g) == 900003
    h = area / "c.yaml"
    h.write_text(RUN)
    assert runid.ensure_number(h, production=False) == 990005
