"""XamsS1Light, XamsS2Light: photons -> photoelectrons per channel, per cluster (plan S6).

From the light maps of the state (xamssim.lightmap; detection probability per channel incl. the QE):
    S1   NEST photons of the cluster at its position (x, y, z)            -> multinomial over the channels
    S2   S2 (EL) photons of the cluster at its gate crossing (x_obs, y_obs) -> multinomial over the channels
Channels: xamssim.lightmap.CHANNEL_NAMES (bottom PMT, top-PMT sectors ch1-ch4, the two SiPMs). No sensor response yet
(gain, SPE spectrum, double PE: S7), no photon times (S8).
"""
from __future__ import annotations

import numpy as np
import strax
import straxen
from fuse.plugin import FuseBasePlugin

from ..lightmap import N_CHANNELS, LightMap

export, __all__ = strax.exporter()


def _multinomial(rng, n, p):
    """n[i] trials over the channels with probabilities p[i, :] (the rest undetected)."""
    p = np.clip(np.nan_to_num(p), 0, 1)
    s = p.sum(axis=1, keepdims=True)
    p = np.where(s > 1, p / np.maximum(s, 1e-12), p)                     # never more than all photons
    full = np.concatenate([p, 1 - p.sum(axis=1, keepdims=True)], axis=1)
    return rng.multinomial(np.maximum(n, 0).astype(np.int64), np.clip(full, 0, 1))[:, :-1]


def _dtype(what):
    return [
        ((f"{what} photoelectrons per channel (lightmap.CHANNEL_NAMES)", f"{what.lower()}_pe"), np.int32, (N_CHANNELS,)),
        ((f"{what} photoelectrons, all channels", f"{what.lower()}_pe_total"), np.int64),
        ((f"{what} detection probability per photon at the cluster, per channel", f"{what.lower()}_p"), np.float32,
         (N_CHANNELS,)),
    ] + strax.time_fields


@export
class XamsS1Light(FuseBasePlugin):
    """S1 photoelectrons per channel per cluster."""

    __version__ = "0.1.0"
    depends_on = "microphysics_summary"
    provides = "s1_photoelectrons"
    data_kind = "interactions_in_roi"
    save_when = strax.SaveWhen.TARGET
    dtype = _dtype("S1")

    xams_s1_map = straxen.URLConfig(type=str, help="S1 light map of the state (<data>/maps/s1_light/<key>/s1.npz)")

    def setup(self):
        super().setup()
        self.map = LightMap(self.xams_s1_map)

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        if not len(d):
            return out
        p = self.map(d["x"] * 10.0, d["y"] * 10.0, d["z"] * 10.0)
        out["s1_p"] = p
        out["s1_pe"] = _multinomial(self.rng, d["photons"], p)
        out["s1_pe_total"] = out["s1_pe"].sum(axis=1)
        return out


@export
class XamsS2Light(FuseBasePlugin):
    """S2 photoelectrons per channel per cluster."""

    __version__ = "0.1.0"
    depends_on = ("extracted_electrons", "drifted_electrons")
    provides = "s2_photoelectrons"
    data_kind = "interactions_in_roi"
    save_when = strax.SaveWhen.TARGET
    dtype = _dtype("S2")

    xams_s2_map = straxen.URLConfig(type=str, help="S2 pattern map of the state (<data>/maps/s2_pattern/<key>/s2.npz)")

    def setup(self):
        super().setup()
        self.map = LightMap(self.xams_s2_map)

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        if not len(d):
            return out
        p = self.map(d["x_obs"] * 10.0, d["y_obs"] * 10.0)
        out["s2_p"] = p
        out["s2_pe"] = _multinomial(self.rng, d["n_s2_photons"], p)
        out["s2_pe_total"] = out["s2_pe"].sum(axis=1)
        return out
