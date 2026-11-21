"""physics.er_model: NEST beta-ER (default) or gamma-ER per electron-recoil cluster (plugins/yields.py)."""
import nestpy
import pytest

from xamssim import chain
from xamssim.plugins.yields import XamsGammaERYields


def test_plugins_swap():
    import fuse
    names = [p.__name__ for p in chain.plugins("lineage")]
    assert "NestYields" in names and "XamsGammaERYields" not in names
    g = chain.plugins("lineage", er_model="gamma")
    assert XamsGammaERYields in g and fuse.micro_physics.NestYields not in g


def test_gamma_yields():
    p = XamsGammaERYields.__new__(XamsGammaERYields)
    p.nc = nestpy.NESTcalc(nestpy.VDetector())
    p.nest_er_yields_parameters_list = [-1.0] * 10
    p.nest_nr_yields_parameters_list = [-1.0] * 12
    y = p.get_yields_from_NEST(662.0, 8, 97.0, 0, 0, 2.86)            # a beta cluster gets gamma-ER yields
    ref = p.nc.GetYields(interaction=nestpy.INTERACTION_TYPE(7), energy=662.0, drift_field=97.0, density=2.86)
    assert y.PhotonYield == pytest.approx(ref.PhotonYield) and y.ElectronYield == pytest.approx(ref.ElectronYield)
    assert y.PhotonYield / 662.0 > 40                                  # gamma-ER: ~42 photons / keV at 97 V/cm


def test_bad_value(tmp_path):
    class R:
        run = {"physics": {"er_model": "alpha"}}
        run_path = tmp_path / "x.yaml"
    with pytest.raises(chain.ConfigError):
        chain.physics(R())
