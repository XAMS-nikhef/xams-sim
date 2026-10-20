"""Start the XAMS Geant4 program `xamsg4` from any conda environment.

There is one compiled program, g4/build/xamsg4 (optical mode by default, particle mode with -m particle). It needs the
Geant4 libraries and data files of the conda env `g4` (override with $XAMSSIM_G4_ENV: a name, or the path of the env as
on STBC). `command()` returns the command line: the program itself when the Geant4 env is active, otherwise wrapped in
`conda run -n g4` (`-p <path>`). So everything can be run from the `xamssim` env; the `g4` env only has to be
activated to compile (cmake --build g4/build -j8).

Standard library only: imported by the xamssim package and by the optical tools (which may run in either env).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "g4" / "build"
XAMSG4 = BUILD / "xamsg4"
G4_ENV = os.environ.get("XAMSSIM_G4_ENV", "g4")


def in_g4_env() -> bool:
    return shutil.which("geant4-config") is not None and "G4LEDATA" in os.environ


def command(args) -> list:
    """Command line for `xamsg4 <args>` that works from the current environment."""
    if not XAMSG4.exists():
        raise FileNotFoundError(f"{XAMSG4} not built: conda activate {G4_ENV}; cmake -S g4 -B g4/build && cmake --build g4/build -j8")
    cmd = [str(XAMSG4)] + [str(a) for a in args]
    if in_g4_env():
        return cmd
    conda = os.environ.get("CONDA_EXE") or shutil.which("conda") or "conda"
    where = ["-p", G4_ENV] if "/" in G4_ENV else ["-n", G4_ENV]          # a name, or the path of the env (STBC)
    return [conda, "run", *where, "--no-capture-output"] + cmd


def run(args, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run(command(args), **kwargs); the working directory defaults to g4/build (the macros are there)."""
    kwargs.setdefault("cwd", BUILD)
    return subprocess.run(command(args), **kwargs)
