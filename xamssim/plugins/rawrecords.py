"""XamsRawRecords: simulated digitizer output, raw records as redax writes them (plan S8; xamssim.waveforms).

One group of clusters per decay (eventid) -> waveforms of every channel -> self-triggered pulses -> records.
PMT channels go to `xams_raw_records`, SiPM channels to `xams_raw_records_sipm` (amstrax: raw_records,
raw_records_sipm; xamssim.amstrax_io copies them under amstrax's keys).
"""
from __future__ import annotations

import numpy as np
import strax
import straxen
from fuse.plugin import FuseBasePlugin

from ..waveforms import Digitizer

export, __all__ = strax.exporter()


def _drop_overlaps(r):
    """Pulses of two decays that overlap in one channel (pile-up, rare at the simulated rates): the later pulse is
    dropped (the real digitizer would have merged them). r sorted by time; returns it sorted by time."""
    o = np.lexsort((r["record_i"], r["time"], r["channel"]))                # pulses contiguous per channel
    q = r[o]
    first = q["record_i"] == 0
    pid = np.cumsum(first) - 1
    starts = q["time"][first]
    ends = starts + q["pulse_length"][first].astype(np.int64) * q["dt"][first]
    chans = q["channel"][first]
    keep = np.ones(len(starts), bool)
    for i in range(1, len(starts)):
        if chans[i] == chans[i - 1] and starts[i] < ends[i - 1]:
            keep[i] = False
            ends[i] = max(ends[i], ends[i - 1])
    q = q[keep[pid]]
    return q[np.lexsort((q["record_i"], q["channel"], q["time"]))]


@export
class XamsRawRecords(FuseBasePlugin):
    """Raw records of the TPC PMTs and the SiPMs."""

    __version__ = "0.2.0"
    depends_on = ("s1_photoelectrons", "s2_photoelectrons", "drifted_electrons", "extracted_electrons",
                  "microphysics_summary")
    provides = ("xams_raw_records", "xams_raw_records_sipm")
    data_kind = {k: k for k in provides}
    save_when = strax.SaveWhen.TARGET

    xams_daq = straxen.URLConfig(type=dict, help="detector daq.yaml incl. the single-PE templates (xamssim.waveforms)")
    spe_resolution = straxen.URLConfig(type=(list, tuple), help="single-PE area resolution per light channel")
    channel_kind = straxen.URLConfig(type=(list, tuple), help="pmt / sipm per light channel")
    double_pe_probability = straxen.URLConfig(type=(int, float), help="PMT double-PE probability")
    crosstalk_probability = straxen.URLConfig(type=(int, float), help="SiPM crosstalk probability")

    def infer_dtype(self):
        dt = strax.raw_record_dtype(int(self.xams_daq["digitizer"]["record_length"]))
        return {k: dt for k in self.provides}

    def setup(self):
        super().setup()
        p_extra = [self.double_pe_probability if k == "pmt" else self.crosstalk_probability for k in self.channel_kind]
        self.dig = Digitizer(self.xams_daq, list(self.spe_resolution), p_extra, self.rng)

    def compute(self, interactions_in_roi, start, end):
        d = interactions_in_roi
        out = {"raw_records": [], "raw_records_sipm": []}
        if len(d):
            ev, inv = np.unique(d["eventid"], return_inverse=True)
            order = np.argsort(inv, kind="stable")
            bounds = np.r_[0, np.cumsum(np.bincount(inv))]
            for e in range(len(ev)):
                cl = d[order[bounds[e]:bounds[e + 1]]]
                if not (cl["s1_pe"].any() or cl["s2_pe"].any()):
                    continue
                for k, r in self.dig.event(cl, t_min=start).items():
                    out[k].append(r)
        res = {}
        for name, key in (("xams_raw_records", "raw_records"), ("xams_raw_records_sipm", "raw_records_sipm")):
            r = np.concatenate(out[key]) if out[key] else np.zeros(0, self.dtype_for(name))
            r = r[np.lexsort((r["record_i"], r["channel"], r["time"]))] if len(r) else r
            if len(r):
                r = r[r["time"] + r["length"] * r["dt"] <= end]                  # nothing past the chunk end
                r = _drop_overlaps(r)
            res[name] = r
        return res
