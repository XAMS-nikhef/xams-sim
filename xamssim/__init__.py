"""xams-sim: simulation chain of the XAMS TPC (plan: docs/xams_sim_plan.md)."""
import logging as _logging
import time as _time
from pathlib import Path as _Path

# utilix (comes with straxen / fuse) looks for ~/.xenon_config with XENONnT database credentials at import and warns
# when there is none; XAMS uses none of those databases: an empty config file of our own (unless one is set)
import os as _os
_os.environ.setdefault("XENON_CONFIG", str(_Path(__file__).resolve().parent / "xenon_config.ini"))

# personal settings: ~/.config/xamssim/env, lines KEY=VALUE (e.g. XAMSSIM_DATA=..., XAMSSIM_AMSTRAX_STORE=...,
# XAMSSIM_G4_ENV=...), used where the environment does not set them, so that every terminal, Jupyter kernel and condor
# job of a user finds the same data folder (environment variables still win)
_USER_ENV = _Path(_os.environ.get("XAMSSIM_USER_ENV", _Path.home() / ".config" / "xamssim" / "env"))
if _USER_ENV.is_file():
    for _line in _USER_ENV.read_text().splitlines():
        _key, _sep, _value = _line.partition("=")
        if _sep and not _line.lstrip().startswith("#"):
            _os.environ.setdefault(_key.strip(), _os.path.expandvars(_value.strip().strip("\"'")))
_logging.getLogger("utilix").setLevel(_logging.ERROR)

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
