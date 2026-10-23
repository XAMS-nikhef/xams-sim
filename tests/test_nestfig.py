"""xamssim nest: NEST with run-file settings (widths by name, yield parameters) and the Cs-137 table."""
import numpy as np
import pytest

nestpy = pytest.importorskip("nestpy")
from xamssim import nestfig  # noqa: E402


def test_settings_and_defaults():
    d = nestfig.Nest()
    assert d.widths == list(d.nc.default_NRERWidthsParam)
    n = nestfig.Nest({"widths": {"A_ER": 0.2, "omega_ER": 0.3}})
    i, j = nestfig.WIDTH_KEYS.index("A_ER"), nestfig.WIDTH_KEYS.index("omega_ER")
    assert n.widths[i] == 0.2 and n.widths[j] == 0.3
    assert n.er == list(nestpy.default_er_yields_params())


def test_yields_and_widths():
    cs = [("default", 150.0, 2.87, {}), ("wide", 150.0, 2.87, {"widths": {"A_ER": 0.2}})]
    rows = nestfig.cs137_table(cs, n=1500)
    assert rows[0]["photons"] == pytest.approx(rows[1]["photons"], rel=0.02)          # widths do not move the means
    assert rows[1]["photons_rel_sd"] > 1.5 * rows[0]["photons_rel_sd"]                # but widen the peak
    assert all(r["corr"] < -0.9 for r in rows)                                        # recombination: anti-correlated
    k = nestfig.Nest().curves("beta", 150.0, 2.87, np.array([10.0, 100.0]), n_fluct=50)
    assert np.all(k["ly"] > 0) and np.all(k["qy"] > 0) and k["ly"].shape == (2,)
