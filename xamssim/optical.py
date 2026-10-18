"""Optical simulation: scans (production) and the optical viewer, through the same front door as the particle mode.

    xamssim optical optical/scans/fit_s2.yaml [--jobs 8] [--dry]   scan -> run/scans/<name>/ (optical/run_scan.py)
    xamssim optical --vis --state cmb50 [--level 4.0]              viewer (Qt): S1 / S2 photons, /run/beamOn N

A scan file defines liquid level, parameter grid, photons per point (see optical/run_scan.py). The viewer uses the
liquid level of a detector state (config/states/) unless --level is given.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import g4bin
from .config import ROOT, ConfigError, load_yaml

STATES = ROOT / "config" / "states"


def scan(scan_file, jobs: int = 8, dry: bool = False) -> int:
    scan_file = Path(scan_file)
    if not scan_file.exists():
        raise ConfigError(f"scan file not found: {scan_file} (scans are in optical/scans/)")
    cmd = [sys.executable, str(ROOT / "optical" / "run_scan.py"), str(scan_file), "--jobs", str(jobs)] + (["--dry"] if dry else [])
    return subprocess.run(cmd).returncode


def vis(state: str | None = None, level: float | None = None) -> None:
    if level is None:
        if state is None:
            raise ConfigError("give --state <name> (liquid level from config/states/) or --level <mm>")
        level = float(load_yaml(STATES / f"{state}.yaml")["liquid_level_mm"])
    out = (ROOT / "run" / "vis_optical").resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfg = out / f"config_level{level:g}.json"
    subprocess.run([sys.executable, str(ROOT / "optical" / "make_config.py"), "--level", str(level), "--out", str(cfg)],
                   check=True, capture_output=True)
    args = ["-c", cfg, "-o", out / "photons.bin"]
    print("viewer:", " ".join(g4bin.command(args)),
          "\n  in the window: /run/beamOn 20   (source: /xamsg4/source/shape s2 | s1, see g4/macros/vis_interactive.mac)")
    g4bin.run(args)
