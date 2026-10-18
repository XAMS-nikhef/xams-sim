"""XAMS volumes: which part of the detector each cluster is in, and its xenon density (plan S4: from the drift map).

The region of a cluster follows from where its electrons go (state's drift map, xamssim.driftmap), not from fixed
planes; only the two real boundaries are settings: the liquid surface (liquid / gas) and the inner radius of the PTFE
cylinder (behind it there is no field and no light: no volume).

    vol_id  name           cluster in the liquid inside the field cage whose electrons ...   density
    1       tpc            cross the gate (to the surface), or end on the wall / a SiPM      liquid
    2       below_cathode  drift down to the bottom screen                                    liquid
    3       gas_phase      (cluster in the gas, above the surface)                           gas
    4       above_gate     reach the surface without crossing the gate                       liquid
    0       outside        outside the field-cage radius or the drift map                   (dropped)

NEST gets the electrons of every cluster (create_S2 = True); what happens to them is decided by the drift
(XamsElectronDrift: survival from the end point and the lifetime). Ids 1-3 are fuse's (fuse.common.VOLUMES_IDS).
"""
from __future__ import annotations

import numpy as np
import strax
import straxen
from fuse.common import VOLUMES_IDS
from fuse.dtypes import volume_properties_fields
from fuse.plugin import FuseBasePlugin

from ..driftmap import BOTTOM, SIPM, SURFACE, WALL, DriftMap

export, __all__ = strax.exporter()

XAMS_VOLUME_IDS = {**VOLUMES_IDS, "above_gate": 4}
VOLUME_NAMES = {1: "drift region", 2: "below cathode", 3: "gas", 4: "above gate"}


@export
class XamsVolumeProperties(FuseBasePlugin):
    """vol_id and xe_density per cluster, from the drift map of the state and the liquid surface."""

    __version__ = "0.3.0"
    depends_on = "clustered_interactions"
    provides = "volume_properties"
    dtype = volume_properties_fields + strax.time_fields

    z_liquid_cm = straxen.URLConfig(type=(int, float), help="liquid surface z [cm] (gate + liquid level of the state)")
    r_field_cage_cm = straxen.URLConfig(type=(int, float), help="inner radius of the PTFE cylinder [cm] (geometry.yaml)")
    density_liquid_g_cm3 = straxen.URLConfig(type=(int, float), help="liquid xenon density (materials.yaml)")
    density_gas_g_cm3 = straxen.URLConfig(type=(int, float), help="gas xenon density (materials.yaml)")
    xams_drift_map = straxen.URLConfig(type=str, help="drift map of the state (<data>/maps/drift/<key>/drift_xyz.npz)")

    def setup(self):
        super().setup()
        self.drift = DriftMap(self.xams_drift_map)

    def compute(self, clustered_interactions):
        c = clustered_interactions
        out = np.zeros(len(c), dtype=self.dtype)
        out["time"], out["endtime"] = c["time"], c["endtime"]
        if not len(c):
            return out
        x, y, z = c["x"] * 10.0, c["y"] * 10.0, c["z"] * 10.0            # cm -> mm (drift map)
        dm = self.drift
        inside = ((np.hypot(c["x"], c["y"]) < self.r_field_cage_cm) & (z >= dm.z[0]) & (z <= dm.z[-1]))
        gas = inside & (c["z"] >= self.z_liquid_cm)
        liq = inside & ~gas
        end = dm(x, y, z, "end")
        crossed = dm(x, y, z, "crossed")
        vid = np.zeros(len(c), np.int8)
        vid[gas] = 3
        vid[liq & np.isin(end, (WALL, SIPM))] = 1
        vid[liq & (end == SURFACE) & crossed] = 1
        vid[liq & (end == SURFACE) & ~crossed] = 4
        vid[liq & (end == BOTTOM)] = 2
        out["vol_id"] = vid
        out["xe_density"] = np.where(gas, self.density_gas_g_cm3, np.where(liq, self.density_liquid_g_cm3, 0.0))
        out["create_S2"] = vid > 0
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
