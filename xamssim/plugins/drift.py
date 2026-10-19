"""XamsElectronDrift: the electrons of each cluster from where they are made to the liquid surface (plan S4).

From the state's drift map (xamssim.driftmap): the end point of the electrons, the drift time to the surface, where
they cross the gate, the path length. The electron cloud of a cluster is not a point: its electrons follow their own
field lines and diffuse sideways, so a cloud across a boundary between field lines that reach the surface and field
lines that end on a SiPM or the wall is split. Cloud splitting: the map is read at `cloud_samples` points drawn around
the cluster (Gaussian, sigma = sqrt(track^2 + 2 D t), D_T in x, y and D_L in z, t = the cluster's drift time; all of the
diffusion applied at the start); f = the fraction of the points that reach the surface (cloud_samples = 1: the
cluster's own point, f = 0 or 1). Then per cluster
    survival      f x exp(-t / tau) (lifetime tau of the state); t, gate crossing and path = mean over the points
                  that reach the surface
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

    __version__ = "0.2.0"
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
        (("Fraction of the electron cloud whose field lines reach the surface (cloud splitting)", "surface_fraction"),
         np.float32),
    ] + strax.time_fields

    xams_drift_map = straxen.URLConfig(type=str, help="drift map of the state (<data>/maps/drift/<key>/drift_xyz.npz)")
    electron_lifetime_us = straxen.URLConfig(type=(int, float), help="electron lifetime in the liquid [µs] (state)")
    diffusion_longitudinal_cm2_s = straxen.URLConfig(type=(int, float), help="D_L of the liquid [cm²/s] (materials.yaml)")
    diffusion_transverse_cm2_s = straxen.URLConfig(type=(int, float), help="D_T of the liquid [cm²/s] (materials.yaml)")
    cloud_samples = straxen.URLConfig(type=int, help="points per cluster for the cloud splitting (1: no splitting)")
    cloud_track_sigma_mm = straxen.URLConfig(type=(int, float), help="size of the ionization track (Gaussian sigma) [mm]")
    z_liquid_cm = straxen.URLConfig(type=(int, float), help="liquid surface z [cm]")

    def setup(self):
        super().setup()
        self.drift = DriftMap(self.xams_drift_map)

    def _cloud(self, x, y, z):
        """Map values averaged over the electron cloud of each cluster: f, t, path, gate crossing, end code."""
        K = max(int(self.cloud_samples), 1)
        c = self.drift.at(x, y, z)
        if K == 1:
            f = (c["end"] == SURFACE).astype(float)
            return f, c["t_us"], c["path_mm"], c["x_gate"], c["y_gate"], c["end"]
        # drift time for the cloud size: the cluster's own, else from its depth at the nominal speed (lost clusters)
        t0 = np.where(np.isfinite(c["t_us"]), c["t_us"], (self.z_liquid_cm * 10.0 - z) / 1.5).clip(0, None)
        s_t = np.sqrt(float(self.cloud_track_sigma_mm) ** 2 + 2.0 * float(self.diffusion_transverse_cm2_s) * 100.0 * t0 * 1e-6)
        s_l = np.sqrt(float(self.cloud_track_sigma_mm) ** 2 + 2.0 * float(self.diffusion_longitudinal_cm2_s) * 100.0 * t0 * 1e-6)
        n = len(x)
        g = self.rng.normal(size=(n, K, 3))
        px = (x[:, None] + g[..., 0] * s_t[:, None]).ravel()
        py = (y[:, None] + g[..., 1] * s_t[:, None]).ravel()
        pz = np.minimum(z[:, None] + g[..., 2] * s_l[:, None], self.z_liquid_cm * 10.0 - 1e-3).ravel()
        m = self.drift.at(px, py, pz)
        ok = (m["end"] == SURFACE).reshape(n, K)
        f = ok.mean(axis=1)
        def mean_ok(a):
            a = np.where(ok, np.nan_to_num(a.reshape(n, K).astype(float)), 0.0)
            return np.where(ok.any(axis=1), a.sum(axis=1) / np.maximum(ok.sum(axis=1), 1), np.nan)
        end = np.where(ok.any(axis=1), SURFACE, c["end"])                 # lost completely: the cluster's own end point
        return f, mean_ok(m["t_us"]), mean_ok(m["path_mm"]), mean_ok(m["x_gate"]), mean_ok(m["y_gate"]), end

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        if not len(d):
            return out
        x, y, z = d["x"] * 10.0, d["y"] * 10.0, d["z"] * 10.0            # cm -> mm (drift map)
        f, t_c, path_c, xg, yg, end = self._cloud(x, y, z)
        end = np.asarray(end).astype(np.int8)
        gas = d["vol_id"] == 3
        end[gas] = GAS
        f = np.where(gas, 1.0, f)
        t_us = np.where(gas, 0.0, np.nan_to_num(t_c)).astype(float)
        path = np.nan_to_num(path_c).astype(float)
        survival = np.where(end == SURFACE, f * np.exp(-t_us / float(self.electron_lifetime_us)), 0.0)
        survival[gas] = 1.0
        out["surface_fraction"] = f
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
        out["x_obs"] = np.where(np.isfinite(xg) & ~gas, xg / 10.0, d["x"])
        out["y_obs"] = np.where(np.isfinite(yg) & ~gas, yg / 10.0, d["y"])
        out["z_obs"] = d["z"]
        return out
