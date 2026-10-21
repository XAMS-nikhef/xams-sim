"""S9: simulated runs as redax live data: chunk folders and the live_mc guard."""
import numpy as np
import pytest

from xamssim import live
from xamssim.config import ConfigError


def test_chunk_folders():
    s = 1_000_000_000
    rel = np.array([0, 9 * s, 10 * s + 1, 10 * s + s // 4, 11 * s, 21 * s])   # chunk 0, overlap 0/1, chunk 1, chunk 2
    f = live.chunk_folders(rel)
    assert list(f) == ["000000", "000000_post", "000001_pre", "000001", "000001_post", "000002_pre", "000002"]
    assert list(f["000000"]) == [0, 1] and list(f["000000_post"]) == [2, 3] and list(f["000001_pre"]) == [2, 3]
    assert list(f["000001"]) == [4] and len(f["000001_post"]) == 0 and list(f["000002"]) == [5]


def test_live_root_guard(tmp_path, monkeypatch):
    monkeypatch.delenv("XAMSSIM_LIVE", raising=False)
    assert live.live_root(tmp_path / "strax_data") == tmp_path / "live_mc"
    monkeypatch.setenv("XAMSSIM_LIVE", str(tmp_path / "live_data"))
    with pytest.raises(ConfigError):
        live.live_root(tmp_path / "strax_data")
