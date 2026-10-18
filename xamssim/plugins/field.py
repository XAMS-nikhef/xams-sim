"""XamsElectricField: the field at each cluster from the state's 3D field map (x, y, z).

Replaces fuse's ElectricField, which looks up (r, z) only: XAMS is not cylindrically symmetric (SiPMs in the wall).
Map: `maps/field/<key>/efield_xyz.npz` (xamssim.fieldmap); trilinear interpolation of |E|, positions outside the grid
moved to its edge.
"""
from __future__ import annotations

import numpy as np
import strax
import straxen
from fuse.dtypes import electric_fields
from fuse.plugin import FuseBasePlugin

from ..fieldmap import FieldMap

export, __all__ = strax.exporter()


@export
class XamsElectricField(FuseBasePlugin):
    """|E| in V/cm at the cluster position (x, y, z in cm) from the 3D field map."""

    __version__ = "0.1.0"
    depends_on = "interactions_in_roi"
    provides = "electric_field_values"
    data_kind = "interactions_in_roi"
    save_when = strax.SaveWhen.TARGET
    dtype = electric_fields + strax.time_fields

    xams_efield_map = straxen.URLConfig(
        type=str, help="3D field map of the state (maps/field/<key>/efield_xyz.npz)",
    )

    def setup(self):
        super().setup()
        self.field = FieldMap(self.xams_efield_map)

    def compute(self, interactions_in_roi):
        d = interactions_in_roi
        out = np.zeros(len(d), dtype=self.dtype)
        out["time"], out["endtime"] = d["time"], d["endtime"]
        if len(d):
            out["e_field"] = self.field(d["x"] * 10.0, d["y"] * 10.0, d["z"] * 10.0)      # cm -> mm
        return out
