"""Optical simulation: a scan file describes it; the same file drives the production run and the viewer.

    xamssim optical optical/scans/fit_s2.yaml [--jobs 8] [--dry]   scan -> run/scans/<name>/ (optical/run_scan.py)
    xamssim optical optical/scans/fit_s2.yaml --vis [--point N]    viewer (Qt) for point N of the scan (default 0):
                                                                   its liquid level, parameters and photon source
    xamssim optical optical/scans/fit_s2.yaml --list               the scan points (number + parameter values)

A scan file defines the photon source (s1 / s2, rmax), photons per point, the base config (liquid level, fixed
overrides) and a grid of parameter points (see optical/run_scan.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from . import g4bin
from .config import ROOT, ConfigError


def _spec(scan_file) -> dict:
    scan_file = Path(scan_file)
    if not scan_file.exists():
        raise ConfigError(f"scan file not found: {scan_file} (scans are in optical/scans/)")
    with open(scan_file) as f:
        return yaml.safe_load(f)


def scan(scan_file, jobs: int = 8, dry: bool = False) -> int:
    _spec(scan_file)
    cmd = [sys.executable, str(ROOT / "optical" / "run_scan.py"), str(scan_file), "--jobs", str(jobs)] + (["--dry"] if dry else [])
    return subprocess.run(cmd).returncode


def _points(spec) -> list:
    sys.path.insert(0, str(ROOT / "optical"))
    from run_scan import make_points  # the same points as the production run
    return make_points(spec)


def list_points(scan_file) -> None:
    spec = _spec(scan_file)
    pts = _points(spec)
    keys = list((spec.get("grid") or {}).keys())
    print(f"scan {spec['name']}: {len(pts)} points; source {spec.get('source')} r < {spec.get('rmax_mm', 30)} mm, "
          f"{float(spec['photons']):.2g} photons per point; base {spec.get('base', {})}")
    if not keys:
        print("  point 0: the base configuration (no grid)")
        return
    names = [k.replace("optics.", "") for k in keys]
    w = [max(len(n), 6) for n in names]
    print("  point  " + "  ".join(n.rjust(x) for n, x in zip(names, w)))
    for p in pts:
        print(f"  {p['id']:5d}  " + "  ".join(str(p["params"][k]).rjust(x) for k, x in zip(keys, w)))


def vis(scan_file, point: int = 0) -> None:
    spec = _spec(scan_file)
    points = _points(spec)
    if not 0 <= point < len(points):
        raise ConfigError(f"--point {point}: the scan has points 0 .. {len(points) - 1} (see --list)")
    p = points[point]
    out = (ROOT / "run" / "vis_optical" / f"{spec['name']}_point{point}").resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfg = out / "config.json"
    args = [sys.executable, str(ROOT / "optical" / "make_config.py"), "--level", str(p["level"]), "--out", str(cfg)]
    for k, v in p["set"].items():
        args += ["--set", f"{k}={json.dumps(v)}"]
    subprocess.run(args, check=True, capture_output=True)
    c = json.loads(cfg.read_text())
    c["vis_source"] = {"shape": spec.get("source", "s2"), "rmax_mm": float(spec.get("rmax_mm", 30))}
    cfg.write_text(json.dumps(c, indent=1))
    print(f"viewer: scan {spec['name']}, point {point} of {len(points)} {p['params'] or ''}, level {p['level']} mm, "
          f"source {c['vis_source']['shape']} r < {c['vis_source']['rmax_mm']:g} mm\n  in the window: /run/beamOn 20")
    g4bin.run(["-c", cfg, "-o", out / "photons.bin"])
