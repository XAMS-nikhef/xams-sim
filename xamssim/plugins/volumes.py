"""XAMS volumes: fuse's three volumes plus the liquid between the gate and the surface; all four are simulated.

fuse knows the drift region (`tpc`), `below_cathode` and `gas_phase`, and its VolumeSelection keeps only the first two.
In XAMS the liquid above the gate (gate -> surface, 4 mm at the nominal level) and the gas gap matter: both give an S1
and electrons with (almost) no drift time. Here:

    vol_id  name           z range (r < field-cage radius)      density   electrons kept (create_S2)
    1       tpc            cathode -> gate                      liquid    yes
    2       below_cathode  bottom PMT window -> cathode         liquid    no
    3       gas_phase      liquid surface -> top PMT window     gas       yes (what they give: S4 / S5)
    4       above_gate     gate -> liquid surface               liquid    yes
"""
from __future__ import annotations

import numpy as np
import strax
import straxen
from fuse.common import VOLUMES_IDS
from fuse.plugins.micro_physics.cuts_and_selections.detector_volumes import VolumeSelection
from fuse.plugins.micro_physics.volume_properties import VolumeProperties, in_cylinder

export, __all__ = strax.exporter()

XAMS_VOLUME_IDS = {**VOLUMES_IDS, "above_gate": 4}
VOLUME_NAMES = {1: "drift region", 2: "below cathode", 3: "gas", 4: "above gate"}


@export
class XamsVolumeProperties(VolumeProperties):
    """fuse's VolumeProperties plus the liquid between the gate and the surface (vol_id 4)."""

    __version__ = "0.1.0"

    create_S2_above_gate = straxen.URLConfig(
        default=True, type=bool,
        help="Electrons of clusters between the gate and the liquid surface are kept",
    )

    def compute(self, clustered_interactions):
        result = super().compute(clustered_interactions)
        if len(clustered_interactions) == 0:
            return result
        c = clustered_interactions
        m = in_cylinder(c["x"], c["y"], c["z"], float(self.xenonnt_z_gate_mesh), float(self.xenonnt_z_lxe),
                        float(self.xenonnt_sensitive_volume_radius))
        if np.any(m):
            result["vol_id"][m] = XAMS_VOLUME_IDS["above_gate"]
            result["xe_density"][m] = float(self.xenon_density_tpc)
            result["create_S2"][m] = bool(self.create_S2_above_gate)
        return result


@export
class XamsVolumeSelection(VolumeSelection):
    """Keep clusters in all four XAMS volumes."""

    __version__ = "0.1.0"
    accept_volumes = ["tpc", "below_cathode", "gas_phase", "above_gate"]

    def cut_by(self, clustered_interactions):
        ids = [XAMS_VOLUME_IDS[v] for v in self.accept_volumes]
        return np.isin(clustered_interactions["vol_id"], ids)
