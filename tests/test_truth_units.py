"""The truth file in amstrax units (mm, ns); older files (cm, µs) converted when read."""
import numpy as np

from xamssim import amstrax_io

DT = np.dtype([(("x of the main S2 at the gate [cm]", "x"), np.float32), (("y [cm]", "y"), np.float32),
               (("true z [cm]", "z"), np.float32), (("Drift time [µs]", "drift_time"), np.float32),
               (("Start time", "time"), np.int64), (("energy [keV]", "energy"), np.float32),
               (("S1 area per channel [PE]", "s1_area_ch"), np.float32, (8,)), ("no_title", np.int16)])


def events():
    e = np.zeros(2, dtype=DT)
    e["x"], e["y"], e["z"], e["drift_time"], e["time"], e["energy"] = [1.5, -2], [0.5, 2.2], [-3, -0.1], [20, 1], [7, 9], [662, 32]
    e["s1_area_ch"][0], e["no_title"] = np.arange(8), [3, 4]
    return e


def test_new_and_old_files(tmp_path):
    e = events()
    new = tmp_path / "new.npz"
    np.savez_compressed(new, events=amstrax_io._truth_units(e), units=np.array(amstrax_io.TRUTH_UNITS))
    old = tmp_path / "old.npz"
    np.savez_compressed(old, events=e)
    for f in (new, old):
        t = amstrax_io.load_truth(f)
        assert np.allclose(t["x"], [15, -20]) and np.allclose(t["z"], [-30, -1])
        assert np.allclose(t["drift_time"], [20000, 1000]) and list(t["time"]) == [7, 9]
        assert np.allclose(t["energy"], [662, 32]) and t["s1_area_ch"].shape == (2, 8) and t["s1_area_ch"][0, 7] == 7
        assert list(t["no_title"]) == [3, 4]
        assert "[mm]" in t.dtype.fields["x"][2] and "[ns]" in t.dtype.fields["drift_time"][2]
