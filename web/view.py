"""Whose simulations the app shows: your own (your environment: $XAMSSIM_DATA etc.) or, read-only, someone else's
(a student looking at the private simulations of a colleague).

Set on the app's settings page (the private app, or the app on your own machine; not the central one) or with
`python -m web.view set <folder>`, kept in ~/.xams/sim_view.json (XAMSSIM_WEB_VIEW_FILE):

    {"paths": {"XAMSSIM_DATA": ".../xamssim/data", "XAMSSIM_STUDIES": ".../xamssim/simulations", ...}}
    ({} or no file: your own)

The five paths of a simulation (PARTS): the data folder (Geant4, chain, maps), the run files (studies), the strax
store (exported raw records), live_mc and processed (reconstruction). On STBC they sit together in one folder per user
(users/<name>/xamssim/{data, simulations, strax_data, live_mc, processed}): the page fills all five from that folder
(paths_for), and each can be changed by hand for another layout (the Mac: simulations/ holds the run files and data/).

Only the app uses it: xamssim commands and condor jobs keep your own settings. xamssim.config reads the paths once at
import, so `xamssim web` restarts itself (same process, os.execve) with the other paths in its environment. While it
shows someone else's simulations the app is read-only: no rerun (XAMSSIM_WEB_SUBMIT=0); figures go to a temporary
folder when the data folder is not writable for you.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import threading
from pathlib import Path

VIEWING = "XAMSSIM_WEB_VIEWING"           # data folder shown while it is not the own one (loop guard + banner)
OWN = "XAMSSIM_WEB_OWN"                   # the own environment (json), to switch back
# environment variable -> (subfolder in a simulation folder, label on the page)
PARTS = {"XAMSSIM_DATA": ("data", "data (Geant4, chain, maps)"),
         "XAMSSIM_STUDIES": ("simulations", "run files (studies)"),
         "XAMSSIM_AMSTRAX_STORE": ("strax_data", "strax store (raw records)"),
         "XAMSSIM_LIVE": ("live_mc", "live data (live_mc)"),
         "XAMSSIM_PROCESSED": ("processed", "reconstruction (processed)")}
KEYS = tuple(PARTS) + ("XAMSSIM_WEB_SUBMIT", VIEWING, OWN)
CANDIDATES = "/data/xenon/xams_v2/users/*/xamssim"


def file() -> Path:
    return Path(os.environ.get("XAMSSIM_WEB_VIEW_FILE") or Path.home() / ".xams" / "sim_view.json")


def load() -> dict:
    """The paths of the settings ({} = your own simulations)."""
    try:
        p = json.loads(file().read_text()).get("paths") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    return {k: str(p[k]).strip() for k in PARTS if str(p.get(k) or "").strip()}


def save(paths: dict) -> None:
    f = file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"paths": {k: v for k, v in paths.items() if k in PARTS and v}}, indent=1) + "\n")
    tmp.replace(f)


def allowed() -> bool:
    """Not on the central app (xamsdata): it shows the production simulations."""
    return os.environ.get("XAMSSIM_WEB_ACCESS", "").strip().lower() != "central"


def paths_for(folder: str) -> dict:
    """The five paths of a simulation folder (the STBC layout)."""
    folder = folder.rstrip("/")
    return {k: f"{folder}/{sub}" for k, (sub, _) in PARTS.items()} if folder else {}


def check(paths: dict) -> dict:
    """{variable: why not} for the paths that cannot be shown. The data folder is needed (and the run files: else
    every status is 'unknown'); the others may be missing (nothing exported / reconstructed)."""
    bad = {}
    if paths and not paths.get("XAMSSIM_DATA"):
        bad["XAMSSIM_DATA"] = "the data folder is needed"
    for k, v in paths.items():
        p = Path(v)
        if not p.is_absolute():
            bad[k] = "give an absolute path"
        elif p.exists() and not os.access(p, os.R_OK | os.X_OK):
            bad[k] = "not readable for you"
        elif not p.is_dir() and k in ("XAMSSIM_DATA", "XAMSSIM_STUDIES"):
            bad[k] = "no such folder (or not readable for you)"
        elif p.exists() and not p.is_dir():
            bad[k] = "not a folder"
    return bad


def candidates() -> list:
    """Readable simulation folders of the users on STBC (suggestions on the settings page)."""
    return sorted(p for p in glob.glob(CANDIDATES) if not check({"XAMSSIM_DATA": p + "/data"}))


def _own(env: dict) -> dict:
    return json.loads(env[OWN]) if env.get(OWN) else {k: env.get(k) for k in list(PARTS) + ["XAMSSIM_WEB_SUBMIT"]}


def own_settings() -> bool:
    """The user has a data folder of their own in ~/.config/xamssim/env (XAMSSIM_USER_ENV)."""
    f = Path(os.environ.get("XAMSSIM_USER_ENV") or Path.home() / ".config" / "xamssim" / "env")
    try:
        return any(line.strip().startswith("XAMSSIM_DATA=") for line in f.read_text().splitlines())
    except OSError:
        return False


def _same(a, b) -> bool:
    try:
        return bool(a) and bool(b) and Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b


def environment(env: dict, paths: dict) -> dict | None:
    """The environment the app should run with to show `paths` ({} = the own simulations), or None if `env` already
    is it. Paths whose data folder is the own one count as the own simulations (rerun stays possible)."""
    own = _own(env)
    new = dict(env)
    if paths and not _same(paths.get("XAMSSIM_DATA"), own.get("XAMSSIM_DATA")):
        for k in PARTS:
            if paths.get(k):
                new[k] = paths[k]
            else:
                new.pop(k, None)
        new.update({"XAMSSIM_WEB_SUBMIT": "0", VIEWING: paths["XAMSSIM_DATA"], OWN: json.dumps(own)})
    else:
        for k, v in own.items():
            if v is None:
                new.pop(k, None)
            else:
                new[k] = v
        if paths:                                             # the own data folder, other paths given by hand
            new.update({k: v for k, v in paths.items() if v})
        new.pop(VIEWING, None)
        new.pop(OWN, None)
    return None if all(new.get(k) == env.get(k) for k in KEYS) else new


def restart(env: dict, delay: float = 0.0) -> None:
    """Replace this process by `xamssim web` with the same arguments and `env` (after `delay` s: the answer first)."""
    def go():
        sys.stdout.flush()
        sys.stderr.flush()
        os.execve(sys.executable, [sys.executable] + sys.argv, env)
    if delay:
        threading.Timer(delay, go).start()
    else:
        go()


def _usable() -> dict:
    p = load()
    return {} if check(p) else p


def apply_at_start() -> None:
    """`xamssim web`: restart with the paths of the settings when the environment does not have them yet. Paths that
    cannot be read (any more) are ignored: the app shows the own simulations."""
    if not allowed():
        return
    new = environment(dict(os.environ), _usable())
    if new is not None:
        restart(new)


def exports() -> str:
    """Shell lines that set the environment for the settings (start scripts, before `xamssim web`: a user without
    simulations of their own has no data folder, and xamssim refuses to start without one)."""
    import shlex
    if not allowed():
        return ""
    new = environment(dict(os.environ), _usable()) or {}
    return "".join(f"export {k}={shlex.quote(new[k])}\n" for k in KEYS if k in new and new.get(k) != os.environ.get(k))


def showing() -> dict:
    """For the pages: what is shown and whether it is someone else's."""
    from xamssim.config import DATA, STUDIES
    return {"data": str(DATA), "studies": str(STUDIES), "viewing": os.environ.get(VIEWING, ""),
            "own": _own(dict(os.environ)).get("XAMSSIM_DATA") or "", "allowed": allowed(),
            "paths": {k: os.environ.get(k, "") for k in PARTS}}


if __name__ == "__main__":
    # python -m web.view exports          shell lines for the settings (start scripts)
    # python -m web.view set <folder>     show the simulations in <folder> (STBC layout); "" = your own
    a = sys.argv[1:]
    if a[:1] == ["exports"]:
        print(exports(), end="")
    elif a[:1] == ["set"] and len(a) == 2:
        paths = paths_for(a[1])
        bad = check(paths)
        if bad:
            print("\n".join(f"{k}: {v}" for k, v in bad.items()), file=sys.stderr)
            sys.exit(1)
        save(paths)
        print(f"simulation app shows: {a[1] or 'your own simulations'} (restart it: web/start_stbc.sh)")
    else:
        print(__doc__)
        sys.exit(2)
