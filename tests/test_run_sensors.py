"""Run file `sensors:` -> detection efficiency per channel on top of the detector's sensors.yaml (validated)."""
from types import SimpleNamespace

import pytest

from xamssim.chain import _run_sensor_override
from xamssim.config import ConfigError

CH = {"bottom": {"kind": "pmt", "spe_resolution": 0.5, "efficiency": 0.75},
      "top_ch1": {"kind": "pmt", "spe_resolution": 0.4, "efficiency": 0.70}}


def res(sensors=None):
    run = {"sensors": sensors} if sensors is not None else {}
    return SimpleNamespace(run=run, run_path="runs/x.yaml")


def test_no_override():
    assert _run_sensor_override(res(), CH) == CH


def test_override_efficiency():
    out = _run_sensor_override(res({"bottom": {"efficiency": 0.62}}), CH)
    assert out["bottom"] == {"kind": "pmt", "spe_resolution": 0.5, "efficiency": 0.62}
    assert out["top_ch1"] == CH["top_ch1"] and CH["bottom"]["efficiency"] == 0.75     # input not changed


@pytest.mark.parametrize("sensors, match", [({"top_ch9": {"efficiency": 0.5}}, "unknown channel"),
                                            ({"bottom": {"spe_resolution": 0.3}}, "only"),
                                            ({"bottom": 0.6}, "only"),
                                            ({"bottom": {"efficiency": 1.5}}, "between 0 and 1")])
def test_invalid(sensors, match):
    with pytest.raises(ConfigError, match=match):
        _run_sensor_override(res(sensors), CH)
