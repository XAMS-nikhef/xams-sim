"""XAMS volumes: which part of the detector each cluster is in, its xenon density and whether its electrons are kept.

Replaces fuse's VolumeProperties / VolumeSelection, whose options are named after XENONnT and which know only three
volumes (fuse keeps two of them). All four volumes lie inside the field-cage radius:

    vol_id  name           z range                               density   electrons kept
    1       tpc            cathode -> gate                       liquid    yes  (drift region)
    2       below_cathode  bottom PMT window -> cathode          liquid    no   (light only)
    3       gas_phase      liquid surface -> top PMT window      gas       yes  (what they give: S4 / S5)
    4       above_gate     gate -> liquid surface                liquid    yes

Lower bounds inclusive, upper bounds exclusive (as fuse's in_cylinder); outside the radius: vol_id 0, dropped.
Ids 1-3 are fuse's (fuse.common.VOLUMES_IDS), so fuse plugins further down read them as usual.
"""
from __future__ import annotations

import numpy as np
import strax
import straxen
from fuse.common import VOLUMES_IDS
from fuse.dtypes import volume_properties_fields
from fuse.plugin import FuseBasePlugin
from fuse.plugins.micro_physics.volume_properties import in_cylinder

export, __all__ = strax.exporter()

XAMS_VOLUME_IDS = {**VOLUMES_IDS, "above_gate": 4}
VOLUME_NAMES = {1: "drift region", 2: "below cathode", 3: "gas", 4: "above gate"}
ELECTRONS_KEPT = {1: True, 2: False, 3: True, 4: True}


@export
class XamsVolumeProperties(FuseBasePlugin):
    """vol_id, xe_density and create_S2 (electrons kept) per cluster, from the XAMS geometry and state."""

    __version__ = "0.2.0"
    depends_on = "clustered_interactions"
    provides = "volume_properties"
    dtype = volume_properties_fields + strax.time_fields

    z_gate_cm = straxen.URLConfig(type=(int, float), help="gate mesh z [cm] (geometry.yaml)")
    z_cathode_cm = straxen.URLConfig(type=(int, float), help="cathode mesh z [cm] (geometry.yaml)")
    z_liquid_cm = straxen.URLConfig(type=(int, float), help="liquid surface z [cm] (gate + liquid level of the state)")
    z_bottom_pmt_cm = straxen.URLConfig(type=(int, float), help="bottom PMT window z [cm] (geometry.yaml)")
    z_top_pmt_cm = straxen.URLConfig(type=(int, float), help="top PMT window z [cm] (geometry.yaml)")
    r_field_cage_cm = straxen.URLConfig(type=(int, float), help="inner radius of the PTFE cylinder [cm] (geometry.yaml)")
    density_liquid_g_cm3 = straxen.URLConfig(type=(int, float), help="liquid xenon density (materials.yaml)")
    density_gas_g_cm3 = straxen.URLConfig(type=(int, float), help="gas xenon density (materials.yaml)")

    def compute(self, clustered_interactions):
        c = clustered_interactions
        out = np.zeros(len(c), dtype=self.dtype)
        out["time"], out["endtime"] = c["time"], c["endtime"]
        if not len(c):
            return out
        r = float(self.r_field_cage_cm)
        zones = (  # (vol_id, z_min, z_max, density)
            (1, self.z_cathode_cm, self.z_gate_cm, self.density_liquid_g_cm3),
            (2, self.z_bottom_pmt_cm, self.z_cathode_cm, self.density_liquid_g_cm3),
            (4, self.z_gate_cm, self.z_liquid_cm, self.density_liquid_g_cm3),
            (3, self.z_liquid_cm, self.z_top_pmt_cm, self.density_gas_g_cm3),
        )
        for vid, lo, hi, rho in zones:
            m = in_cylinder(c["x"], c["y"], c["z"], float(lo), float(hi), r)
            out["vol_id"][m] = vid
            out["xe_density"][m] = float(rho)
            out["create_S2"][m] = ELECTRONS_KEPT[vid]
        return out


@export
class XamsVolumeSelection(strax.CutPlugin):
    """Keep clusters in the four XAMS volumes (vol_id 1-4)."""

    __version__ = "0.2.0"
    depends_on = "volume_properties"
    provides = "volume_selection"
    cut_name = "volume_selection"
    cut_description = "cluster in one of the four XAMS volumes"

    def cut_by(self, clustered_interactions):          # data kind of volume_properties
        return np.isin(clustered_interactions["vol_id"], list(VOLUME_NAMES))
