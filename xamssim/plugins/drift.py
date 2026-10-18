"""XamsElectronDrift: the electrons of each cluster from where they are made to the liquid surface (plan S4).

From the state's drift map (xamssim.driftmap) at the cluster position: the end point of the electrons, the drift time
to the surface, where they cross the gate, the path length. Then per cluster
    survival      exp(-t / tau) if the electrons reach the surface (lifetime tau of the state), 0 if they end on the
                  bottom screen, the PTFE wall or a SiPM
    electrons     binomial(NEST electrons, survival) at the surface; clusters in the gas keep their electrons (S5)
    drift time    mean = map value; spread from longitudinal diffusion sigma_L = sqrt(2 D_L t), divided by the mean
                  velocity along the path
    position      where the electrons cross the gate (field distortion included); transverse spread sqrt(2 D_T t)
Transport constants from materials.yaml (liquid_xenon.transport), lifetime from the state.
"""
from __future__ import annotations

import numpy as np
import strax
import straxen
from fuse.plugin import FuseBasePlugin

from ..driftmap import GAS, SURFACE, DriftMap

export, __all__ = strax.exporter()


@export
class XamsElectronDrift(FuseBasePlugin):
    """Electrons at the liquid surface per cluster, their drift time and position."""

    __version__ = "0.1.0"
    depends_on = "microphysics_summary"
    provides = "drifted_electrons"
    data_kind = "interactions_in_roi"
    save_when = strax.SaveWhen.TARGET

    dtype = [
        (("Number of electrons reaching the liquid-gas interface", "n_electron_interface"), np.int32),
        (("Mean drift time to the liquid surface [ns]", "drift_time_mean"), np.int32),
        (("Spread of the drift time (longitudinal diffusion) [ns]", "drift_time_spread"), np.int32),
        (("x where the electrons cross the gate [cm]", "x_obs"), np.float32),
        (("y where the electrons cross the gate [cm]", "y_obs"), np.float32),
        (("z of the cluster (no field-distortion correction yet) [cm]", "z_obs"), np.float32),
        (("Transverse spread of the electron cloud at the surface (diffusion) [cm]", "xy_spread"), np.float32),
        (("End point of the electrons (xamssim.driftmap.CODES)", "drift_end"), np.int8),
        (("Survival probability to the surface", "survival"), np.float32),
    ] + strax.time_fields

    xams_drift_map = straxen.URLConfig(type=str, help="drift map of the state (<data>/maps/drift/<key>/drift_xyz.npz)")
    electron_lifetime_us = straxen.URLConfig(type=(int, float), help="electron lifetime in the liquid [µs] (state)")
    diffusion_longitudinal_cm2_s = straxen.URLConfig(type=(int, float), help="D_L of the liquid [cm²/s] (materials.yaml)")
    diffusion_transverse_cm2_s = straxen.URLConfig(type=(int, float), help="D_T of the liquid [cm²/s] (materials.yaml)")

    def setup(self):
        super().setup()
        self.drift = DriftMap(self.xams_drift_map)

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        if not len(d):
            return out
        x, y, z = d["x"] * 10.0, d["y"] * 10.0, d["z"] * 10.0            # cm -> mm (drift map)
        m = self.drift.at(x, y, z)
        end = m["end"].astype(np.int8)
        gas = d["vol_id"] == 3
        end[gas] = GAS
        t_us = np.where(gas, 0.0, np.nan_to_num(m["t_us"])).astype(float)
        path = np.nan_to_num(m["path_mm"]).astype(float)
        survival = np.where(end == SURFACE, np.exp(-t_us / float(self.electron_lifetime_us)), 0.0)
        survival[gas] = 1.0
        n = np.maximum(d["electrons"], 0).astype(np.int64)
        out["n_electron_interface"] = self.rng.binomial(n, survival)
        out["survival"] = survival
        out["drift_end"] = end
        out["drift_time_mean"] = np.round(t_us * 1e3).astype(np.int32)
        # diffusion: D [cm²/s] -> sigma [mm] = sqrt(2 D t) with D*100 mm²/s, t in s
        sig_l = np.sqrt(2.0 * float(self.diffusion_longitudinal_cm2_s) * 100.0 * t_us * 1e-6)
        v = np.where(t_us > 0, path / np.maximum(t_us, 1e-9), 1.0)            # mean velocity mm/µs
        out["drift_time_spread"] = np.round(np.where(t_us > 0, sig_l / v, 0.0) * 1e3).astype(np.int32)
        out["xy_spread"] = np.sqrt(2.0 * float(self.diffusion_transverse_cm2_s) * t_us * 1e-6)   # cm
        xg, yg = m["x_gate"], m["y_gate"]
        out["x_obs"] = np.where(np.isfinite(xg) & ~gas, xg / 10.0, d["x"])
        out["y_obs"] = np.where(np.isfinite(yg) & ~gas, yg / 10.0, d["y"])
        out["z_obs"] = d["z"]
        return out
