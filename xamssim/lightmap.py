"""Light maps: the probability that a photon made at a position gives a photoelectron in each channel (plan S6).

Made with the Geant4 optical mode (geometry.yaml, the optics of materials.yaml, the liquid level of the state):
photons uniform in a cylinder of the field-cage radius, isotropic, 178 nm; a photon counts when it is detected on a
sensor (photocathode with the QE of geometry.yaml, SiPM with its PDE), so the map includes the QE. Edge bins mostly
outside the cylinder take the value of the nearest bin inside.

    s1_light    S1: photons in the liquid, (x, y, z) grid of 2 x 2 x 2 mm from the bottom screen to the liquid surface
    s2_pattern  S2: photons in the gas gap (liquid surface to anode, uniform in z), (x, y) grid of 1 x 1 mm

Per voxel and channel: detected / emitted (emitted from the uniform source density and the part of the voxel inside the
cylinder). Channels: CHANNELS (sensor id of xamsg4: 0 bottom PMT, 1-4 top-PMT sectors = ch1-ch4, 6 / 7 SiPMs at the
azimuths of geometry.yaml). Registry files `<data>/maps/s1_light/<key>/s1.npz`, `s2_pattern/<key>/s2.npz` (one key:
both depend on the geometry, the optics and the level only, not on the voltages).

    xamssim maps --state sept --export light [--photons-s1 5e7 --photons-s2 2e7 --jobs 8]   (~5 min on 8 cores)

The default statistics give ~10 % per voxel for the bottom PMT (S1) and ~2 % per bin for a top sector (S2); the
plugins interpolate linearly between voxel centres. More photons for precision studies.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import g4bin
from .config import Resolved
from .maps import MAPS, find, register

CHANNELS = (0, 1, 2, 3, 4, 6, 7)
CHANNEL_NAMES = ("bottom", "top_ch1", "top_ch2", "top_ch3", "top_ch4", "sipm_1", "sipm_2")
N_CHANNELS = len(CHANNELS)
S1_STEP_MM, S2_STEP_MM = 2.0, 1.0
FILES = {"s1_light": "s1.npz", "s2_pattern": "s2.npz"}


def _region(res: Resolved) -> dict:
    from .driftmap import geometry_numbers
    g = geometry_numbers(res)
    z_anode = next(m["z_mm"] for m in res.geometry["meshes"] if m["name"] == "anode")
    return dict(r=g["r_cage"], s1_z=(g["z_bottom_screen"], g["z_surface"]), s2_z=(g["z_surface"], z_anode))


def _edges(lo, hi, step):
    n = int(np.ceil((hi - lo) / step - 1e-9))
    return lo + step * np.arange(n + 1)


def _inside_fraction(xe, ye, r, sub=10):
    """Part of each (x, y) bin inside the circle of radius r (sub-sampled)."""
    fx = (xe[:-1, None] + (np.arange(sub) + 0.5)[None, :] / sub * np.diff(xe)[:, None]).ravel()
    fy = (ye[:-1, None] + (np.arange(sub) + 0.5)[None, :] / sub * np.diff(ye)[:, None]).ravel()
    ins = (np.hypot(fx[:, None], fy[None, :]) < r).reshape(len(xe) - 1, sub, len(ye) - 1, sub)
    return ins.mean(axis=(1, 3))


def _fill_edge(p, frac, min_frac=0.3):
    """Bins with less than min_frac of their area inside the cylinder (few photons): value of the nearest bin that is
    mostly inside (x, y; every z and channel)."""
    from scipy.ndimage import distance_transform_edt
    bad = frac < min_frac
    _, (ix, iy) = distance_transform_edt(bad, return_indices=True)
    return p[:, ix, iy]


def _run_geant4(res: Resolved, work: Path, shape: str, n: int, z: tuple, r: float, jobs: int, seed: int, log) -> list:
    """Geant4 optical runs in `jobs` parts; returns the record files."""
    cfg = work / "config.json"
    if not cfg.exists():
        subprocess.run([sys.executable, "-m", "xamssim.g4config", "--level", str(res.state["liquid_level_mm"]),
                        "--out", str(cfg)], check=True, capture_output=True, text=True)
    per = [n // jobs + (1 if k < n % jobs else 0) for k in range(jobs)]
    cmds, files = [], []
    for k, nk in enumerate(per):
        stem = work / f"{shape}_{k}"
        mac = stem.with_suffix(".mac")
        lines = ["/run/verbose 0", "/run/printProgress 0", "/run/initialize", f"/xamsg4/source/shape {shape}",
                 f"/xamsg4/source/rmax {r} mm"]
        if shape == "cylinder":
            lines += [f"/xamsg4/source/zmin {z[0]} mm", f"/xamsg4/source/zmax {z[1]} mm"]
        mac.write_text("\n".join(lines + [f"/run/beamOn {nk}", ""]))
        out = Path(str(stem) + ".bin")
        files.append((out, nk))
        cmds.append((g4bin.command(["-c", cfg, "-o", out, "-s", seed + k, "-d", mac]), Path(str(stem) + ".log")))

    def one(c):
        with open(c[1], "w") as f:
            return subprocess.run(c[0], cwd=g4bin.BUILD, stdout=f, stderr=subprocess.STDOUT).returncode

    t0 = time.time()
    with ThreadPoolExecutor(jobs) as ex:
        rc = list(ex.map(one, cmds))
    if any(rc):
        raise RuntimeError(f"Geant4 optical run failed: see {[str(c[1]) for c, r_ in zip(cmds, rc) if r_]}")
    log(f"  {shape}: {n:.2g} photons in {time.time() - t0:.0f} s ({jobs} parts)")
    return files


def _detected(files):
    from .read_output import read
    rec = np.concatenate([read(f)[0] for f, _ in files])
    return rec[rec["end_code"] == 1]


def compute(res: Resolved, photons_s1: float = 5e7, photons_s2: float = 2e7, jobs: int = 8, seed: int = 1,
            work: Path | None = None, log=print) -> dict:
    reg = _region(res)
    r = reg["r"]
    work = work or (MAPS / "_work_light")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    out = {}
    try:
        for kind, shape, z, n, step in (("s1_light", "cylinder", reg["s1_z"], int(photons_s1), S1_STEP_MM),
                                        ("s2_pattern", "s2", reg["s2_z"], int(photons_s2), S2_STEP_MM)):
            files = _run_geant4(res, work, shape, n, z, r, jobs, seed + (0 if shape == "cylinder" else 1000), log)
            det = _detected(files)
            xe = ye = _edges(-r, r, step)
            frac = _inside_fraction(xe, ye, r)
            per_area = n / (np.pi * r ** 2)                                   # emitted per mm² (summed over z)
            if kind == "s1_light":
                ze = _edges(z[0], z[1], step)
                ze[-1] = z[1]
                emitted = per_area * frac[:, :, None] * step ** 2 * (np.diff(ze) / (z[1] - z[0]))[None, None, :]
                p = np.zeros((N_CHANNELS,) + emitted.shape)
                for i, ch in enumerate(CHANNELS):
                    d = det[det["sensor"] == ch]
                    h, _ = np.histogramdd(np.stack([d["x0"], d["y0"], d["z0"]], axis=1), bins=(xe, ye, ze))
                    p[i] = np.where(emitted > 0, h / np.maximum(emitted, 1e-12), 0.0)
                out[kind] = dict(x=0.5 * (xe[1:] + xe[:-1]), y=0.5 * (ye[1:] + ye[:-1]), z=0.5 * (ze[1:] + ze[:-1]),
                                 p=_fill_edge(p, frac).astype(np.float32), inside=frac.astype(np.float32))
            else:
                emitted = per_area * frac * step ** 2
                p = np.zeros((N_CHANNELS,) + emitted.shape)
                for i, ch in enumerate(CHANNELS):
                    d = det[det["sensor"] == ch]
                    h, _, _ = np.histogram2d(d["x0"], d["y0"], bins=(xe, ye))
                    p[i] = np.where(emitted > 0, h / np.maximum(emitted, 1e-12), 0.0)
                out[kind] = dict(x=0.5 * (xe[1:] + xe[:-1]), y=0.5 * (ye[1:] + ye[:-1]), z_range=np.array(z),
                                 p=_fill_edge(p, frac).astype(np.float32), inside=frac.astype(np.float32))
            tot = len(det) / n
            by = ", ".join(f"{nm} {(det['sensor'] == ch).sum() / n:.4f}" for nm, ch in zip(CHANNEL_NAMES, CHANNELS))
            log(f"  {kind}: detected {tot:.4f} of the photons ({by})")
            out[kind].update(channels=np.array(CHANNELS), channel_names=np.array(CHANNEL_NAMES), photons=n,
                             r_mm=r, step_mm=step)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


def export(res: Resolved, photons_s1: float = 5e7, photons_s2: float = 2e7, jobs: int = 8) -> list:
    d = compute(res, photons_s1, photons_s2, jobs)
    key = res.map_keys()["s1_light"]
    entries = []
    for kind, f in FILES.items():
        rel = f"{kind}/{key}/{f}"
        (MAPS / rel).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(MAPS / rel, **d[kind])
        entries.append(register(res, kind, [rel], producer_version=None))
    return entries


def path(res: Resolved, kind: str) -> Path:
    e = find(kind, res.map_keys()[kind])
    if e is None:
        raise FileNotFoundError(f"no {kind} map for state '{res.state_name}' (key {res.map_keys()[kind]}): "
                                f"xamssim maps --state {res.state_name} --export light")
    return MAPS / e["files"][0]


class LightMap:
    """Per-channel detection probability at positions [mm]: linear interpolation between voxel centres, positions
    outside the grid at its edge."""

    def __init__(self, file):
        d = np.load(file)
        self.axes = [d["x"], d["y"]] + ([d["z"]] if "z" in d.files else [])
        self.p = d["p"]
        if self.p.shape[0] != N_CHANNELS:
            raise ValueError(f"{file}: {self.p.shape[0]} channels, expected {N_CHANNELS}")

    def __call__(self, *pos):
        from scipy.ndimage import map_coordinates
        idx = [np.clip(np.interp(q, a, np.arange(len(a))), 0, len(a) - 1) for q, a in zip(pos, self.axes)]
        return np.stack([map_coordinates(c, idx, order=1, mode="nearest") for c in self.p], axis=1)   # (n, channels)
