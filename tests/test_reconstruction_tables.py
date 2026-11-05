"""Reconstruction figures from the amstrax 3 tables: events joined with the main site and the main S1 / S2."""
import numpy as np

from xamssim import compose


def test_flat_joins_events_sites_peaks(monkeypatch):
    ev = np.zeros(2, dtype=[("time", np.int64), ("event_number", np.int64), ("cs1", np.float32), ("cs2", np.float32)])
    ev["event_number"] = [3, 4]; ev["cs1"] = [10, 20]; ev["cs2"] = [100, 200]
    st = np.zeros(2, dtype=[("event_number", np.int64), ("peak_index", np.int64), ("rank", np.int16),
                            ("drift_time", np.float32), ("x", np.float32), ("y", np.float32)])
    st["event_number"] = [3, 3]; st["peak_index"] = [11, 12]; st["rank"] = [1, 2]; st["drift_time"] = [9000, 1]
    st["x"], st["y"] = [1, 5], [2, 5]
    pk = np.zeros(3, dtype=[("event_number", np.int64), ("peak_index", np.int64), ("type", np.int16),
                            ("dt_s1", np.float32), ("area", np.float32)])
    pk["event_number"] = [3, 3, 3]; pk["peak_index"] = [10, 11, 12]; pk["type"] = [1, 2, 2]
    pk["dt_s1"] = [0, 9000, 1]; pk["area"] = [50, 700, 30]
    data = {"e": ev, "s": st, "p": pk}
    monkeypatch.setattr(compose, "_load", lambda path: data[path])
    prods = [dict(type="events", path="e", calibration=1, made="b", hash="h"),
             dict(type="sites", path="s", calibration=1, made="a", hash="h2"),
             dict(type="event_peaks", path="p", calibration=1, made="a", hash="h3")]
    out = compose._flat(prods[0], prods)
    np.testing.assert_allclose(out["s1_area"], [50, np.nan])
    np.testing.assert_allclose(out["s2_area"], [700, np.nan])
    np.testing.assert_allclose(out["drift_time"], [9000, np.nan])
    np.testing.assert_allclose(out["s2_x"], [1, np.nan])
    np.testing.assert_allclose(out["cs2"], [100, 200])
