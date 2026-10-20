"""S8: digitizer pulses (self-trigger, pre / post samples, merging) and records."""
import numpy as np

from xamssim.waveforms import Digitizer


def _dig():
    daq = {"digitizer": {"dt_ns": 4, "record_length": 110, "pre_trigger_samples": 32, "min_pulse_samples": 80},
           "channels": {"1": {"light": "top_ch1", "raw": "raw_records", "threshold": 20, "polarity": "negative",
                              "baseline": 15900, "noise": 0.0, "post_samples": 47, "gain": 50.0}},
           "templates": {"1": [0.0] * 10 + [1.0] + [0.0] * 39},
           "scintillation": {"singlet_ns": 3.1, "triplet_ns": 24.0, "singlet_fraction": 0.25}, "pmt_transit_spread_ns": 2.0}
    return Digitizer(daq, [0.0] * 7, [0.0] * 7, np.random.default_rng(1))


def test_pulse_window_and_merging():
    d = _dig()
    c = d.chans[0]
    a = np.zeros(2000)
    a[500] = 1.0                                     # one PE: 50 ADC at sample 500
    p = d.pulses(c, 0, a)
    assert len(p) == 1 and p[0][0] == (500 - 32) * 4 and len(p[0][1]) == 80        # pre 32, minimum length 80
    assert p[0][1][32] == 15900 - 50                                                 # negative polarity
    a[1500] = 1.0                                    # far away: a second pulse
    assert len(d.pulses(c, 0, a)) == 2
    a[:] = 0
    a[500], a[560] = 1.0, 1.0                        # windows overlap (post 47 + pre 32 > 60): one pulse
    p = d.pulses(c, 0, a)
    assert len(p) == 1 and len(p[0][1]) == (560 + 47 + 1) - (500 - 32)


def test_records_split():
    d = _dig()
    r = d.records([(1000, np.arange(250, dtype=np.int16))], ch=3)
    assert len(r) == 3 and list(r["length"]) == [110, 110, 30] and list(r["record_i"]) == [0, 1, 2]
    assert (r["pulse_length"] == 250).all() and r["time"][1] == 1000 + 110 * 4 and (r["channel"] == 3).all()
