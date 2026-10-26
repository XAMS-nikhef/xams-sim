"""Zero field (state zero_field: true): config, plugin swap, quanta options, no drift / extraction (plugins/zero.py)."""
import numpy as np
import pytest

from xamssim import chain, config
from xamssim.config import ConfigError

from test_chain import ROWS, write_g4


def run_file(tmp_path, **physics):
    p = tmp_path / "zf.yaml"
    phys = "".join(f"\n  {k}: {v}" for k, v in physics.items())
    p.write_text(f"state: zero\nsource: cs137_zerofield\nn_events: 6\nseed: 1\nrun_number: 999950\n"
                 + (f"physics:{phys}\n" if physics else ""))
    return p


def test_config(tmp_path):
    res = config.resolve(run_file(tmp_path))
    assert res.zero_field and set(res.map_keys()) == {"s1_light", "s2_pattern"}        # no field / drift / EL maps
    assert all(res.hv_case[k] == 0 for k in ("A", "G", "C", "BS", "TS"))
    from xamssim.waveforms import daq_file, load_daq
    assert daq_file(res).name == "daq_sr2026_3.yaml"
    d = load_daq(res)
    assert d["channels"]["0"]["gain"] == pytest.approx(53.0) and set(d["templates"]) == {"0", "1", "2", "3", "4", "6", "7"}
    assert chain.physics(res)["zero_field_yields"] == "nest_gamma"
    with pytest.raises(ConfigError):
        chain.physics(config.resolve(run_file(tmp_path, zero_field_yields="beta")))
    names = [p.__name__ for p in chain.plugins("lineage", zero_field=True)]
    assert {"XamsZeroField", "XamsZeroFieldYields", "XamsNoDrift", "XamsNoExtraction", "XamsZeroFieldVolumes"} <= set(names)
    assert "XamsElectronDrift" not in names and "NestYields" not in names


@pytest.mark.parametrize("model", ["nest_gamma", "proportional"])
def test_chain(tmp_path, model):
    pytest.importorskip("fuse")
    write_g4(tmp_path / "g4", ROWS, 6)
    run = run_file(tmp_path, zero_field_yields=model, zero_field_light_fraction=0.8)
    st, rid = chain.context(run, g4_out=tmp_path / "g4", store=tmp_path / "strax")
    s = st.get_array(rid, "microphysics_summary")
    assert np.all(s["e_field"] == 0)
    assert sorted(s["vol_id"]) == [1, 1, 1, 2, 3, 4]                              # geometric volumes, as with field
    er = (s["vol_id"] == 1) & (s["ed"] > 1)
    frac = s["photons"][er] / (s["photons"][er] + s["electrons"][er])
    if model == "nest_gamma":
        assert np.all(frac > 0.8)                                                 # ~90 % light at zero field
    else:
        assert np.mean(frac) == pytest.approx(0.8, abs=0.1)
    dr = st.get_array(rid, "drifted_electrons")
    assert np.all(dr["n_electron_interface"] == 0) and np.allclose(dr["x_obs"], s["x"])
    ex = st.get_array(rid, "extracted_electrons")
    assert np.all(ex["n_s2_photons"] == 0)
