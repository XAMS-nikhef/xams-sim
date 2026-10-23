"""physics.nest of a run file -> fuse's NEST options (validated; part of the run key via the run file)."""
from types import SimpleNamespace

import pytest

from xamssim.chain import nest_settings
from xamssim.config import ConfigError


def res(nest=None):
    run = {"physics": {"nest": nest}} if nest is not None else {"physics": {}}
    return SimpleNamespace(run=run, run_path="runs/x.yaml")


def test_defaults():
    assert nest_settings(res()) == {"nest_er_yields_parameters": -1, "nest_nr_yields_parameters": -1,
                                    "nest_width_parameters": {}}


def test_settings():
    out = nest_settings(res({"widths": {"A_ER": 0.11, "fano_ER": 1}, "er_yields": [-1] * 10}))
    assert out["nest_width_parameters"] == {"A_ER": 0.11, "fano_ER": 1.0}
    assert out["nest_er_yields_parameters"] == [-1] * 10 and out["nest_nr_yields_parameters"] == -1


@pytest.mark.parametrize("nest, match", [({"recomb": 1}, "unknown physics.nest"),
                                         ({"widths": {"A_XX": 1}}, "widths"),
                                         ({"er_yields": [1, 2]}, "list of 10"),
                                         ({"nr_yields": 3}, "list of 12")])
def test_invalid(nest, match):
    with pytest.raises(ConfigError, match=match):
        nest_settings(res(nest))
