"""XamsSensorResponse, XamsEvents: photoelectrons -> areas per channel, and one row per decay (plan S7).

XamsSensorResponse (per cluster, `peak_areas`): the photoelectrons of each channel -> area in PE, as the analysis
calibrates it (LED single-PE gain): PMTs emit a second PE with the double-PE probability (VUV), SiPMs add crosstalk
PEs, each PE has a Gaussian area of width spe_resolution (detector sensors.yaml).

XamsEvents (per decay, `xams_events`, the fast output at peak level): S1 = all clusters of the decay; the main S2 = the
clusters within S2_MERGE_NS (drift time) of the brightest S2 (deeper / shallower scatters are separate S2s in the
data), the alternative S2 = the brightest one outside it. Area fraction top (top PMT / both PMTs, no SiPMs), drift
time, position (gate crossing, true z), top-PMT pattern u, v, and the corrected areas: cS1 = S1 divided by the
relative S1 light yield at each cluster (S1 light map, mean over the drift region = 1), cS2 = main S2 divided by the
relative S2 light collection at the gate crossings (S2 pattern map, mean over the gate area = 1) x exp(t / tau).
"""
from __future__ import annotations

import numpy as np
import strax
import straxen
from fuse.plugin import FuseBasePlugin

from ..lightmap import CHANNEL_NAMES, N_CHANNELS

export, __all__ = strax.exporter()
S2_MERGE_NS = 750
PMT = slice(0, 5)                     # bottom, top ch1-ch4
TOP = slice(1, 5)


@export
class XamsSensorResponse(FuseBasePlugin):
    """Areas per channel [PE] from the photoelectrons."""

    __version__ = "0.1.0"
    depends_on = ("s1_photoelectrons", "s2_photoelectrons")
    provides = "peak_areas"
    data_kind = "interactions_in_roi"
    save_when = strax.SaveWhen.TARGET
    dtype = [
        (("S1 area per channel [PE] (lightmap.CHANNEL_NAMES)", "s1_area_ch"), np.float32, (N_CHANNELS,)),
        (("S2 area per channel [PE]", "s2_area_ch"), np.float32, (N_CHANNELS,)),
        (("S1 area, all channels [PE]", "s1_area"), np.float32),
        (("S2 area, all channels [PE]", "s2_area"), np.float32),
    ] + strax.time_fields

    spe_resolution = straxen.URLConfig(type=(list, tuple), help="single-PE area resolution per channel (sensors.yaml)")
    channel_kind = straxen.URLConfig(type=(list, tuple), help="pmt / sipm per channel (sensors.yaml)")
    double_pe_probability = straxen.URLConfig(type=(int, float), help="PMT double-PE probability (sensors.yaml)")
    crosstalk_probability = straxen.URLConfig(type=(int, float), help="SiPM crosstalk probability (sensors.yaml)")

    def setup(self):
        super().setup()
        if len(self.spe_resolution) != N_CHANNELS or len(self.channel_kind) != N_CHANNELS:
            raise ValueError(f"sensors.yaml: {N_CHANNELS} channels expected ({CHANNEL_NAMES})")
        self.res = np.array(self.spe_resolution, float)
        self.p_extra = np.where(np.array(self.channel_kind) == "pmt", float(self.double_pe_probability),
                                float(self.crosstalk_probability))

    def area(self, n):
        n = np.maximum(n, 0).astype(np.int64)
        m = n + self.rng.binomial(n, np.broadcast_to(self.p_extra, n.shape))
        a = m + self.rng.normal(0.0, 1.0, m.shape) * self.res * np.sqrt(m)
        return np.clip(a, 0, None).astype(np.float32)

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        if len(d):
            out["s1_area_ch"], out["s2_area_ch"] = self.area(d["s1_pe"]), self.area(d["s2_pe"])
            out["s1_area"], out["s2_area"] = out["s1_area_ch"].sum(axis=1), out["s2_area_ch"].sum(axis=1)
        return out


@export
class XamsEvents(FuseBasePlugin):
    """One row per decay: S1, main and alternative S2, corrected areas, position."""

    __version__ = "0.2.0"
    depends_on = ("peak_areas", "microphysics_summary", "drifted_electrons", "s1_photoelectrons", "s2_photoelectrons")
    provides = "xams_events"
    data_kind = "xams_events"
    save_when = strax.SaveWhen.TARGET
    dtype = [
        (("Decay (event) id", "eventid"), np.int32),
        (("Clusters of the decay in the XAMS volumes", "n_clusters"), np.int16),
        (("Deposited energy in the XAMS volumes [keV]", "energy"), np.float32),
        (("Deposited energy in the drift region [keV]", "energy_drift"), np.float32),
        (("S1 area [PE]", "s1_area"), np.float32),
        (("S1 area per channel [PE]", "s1_area_ch"), np.float32, (N_CHANNELS,)),
        (("S1 area fraction top (PMTs)", "s1_aft"), np.float32),
        (("Corrected S1 [PE]: S1 / relative light yield at the clusters", "cs1"), np.float32),
        (("Main S2 area [PE]", "s2_area"), np.float32),
        (("Main S2 area per channel [PE]", "s2_area_ch"), np.float32, (N_CHANNELS,)),
        (("Main S2 area fraction top (PMTs)", "s2_aft"), np.float32),
        (("Alternative S2 area [PE] (brightest outside the main S2)", "alt_s2_area"), np.float32),
        (("Number of separate S2s (groups within S2_MERGE_NS)", "n_s2"), np.int16),
        (("Drift time of the main S2 [µs] (area-weighted)", "drift_time"), np.float32),
        (("Corrected main S2 [PE]: S2 / relative S2 light collection at the gate crossings x exp(t / lifetime)", "cs2"),
         np.float32),
        (("x of the main S2 at the gate [cm]", "x"), np.float32),
        (("y of the main S2 at the gate [cm]", "y"), np.float32),
        (("true z of the main S2 clusters [cm]", "z"), np.float32),
        (("top-PMT pattern of the main S2: (ch1 + ch3 - ch2 - ch4) / top", "u"), np.float32),
        (("top-PMT pattern of the main S2: (ch1 + ch2 - ch3 - ch4) / top", "v"), np.float32),
    ] + strax.time_fields

    electron_lifetime_us = straxen.URLConfig(type=(int, float), help="electron lifetime [µs] (state; for cS2)")
    xams_s1_map = straxen.URLConfig(type=str, help="S1 light map (relative light yield for cS1)")
    xams_s2_map = straxen.URLConfig(type=str, help="S2 pattern map (relative S2 light collection for cS2)")
    z_gate_cm = straxen.URLConfig(type=(int, float), help="gate z [cm]")
    z_cathode_cm = straxen.URLConfig(type=(int, float), help="cathode z [cm]")

    def setup(self):
        super().setup()
        m = np.load(self.xams_s1_map)
        tot = m["p"].sum(axis=0)                                           # (x, y, z) all channels
        zsel = (m["z"] > self.z_cathode_cm * 10) & (m["z"] < self.z_gate_cm * 10)
        w = m["inside"][:, :, None] * zsel[None, None, :]
        self.ly_ref = float((tot * w).sum() / w.sum())                    # mean detection over the drift region
        m2 = np.load(self.xams_s2_map)
        self.s2_ref = float((m2["p"].sum(axis=0) * m2["inside"]).sum() / m2["inside"].sum())   # mean over the gate area

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        ev, first, inv = np.unique(d["eventid"], return_index=True, return_inverse=True)
        out = np.zeros(len(ev), dtype=self.dtype)
        if not len(d):
            return out
        out["eventid"] = ev
        out["time"] = np.minimum.reduceat(d["time"][np.argsort(inv, kind="stable")],
                                          np.r_[0, np.cumsum(np.bincount(inv))[:-1]])
        out["endtime"] = np.maximum(out["time"] + 1,
                                    np.maximum.reduceat(d["endtime"][np.argsort(inv, kind="stable")],
                                                        np.r_[0, np.cumsum(np.bincount(inv))[:-1]]))
        out["n_clusters"] = np.bincount(inv)
        out["energy"] = np.bincount(inv, weights=d["ed"])
        out["energy_drift"] = np.bincount(inv, weights=d["ed"] * (d["vol_id"] == 1))
        out["s1_area"] = np.bincount(inv, weights=d["s1_area"])
        for c in range(N_CHANNELS):
            out["s1_area_ch"][:, c] = np.bincount(inv, weights=d["s1_area_ch"][:, c])
        rel = d["s1_p"].sum(axis=1) / self.ly_ref
        out["cs1"] = np.bincount(inv, weights=np.where(rel > 0, d["s1_area"] / np.where(rel > 0, rel, 1), 0.0))
        pm = out["s1_area_ch"][:, PMT].sum(axis=1)
        out["s1_aft"] = np.where(pm > 0, out["s1_area_ch"][:, TOP].sum(axis=1) / np.where(pm > 0, pm, 1), np.nan)
        # S2s per decay: group the clusters with S2 around the brightest one
        tdrift = d["drift_time_mean"].astype(float)
        order = np.argsort(inv, kind="stable")
        bounds = np.r_[0, np.cumsum(np.bincount(inv))]
        tau = float(self.electron_lifetime_us)
        for e in range(len(ev)):
            idx = order[bounds[e]:bounds[e + 1]]
            a = d["s2_area"][idx]
            if not (a > 0).any():
                out["drift_time"][e] = out["x"][e] = out["y"][e] = out["z"][e] = np.nan
                out["u"][e] = out["v"][e] = out["s2_aft"][e] = np.nan
                continue
            rest, groups = idx[a > 0], []
            while len(rest):
                b = rest[np.argmax(d["s2_area"][rest])]
                g = np.abs(tdrift[rest] - tdrift[b]) < S2_MERGE_NS
                groups.append(rest[g])
                rest = rest[~g]
            main = groups[0]
            w = d["s2_area"][main]
            out["n_s2"][e] = len(groups)
            out["s2_area"][e] = w.sum()
            rel2 = d["s2_p"][main].sum(axis=1) / self.s2_ref
            out["cs2"][e] = np.sum(np.where(rel2 > 0, w / np.where(rel2 > 0, rel2, 1), 0.0)) * \
                np.exp(np.average(tdrift[main], weights=w) / 1e3 / tau)
            out["s2_area_ch"][e] = d["s2_area_ch"][main].sum(axis=0)
            out["alt_s2_area"][e] = d["s2_area"][groups[1]].sum() if len(groups) > 1 else 0.0
            out["drift_time"][e] = np.average(tdrift[main], weights=w) / 1e3
            out["x"][e], out["y"][e] = np.average(d["x_obs"][main], weights=w), np.average(d["y_obs"][main], weights=w)
            out["z"][e] = np.average(d["z"][main], weights=w)
        ch = out["s2_area_ch"]
        top = ch[:, TOP].sum(axis=1)
        pm2 = ch[:, PMT].sum(axis=1)
        ok = (top > 0) & (out["s2_area"] > 0)
        out["s2_aft"] = np.where(ok, top / np.where(pm2 > 0, pm2, 1), np.nan)
        out["u"] = np.where(ok, (ch[:, 1] + ch[:, 3] - ch[:, 2] - ch[:, 4]) / np.where(ok, top, 1), np.nan)
        out["v"] = np.where(ok, (ch[:, 1] + ch[:, 2] - ch[:, 3] - ch[:, 4]) / np.where(ok, top, 1), np.nan)
        return out[np.argsort(out["time"], kind="stable")]               # decays are placed at random times
