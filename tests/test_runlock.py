"""One xamssim process per run id."""
import os

import pytest

from xamssim import runlock


def test_run_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(runlock, "LOCKS", tmp_path)
    with runlock.run_lock("r1"):
        assert (tmp_path / "r1.lock").read_text() == str(os.getpid())
        (tmp_path / "r2.lock").write_text("1")                   # pid 1 (launchd / init) runs: locked
        with pytest.raises(runlock.RunLocked):
            with runlock.run_lock("r2"):
                pass
    assert not (tmp_path / "r1.lock").exists()
    (tmp_path / "r3.lock").write_text("999999")                  # no such process: stale lock taken over
    with runlock.run_lock("r3"):
        pass
