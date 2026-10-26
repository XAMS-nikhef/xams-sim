"""Light maps: the probability that a photon made at a position gives a photoelectron in each channel (plan S6).

Made with the Geant4 optical mode (geometry.yaml, the optics of materials.yaml, the liquid level of the state):
photons uniform in a cylinder of the field-cage radius, isotropic, 178 nm; a photon counts when it is detected on a
sensor (photocathode with the QE of geometry.yaml, SiPM with its PDE), so the map includes the QE. Edge bins mostly
outside the cylinder take the value of the nearest bin inside.

    s1_light    S1: photons in the liquid, (x, y, z) grid of 2 x 2 x 2 mm from the bottom screen to the liquid surface
    s2_pattern  S2: photons in the gas gap (liquid surface to anode, uniform in z), (x, y) grid of 1 x 1 mm
    s1_outer    S1 of the liquid outside the TPC: in the PTFE bucket (to its wall, from its bottom to the surface)
                without the TPC cylinder (field-cage radius, bottom screen to surface): between the PTFE wall and
                the bucket, above the PTFE top edge, under the TPC. (x, y, z) grid of 4 x 4 x 4 mm; photons uniform in
                the liquid xenon of that region (source shape "liquid", rejection with the Geant4 navigator); emitted
                per voxel from its liquid fraction (Geant4 section scans: material per point). Only for clusters there
                (volume "outer liquid" of the chain: S1 only, no electrons at the gate).

Per voxel and channel: detected / emitted (emitted from the uniform source density and the part of the voxel inside the
cylinder). Channels: CHANNELS (sensor id of xamsg4: 0 bottom PMT, 1-4 top-PMT sectors = ch1-ch4, 6 / 7 SiPMs at the
azimuths of geometry.yaml). Registry files `<data>/maps/s1_light/<key>/s1.npz`, `s2_pattern/<key>/s2.npz` (one key:
both depend on the geometry, the optics and the level only, not on the voltages).

    xamssim maps --state sept --export light [--photons-s1 5e7 --photons-s2 1e8 --jobs 8]   (~3 min on 8 cores)

Both maps are smoothed with a Gaussian of SMOOTH_MM in x, y (not in z): the light pattern on the sensors changes over
~10 mm, the bin-to-bin noise of the raw map (S2 at 2e7 photons: ~12 % per 1 mm bin and top sector) scrambles the
small differences between neighbouring gate holes in the top-PMT pattern. The defaults (MODEL) are part of the light
key; other --photons values overwrite the map under the same key (remake the strax light products then).
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
SMOOTH_MM = 2.0                  # Gaussian smoothing in x, y (statistical noise; the light pattern changes over ~10 mm)
PHOTONS_S1, PHOTONS_S2 = 5e7, 1e8
MODEL = (f"lightmap v2: Geant4 optical, S1 {PHOTONS_S1:.0e} / S2 {PHOTONS_S2:.0e} photons, bins {S1_STEP_MM} / "
         f"{S2_STEP_MM} mm, smoothed sigma {SMOOTH_MM} mm in x, y")      # part of the light key (config.map_inputs)
FILES = {"s1_light": "s1.npz", "s2_pattern": "s2.npz"}
OUTER_STEP_MM, OUTER_SMOOTH_MM, PHOTONS_OUTER = 4.0, 4.0, 2e8
OUTER_MODEL = (f"outer liquid v1: Geant4 optical, source 'liquid' (LXe of the bucket without the TPC cylinder), "
               f"{PHOTONS_OUTER:.0e} photons, bins {OUTER_STEP_MM} mm, liquid fraction from section scans, smoothed "
               f"sigma {OUTER_SMOOTH_MM} mm within the liquid")         # part of the s1_outer key (config.map_inputs)


def _region(res: Resolved) -> dict:
    from .driftmap import geometry_numbers
    g = geometry_numbers(res)
    z_anode = next(m["z_mm"] for m in res.geometry["meshes"] if m["name"] == "anode")
    return dict(r=g["r_cage"], s1_z=(g["z_bottom_screen"], g["z_surface"]), s2_z=(g["z_surface"], z_anode))


def outer_region(res: Resolved) -> dict:
    """The liquid outside the TPC: bucket radius and liquid z range (bucket bottom to surface), the excluded TPC
    cylinder (field-cage radius, bottom screen to surface). As XamsGeometry.cc builds it."""
    from .driftmap import geometry_numbers
    g = geometry_numbers(res)
    b = res.geometry["ptfe_bucket"]
    z_rim = g["z_surface"] + b["weir_below_rim_mm"]
    z_lo = z_rim - b["height_mm"] + (b.get("bottom_thickness_mm") or 10.0)
    return dict(r=b["inner_diameter_mm"] / 2, z=(z_lo, g["z_surface"]),
                excl_r=g["r_cage"], excl_z=(g["z_bottom_screen"], g["z_surface"]))


def _liquid_fraction(res: Resolved, cfg: Path, work: Path, xe, ye, ze, reg: dict, sub_z: int = 4, step: float = 0.5):
    """Part of each (x, y, z) voxel that is liquid xenon of the outer region: Geant4 section scans (xy planes, sub_z per
    voxel layer, points every `step` mm), material LXe and outside the excluded TPC cylinder."""
    lines = ["/run/verbose 0", "/run/initialize"]
    zs = []
    for k in range(len(ze) - 1):
        for j in range(sub_z):
            z = ze[k] + (j + 0.5) * (ze[k + 1] - ze[k]) / sub_z
            zs.append(z)
            lines.append(f"/xamsg4/section {work / f'sec_{len(zs) - 1}.bin'} xy {z:.4f} {xe[0] + step / 2:.4f} "
                         f"{xe[-1] - step / 2:.4f} {ye[0] + step / 2:.4f} {ye[-1] - step / 2:.4f} {step}")
    mac = work / "sections.mac"
    mac.write_text("\n".join(lines + [""]))
    with open(work / "sections.log", "w") as f:
        rc = subprocess.run(g4bin.command(["-c", cfg, "-o", work / "sec_dummy.bin", "-s", 1, "-d", mac]),
                            cwd=g4bin.BUILD, stdout=f, stderr=subprocess.STDOUT).returncode
    if rc:
        raise RuntimeError(f"Geant4 section scans failed: see {work / 'sections.log'}")
    nx, ny, nz = len(xe) - 1, len(ye) - 1, len(ze) - 1
    frac = np.zeros((nx, ny, nz))
    for i, z in enumerate(zs):
        f = work / f"sec_{i}.bin"
        meta = json.loads(Path(str(f) + ".json").read_text())
        m = np.fromfile(f, dtype=np.uint16).reshape(meta["nv"], meta["nu"]).T          # (u = x, v = y)
        lxe = np.array([meta["materials"].get(meta["volumes"][str(k)]) == "LXe" for k in range(len(meta["volumes"]))])
        u = meta["umin"] + step * np.arange(meta["nu"])
        v = meta["vmin"] + step * np.arange(meta["nv"])
        ok = lxe[m]
        if reg["excl_z"][0] < z < reg["excl_z"][1]:
            ok &= np.hypot(u[:, None], v[None, :]) >= reg["excl_r"]
        ix = np.clip(np.searchsorted(xe, u) - 1, 0, nx - 1)
        iy = np.clip(np.searchsorted(ye, v) - 1, 0, ny - 1)
        cnt = np.zeros((nx, ny))
        np.add.at(cnt, (ix[:, None].repeat(len(v), 1), iy[None, :].repeat(len(u), 0)), ok.astype(float))
        npts = np.zeros((nx, ny))
        np.add.at(npts, (ix[:, None].repeat(len(v), 1), iy[None, :].repeat(len(u), 0)), 1.0)
        frac[:, :, i // sub_z] += cnt / np.maximum(npts, 1) / sub_z
    return frac


def compute_outer(res: Resolved, photons: float = PHOTONS_OUTER, jobs: int = 8, seed: int = 5000,
                  work: Path | None = None, log=print) -> dict:
    """The s1_outer map (see the module doc)."""
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    reg = outer_region(res)
    r, step = reg["r"], OUTER_STEP_MM
    work = work or (MAPS / "_work_outer")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    try:
        files = _run_geant4(res, work, "liquid", int(photons), reg["z"], r, jobs, seed, log,
                            extra=[f"/xamsg4/source/exclude_r {reg['excl_r']} mm",
                                   f"/xamsg4/source/exclude_zmin {reg['excl_z'][0]} mm",
                                   f"/xamsg4/source/exclude_zmax {reg['excl_z'][1]} mm"])
        det = _detected(files)
        xe = ye = _edges(-r, r, step)
        ze = _edges(reg["z"][0], reg["z"][1], step)
        ze[-1] = reg["z"][1]
        frac = _liquid_fraction(res, work / "config.json", work, xe, ye, ze, reg)
        vol = frac * step * step * np.diff(ze)[None, None, :]
        emitted = photons * vol / vol.sum()
        good = frac >= 0.3
        w = good.astype(float)
        p = np.zeros((N_CHANNELS,) + frac.shape)
        sig = OUTER_SMOOTH_MM / step
        _, idx = distance_transform_edt(~good, return_indices=True)
        for i, ch in enumerate(CHANNELS):
            d = det[det["sensor"] == ch]
            h, _ = np.histogramdd(np.stack([d["x0"], d["y0"], d["z0"]], axis=1), bins=(xe, ye, ze))
            raw = np.where(good, h / np.maximum(emitted, 1e-12), 0.0)
            # smoothing within the liquid only (normalised convolution), then voxels that are hardly liquid take the
            # value of the nearest liquid voxel (lookups near PTFE / steel)
            sm = gaussian_filter(raw * w, sig, mode="nearest") / np.maximum(gaussian_filter(w, sig, mode="nearest"), 1e-9)
            p[i] = sm[tuple(idx)]
        tot = len(det) / photons
        by = ", ".join(f"{nm} {(det['sensor'] == ch).sum() / photons:.4f}" for nm, ch in zip(CHANNEL_NAMES, CHANNELS))
        log(f"  s1_outer: detected {tot:.4f} of the photons ({by}); liquid volume {vol.sum() / 1e3:.0f} cm3")
        return dict(x=0.5 * (xe[1:] + xe[:-1]), y=0.5 * (ye[1:] + ye[:-1]), z=0.5 * (ze[1:] + ze[:-1]),
                    p=p.astype(np.float32), liquid=frac.astype(np.float32), channels=np.array(CHANNELS),
                    channel_names=np.array(CHANNEL_NAMES), photons=photons, r_mm=r, step_mm=step,
                    exclude_r_mm=reg["excl_r"], exclude_z_mm=np.array(reg["excl_z"]))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def export_outer(res: Resolved, photons: float = PHOTONS_OUTER, jobs: int = 8) -> dict:
    d = compute_outer(res, photons, jobs)
    key = res.map_keys()["s1_outer"]
    rel = f"s1_outer/{key}/s1_outer.npz"
    (MAPS / rel).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(MAPS / rel, **d)
    return register(res, "s1_outer", [rel], producer_version=None)


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


def _smooth(p, step):
    """Gaussian smoothing over x, y (axes 1, 2) of every channel; edge bins already filled from the inside."""
    from scipy.ndimage import gaussian_filter
    sig = [0, SMOOTH_MM / step, SMOOTH_MM / step] + [0] * (p.ndim - 3)
    return gaussian_filter(p, sig, mode="nearest")


def _run_geant4(res: Resolved, work: Path, shape: str, n: int, z: tuple, r: float, jobs: int, seed: int, log,
                extra=()) -> list:
    """Geant4 optical runs in `jobs` parts; returns the record files."""
    cfg = work / "config.json"
    if not cfg.exists():
        subprocess.run([sys.executable, "-m", "xamssim.g4config", "--detector", res.detector,
                        "--level", str(res.state["liquid_level_mm"]),
                        "--out", str(cfg)], check=True, capture_output=True, text=True)
    per = [n // jobs + (1 if k < n % jobs else 0) for k in range(jobs)]
    cmds, files = [], []
    for k, nk in enumerate(per):
        stem = work / f"{shape}_{k}"
        mac = stem.with_suffix(".mac")
        lines = ["/run/verbose 0", "/run/printProgress 0", "/run/initialize", f"/xamsg4/source/shape {shape}",
                 f"/xamsg4/source/rmax {r} mm"]
        if shape in ("cylinder", "liquid"):
            lines += [f"/xamsg4/source/zmin {z[0]} mm", f"/xamsg4/source/zmax {z[1]} mm", *extra]
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


def compute(res: Resolved, photons_s1: float = PHOTONS_S1, photons_s2: float = PHOTONS_S2, jobs: int = 8, seed: int = 1,
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
                                 p=_smooth(_fill_edge(p, frac), step).astype(np.float32), inside=frac.astype(np.float32))
            else:
                emitted = per_area * frac * step ** 2
                p = np.zeros((N_CHANNELS,) + emitted.shape)
                for i, ch in enumerate(CHANNELS):
                    d = det[det["sensor"] == ch]
                    h, _, _ = np.histogram2d(d["x0"], d["y0"], bins=(xe, ye))
                    p[i] = np.where(emitted > 0, h / np.maximum(emitted, 1e-12), 0.0)
                out[kind] = dict(x=0.5 * (xe[1:] + xe[:-1]), y=0.5 * (ye[1:] + ye[:-1]), z_range=np.array(z),
                                 p=_smooth(_fill_edge(p, frac), step).astype(np.float32), inside=frac.astype(np.float32))
            tot = len(det) / n
            by = ", ".join(f"{nm} {(det['sensor'] == ch).sum() / n:.4f}" for nm, ch in zip(CHANNEL_NAMES, CHANNELS))
            log(f"  {kind}: detected {tot:.4f} of the photons ({by})")
            out[kind].update(channels=np.array(CHANNELS), channel_names=np.array(CHANNEL_NAMES), photons=n,
                             r_mm=r, step_mm=step)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


def export(res: Resolved, photons_s1: float = PHOTONS_S1, photons_s2: float = PHOTONS_S2, jobs: int = 8) -> list:
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
