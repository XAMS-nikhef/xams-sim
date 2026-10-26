"""Zero field (state zero_field: true): all electrodes at 0 V, S1 only.

Replaces four steps of the chain, with the same data types so that everything downstream (S1 light, waveforms,
events) is unchanged:
    XamsZeroFieldVolumes  volume_properties from the geometry instead of the drift map's field lines: drift region =
                          between cathode and gate inside the PTFE cylinder, below cathode = down to the bottom screen,
                          above gate = gate to the liquid surface, gas above it
    XamsZeroField         electric_field_values: 0 V/cm everywhere (no field map)
    XamsZeroFieldYields   quanta per cluster at zero field (physics.zero_field_yields):
                            nest_gamma    NEST's gamma-ER model at 0 V/cm for every electron-recoil cluster. NEST's beta-ER
                                          model (used with field) is not defined at 0 V/cm (log10 of the field in its
                                          parameters, nestpy 2.0.6 up to NEST master 2026-09); gamma-ER is NEST's only
                                          ER model with a zero-field limit (~90 % light at 662 keV). Per cluster it is a
                                          proxy for an electron of that energy (exact for the summed photoabsorption,
                                          approximate for a lone Compton electron and below the K edge).
                            proportional  the same total quanta per cluster (NEST, W) with a fixed light fraction
                                          (physics.zero_field_light_fraction): no non-proportionality. A bracket.
                          Fluctuations in both: NEST's GetQuanta with the run's width parameters.
    XamsNoDrift           drifted_electrons: no electron reaches the surface (end code "stuck")
    XamsNoExtraction      extracted_electrons: nothing extracted, no S2 photons
"""
from __future__ import annotations

import numpy as np
import nestpy
import strax
import straxen
from fuse.dtypes import electric_fields
from fuse.plugin import FuseBasePlugin
from fuse.plugins.micro_physics.yields import NestYields

from fuse.dtypes import volume_properties_fields

from .drift import XamsElectronDrift
from .extraction import XamsExtractionEL

export, __all__ = strax.exporter()

ER_MODELS = (7, 8, 9, 10)            # nestpy INTERACTION_TYPE: gammaRay, beta, CH3T, C14 -> gammaRay at 0 V/cm
GAMMA = 7
ZERO_FIELD_YIELDS = ("nest_gamma", "proportional")


@export
class XamsZeroFieldVolumes(FuseBasePlugin):
    """vol_id and xe_density per cluster from the geometry (no field lines at zero field)."""

    __version__ = "0.1.0"
    depends_on = "clustered_interactions"
    provides = "volume_properties"
    dtype = volume_properties_fields + strax.time_fields

    z_liquid_cm = straxen.URLConfig(type=(int, float), help="liquid surface z [cm] (gate + liquid level of the state)")
    r_field_cage_cm = straxen.URLConfig(type=(int, float), help="inner radius of the PTFE cylinder [cm] (geometry.yaml)")
    density_liquid_g_cm3 = straxen.URLConfig(type=(int, float), help="liquid xenon density (materials.yaml)")
    density_gas_g_cm3 = straxen.URLConfig(type=(int, float), help="gas xenon density (materials.yaml)")
    z_gate_cm = straxen.URLConfig(type=(int, float), help="gate z [cm]")
    z_cathode_cm = straxen.URLConfig(type=(int, float), help="cathode z [cm]")
    z_bottom_cm = straxen.URLConfig(type=(int, float), help="bottom screen z [cm]: lower end of the volumes")

    def compute(self, clustered_interactions):
        c = clustered_interactions
        out = np.zeros(len(c), dtype=self.dtype)
        out["time"], out["endtime"] = c["time"], c["endtime"]
        if not len(c):
            return out
        z = c["z"]
        inside = (np.hypot(c["x"], c["y"]) < self.r_field_cage_cm) & (z >= self.z_bottom_cm)
        gas = inside & (z >= self.z_liquid_cm)
        vid = np.zeros(len(c), np.int8)
        vid[gas] = 3
        vid[inside & ~gas & (z >= self.z_gate_cm)] = 4
        vid[inside & (z < self.z_gate_cm) & (z >= self.z_cathode_cm)] = 1
        vid[inside & (z < self.z_cathode_cm)] = 2
        out["vol_id"] = vid
        out["xe_density"] = np.where(gas, self.density_gas_g_cm3, np.where(inside, self.density_liquid_g_cm3, 0.0))
        out["create_S2"] = vid > 0
        return out


@export
class XamsZeroField(FuseBasePlugin):
    """|E| = 0 V/cm at every cluster."""

    __version__ = "0.1.0"
    depends_on = "interactions_in_roi"
    provides = "electric_field_values"
    data_kind = "interactions_in_roi"
    save_when = strax.SaveWhen.TARGET
    dtype = electric_fields + strax.time_fields

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        return out


@export
class XamsZeroFieldYields(NestYields):
    """NEST quanta at zero field: gamma-ER per electron-recoil cluster, or fixed light fraction (see module doc)."""

    __version__ = "0.1.0"

    zero_field_yields = straxen.URLConfig(type=str, help="nest_gamma | proportional (physics.zero_field_yields)")
    zero_field_light_fraction = straxen.URLConfig(type=(int, float), help="photons / (photons + electrons) per cluster "
                                                                        "for zero_field_yields = proportional")

    def setup(self):
        super().setup()
        if self.zero_field_yields not in ZERO_FIELD_YIELDS:
            raise ValueError(f"zero_field_yields '{self.zero_field_yields}': one of {ZERO_FIELD_YIELDS}")

    def get_yields_from_NEST(self, en, model, e_field, A, Z, density):
        if model not in ER_MODELS:                       # NR, alphas, ...: NEST's own model at 0 V/cm
            return super().get_yields_from_NEST(en, model, 0.0, A, Z, density)
        y = self.nc.GetYields(interaction=nestpy.INTERACTION_TYPE(GAMMA), energy=en, drift_field=0.0, A=A, Z=Z,
                              density=density, ERYieldsParam=self.nest_er_yields_parameters_list,
                              nuisance_parameters=self.nest_nr_yields_parameters_list)
        if self.zero_field_yields == "proportional":
            nq = y.PhotonYield + y.ElectronYield         # total quanta E / W, independent of the model
            f = float(self.zero_field_light_fraction)
            y.PhotonYield, y.ElectronYield = f * nq, (1.0 - f) * nq
        return y


@export
class XamsNoDrift(FuseBasePlugin):
    """No drift at zero field: no electron reaches the surface; positions = the cluster's own."""

    __version__ = "0.1.0"
    depends_on = "microphysics_summary"
    provides = "drifted_electrons"
    data_kind = "interactions_in_roi"
    save_when = strax.SaveWhen.TARGET
    dtype = XamsElectronDrift.dtype                      # same data type, no drift map or transport options

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        out["x_obs"], out["y_obs"], out["z_obs"] = d["x"], d["y"], d["z"]
        return out                                       # drift_end 0 = "stuck", survival 0, no electrons


@export
class XamsNoExtraction(FuseBasePlugin):
    """No extraction and no S2 photons at zero field."""

    __version__ = "0.1.0"
    depends_on = ("drifted_electrons", "microphysics_summary")
    provides = "extracted_electrons"
    data_kind = "interactions_in_roi"
    save_when = strax.SaveWhen.TARGET
    dtype = XamsExtractionEL.dtype                       # same data type, no extraction / EL map

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        return out
