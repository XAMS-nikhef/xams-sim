"""strax / fuse plugins of the XAMS chain (plan S3 onwards)."""
import numpy as _np

# fuse 1.6.3 calls np.in1d (lineage clustering, S2 scintillation, S1 propagation), removed in numpy 2.4; np.isin is
# the same function for 1-d input. Remove when fuse is updated (or in our fork).
if not hasattr(_np, "in1d"):
    _np.in1d = _np.isin

from .drift import XamsElectronDrift  # noqa: E402
from .extraction import XamsExtractionEL  # noqa: E402
from .field import XamsElectricField  # noqa: E402
from .input import XamsG4Input, XamsG4Loader  # noqa: E402
from .light import XamsS1Light, XamsS2Light  # noqa: E402
from .sensors import XamsEvents, XamsSensorResponse  # noqa: E402
from .volumes import VOLUME_NAMES, XAMS_VOLUME_IDS, XamsVolumeProperties, XamsVolumeSelection  # noqa: E402

__all__ = ["XamsElectronDrift", "XamsExtractionEL", "XamsElectricField", "XamsG4Input", "XamsG4Loader", "XamsS1Light", "XamsS2Light", "XamsSensorResponse", "XamsEvents", "XamsVolumeProperties", "XamsVolumeSelection", "XAMS_VOLUME_IDS", "VOLUME_NAMES"]
