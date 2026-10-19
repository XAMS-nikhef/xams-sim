"""xams-sim: simulation chain of the XAMS TPC (plan: docs/xams_sim_plan.md)."""
import time as _time
from pathlib import Path as _Path

__version__ = "0.1.0"

_PKG = _Path(__file__).resolve().parent
_LOADED = _time.time()


def changed_since_import() -> list:
    """xamssim source files changed on disk after this process imported the package (a Jupyter kernel keeps the old
    code until it is restarted)."""
    return sorted(str(p.relative_to(_PKG.parent)) for p in _PKG.rglob("*.py") if p.stat().st_mtime > _LOADED)


def warn_if_stale() -> bool:
    """Print a warning when the code on disk is newer than the code running here; True if so."""
    files = changed_since_import()
    if files:
        print(f"WARNING: xams-sim changed on disk since this kernel / process started ({', '.join(files[:4])}"
              f"{', ...' if len(files) > 4 else ''}): it still runs the old code. Restart the kernel.")
    return bool(files)
