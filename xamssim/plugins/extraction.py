"""XamsExtractionEL: extraction from the liquid and electroluminescence in the gas, per cluster (plan S5).

From the state's extraction / EL map (xamssim.elmap) at the position where the cluster's electrons cross the gate
(x_obs, y_obs of drifted_electrons -> coordinates (u, v) in the gate-hole cell; the anode is aligned with the gate):
    extracted     binomial(electrons at the surface, extraction efficiency)
    S2 photons    Poisson(extracted x EL photons per electron)
    S2 time       drift time + the electron's EL emission profile (quantiles), its width combined with the
                  longitudinal diffusion of the drift
Clusters in the gas (vol_id 3) keep their electrons and emit the part of the EL path that lies above them.
"""
from __future__ import annotations

import numpy as np
import strax
import straxen
from fuse.plugin import FuseBasePlugin

from ..elmap import ELMap, QUANTILES

export, __all__ = strax.exporter()
NQ = len(QUANTILES)


@export
class XamsExtractionEL(FuseBasePlugin):
    """Extracted electrons, S2 photons and the S2 time profile per cluster."""

    __version__ = "0.1.0"
    depends_on = ("drifted_electrons", "microphysics_summary")
    provides = "extracted_electrons"
    data_kind = "interactions_in_roi"
    save_when = strax.SaveWhen.TARGET

    dtype = [
        (("Electrons extracted into the gas", "n_electron_extracted"), np.int32),
        (("S2 (EL) photons produced", "n_s2_photons"), np.int64),
        (("Extraction efficiency at the cluster's gate-hole position", "extraction_efficiency"), np.float32),
        (("EL photons per extracted electron", "el_photons_per_electron"), np.float32),
        (("Mean S2 time after the interaction: drift + mean EL emission [ns]", "s2_time_mean"), np.int32),
        (("Width of the S2 of this cluster: 25-75 % of the light, EL profile and diffusion [ns]", "s2_width50"), np.int32),
        (("EL emission-time quantiles of one electron, 5 ... 95 % [ns]", "el_time_quantiles"), np.float32, (NQ,)),
    ] + strax.time_fields

    xams_el_map = straxen.URLConfig(type=str, help="extraction / EL map of the state (<data>/maps/extraction_el/<key>/el.npz)")
    gate_angle_deg = straxen.URLConfig(type=(int, float), help="rotation of the gate mesh (geometry.yaml)")
    mesh_pitch_mm = straxen.URLConfig(type=(int, float), help="mesh pitch (geometry.yaml)")
    z_anode_cm = straxen.URLConfig(type=(int, float), help="anode mesh z [cm] (geometry.yaml)")
    z_liquid_cm = straxen.URLConfig(type=(int, float), help="liquid surface z [cm] (gate + liquid level of the state)")

    def setup(self):
        super().setup()
        self.el = ELMap(self.xams_el_map)
        a = np.radians(float(self.gate_angle_deg))
        self.cos, self.sin = np.cos(a), np.sin(a)
        self.iq = {q: int(np.argmin(abs(QUANTILES - q))) for q in (0.25, 0.5, 0.75)}

    def cell_uv(self, x_mm, y_mm):
        p = float(self.mesh_pitch_mm)
        xm = self.cos * x_mm + self.sin * y_mm
        ym = -self.sin * x_mm + self.cos * y_mm
        return xm - (np.floor(xm / p) + 0.5) * p, ym - (np.floor(ym / p) + 0.5) * p

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        if not len(d):
            return out
        u, v = self.cell_uv(d["x_obs"] * 10.0, d["y_obs"] * 10.0)
        ext = self.el(u, v, "ext_eff").astype(float)
        nel = self.el(u, v, "n_el").astype(float)
        tq = self.el(u, v, "t_q_us").astype(float) * 1e3                       # ns
        gas = d["vol_id"] == 3
        ext[gas] = 1.0
        if gas.any():                                                          # only the part of the gap above them
            frac = np.clip((self.z_anode_cm - d["z"][gas]) / (self.z_anode_cm - self.z_liquid_cm), 0, 1)
            nel[gas] *= frac
            tq[gas] *= frac[:, None]
        n = np.maximum(d["n_electron_interface"], 0).astype(np.int64)
        n_ext = self.rng.binomial(n, np.clip(ext, 0, 1))
        out["n_electron_extracted"] = n_ext
        out["n_s2_photons"] = self.rng.poisson(n_ext * np.nan_to_num(nel))
        out["extraction_efficiency"] = ext
        out["el_photons_per_electron"] = nel
        out["el_time_quantiles"] = np.nan_to_num(tq)
        mean_el = np.nan_to_num(tq.mean(axis=1))
        out["s2_time_mean"] = np.round(np.where(gas, 0, d["drift_time_mean"]) + mean_el).astype(np.int32)
        w_el = np.nan_to_num(tq[:, self.iq[0.75]] - tq[:, self.iq[0.25]])
        out["s2_width50"] = np.round(np.sqrt(w_el ** 2 + (1.349 * d["drift_time_spread"]) ** 2)).astype(np.int32)
        return out
