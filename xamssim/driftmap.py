"""Drift map: where an electron from each point of the TPC goes, and how long it takes (plan S4).

From the state's 3D field map (xamssim.fieldmap) an electron is tracked from every grid point inside the field cage
against the field (electrons move along -E), with the drift velocity v(|E|) of the liquid from NEST, until it
    1 SURFACE  reaches the liquid surface (through the gate, or directly when it starts above the gate)
    2 BOTTOM   goes down to the bottom screen (below the cathode the field points the other way)
    3 WALL     hits the PTFE wall of the field cage (r = inner radius, between gate and cathode)
    4 SIPM     hits the wall at a SiPM (its 3 x 3 mm opening)
    5 GAS      starts in the gas (not tracked here; extraction and EL: S5)
    6 OUT      leaves the map sideways (below the cathode or above the gate, where there is no PTFE)
    0 STUCK    none of these within the step limit (field ~ 0)
Per grid point: end code, drift time to the surface [µs], position where it crosses the gate (x, y) [mm], whether it
crossed the gate (False: it started above the gate), path length [mm], end point.

Registry file `<data>/maps/drift/<key>/drift_xyz.npz`; key = the field inputs + the transport model of the liquid.

    xamssim maps --state sept --export drift          # needs the field map of the state; no COMSOL
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from .config import Resolved
from .maps import MAPS, find, register

FILE = "drift_xyz.npz"
CODES = {0: "stuck", 1: "surface", 2: "bottom", 3: "wall", 4: "sipm", 5: "gas", 6: "out"}
STUCK, SURFACE, BOTTOM, WALL, SIPM, GAS, OUT = range(7)
STEP_MM = 0.1
MAX_STEPS = 2500
GRID = dict(dxy=1.0, dz=0.5)


def geometry_numbers(res: Resolved) -> dict:
    """Everything the tracking needs, from geometry.yaml and the state (mm)."""
    g = res.geometry
    z = {m["name"]: m["z_mm"] for m in g["meshes"]}
    pt = g["ptfe_cylinder"]
    sp = g["sipms"]
    pz = [p["window_z_mm"] for p in g["pmts"]]
    return dict(z_gate=z["gate"], z_cathode=z["cathode"], z_bottom_screen=z["bottom_screen"],
                z_surface=z["gate"] + res.state["liquid_level_mm"],
                r_cage=pt["inner_diameter_mm"] / 2, z_ptfe_top=pt["z_top_mm"], z_ptfe_bottom=pt["z_top_mm"] - pt["length_mm"],
                sipm_phi=np.radians(sp["azimuth_deg"]), sipm_z=np.array(sp["z_mm"], float), sipm_half=sp["active_mm"][0] / 2,
                z_min=min(pz), z_max=max(pz))


def velocity_table(res: Resolved):
    """(|E| grid [V/cm], v [mm/µs]) for the liquid from NEST at the reference temperature and density."""
    import nestpy
    lxe = res.materials["materials"]["liquid_xenon"]
    if lxe.get("transport", {}).get("drift_velocity") != "nest":
        raise ValueError("materials.yaml liquid_xenon.transport.drift_velocity: only 'nest' is implemented")
    nc = nestpy.NESTcalc(nestpy.VDetector())
    e = np.logspace(1, 4.5, 300)                       # below 10 V/cm: v(10 V/cm) (np.interp holds the edge)
    v = np.array([nc.SetDriftVelocity(lxe["temperature_k"], lxe["density_g_cm3"], float(x), 0.0) for x in e])
    return e, v


class _Field:
    """Ex, Ey, Ez [V/cm] at points (mm), trilinear on the field-map grid (map_coordinates: fast for many points)."""

    def __init__(self, file):
        d = np.load(file)
        self.ax = [d["x"], d["y"], d["z"]]
        self.c = [d[k].astype(np.float32) for k in ("Ex", "Ey", "Ez")]
        self.lo = np.array([a[0] for a in self.ax])
        self.step = np.array([a[1] - a[0] for a in self.ax])
        self.n = np.array([len(a) for a in self.ax])

    def __call__(self, p):
        from scipy.ndimage import map_coordinates
        idx = ((p - self.lo) / self.step).T
        idx = np.clip(idx, 0, (self.n - 1)[:, None])
        return np.stack([map_coordinates(c, idx, order=1, mode="nearest") for c in self.c], axis=1)


def track(field, geo: dict, start, vtab, step_mm: float = STEP_MM, max_steps: int = MAX_STEPS, log=print) -> dict:
    """Track electrons from `start` (N, 3) mm against the field; see the module docstring for the end codes."""
    n = len(start)
    p = np.array(start, float)
    end = np.full(n, STUCK, np.int8)
    t = np.zeros(n)
    path = np.zeros(n)
    xg, yg = p[:, 0].copy(), p[:, 1].copy()
    crossed = np.zeros(n, bool)
    gas = p[:, 2] >= geo["z_surface"]
    end[gas] = GAS
    active = np.flatnonzero(~gas)
    e_tab, v_tab = vtab
    t0 = time.time()
    for k in range(max_steps):
        if not len(active):
            break
        q = p[active]
        f = field(q)
        emag = np.linalg.norm(f, axis=1)
        ok = emag > 1e-3
        d = np.zeros_like(f)
        d[ok] = -f[ok] / emag[ok, None]                  # electrons move against E
        v = np.interp(emag, e_tab, v_tab)                # mm/µs
        q_new = q + d * step_mm
        dt = np.where(ok, step_mm / np.maximum(v, 1e-6), 0.0)
        # gate crossing (from below)
        up = (q[:, 2] < geo["z_gate"]) & (q_new[:, 2] >= geo["z_gate"])
        if up.any():
            frac = (geo["z_gate"] - q[up, 2]) / (q_new[up, 2] - q[up, 2])
            ia = active[up]
            xg[ia] = q[up, 0] + frac * (q_new[up, 0] - q[up, 0])
            yg[ia] = q[up, 1] + frac * (q_new[up, 1] - q[up, 1])
            crossed[ia] = True
        p[active] = q_new
        t[active] += dt
        path[active] += np.where(ok, step_mm, 0.0)
        # end conditions
        r = np.hypot(q_new[:, 0], q_new[:, 1])
        z = q_new[:, 2]
        code = np.full(len(active), -1, np.int8)
        code[z >= geo["z_surface"]] = SURFACE
        code[(code < 0) & (z <= geo["z_bottom_screen"])] = BOTTOM
        in_ptfe = (z <= geo["z_ptfe_top"]) & (z >= geo["z_ptfe_bottom"])
        wall = (code < 0) & in_ptfe & (r >= geo["r_cage"])
        if wall.any():
            phi = np.arctan2(q_new[wall, 1], q_new[wall, 0])
            dphi = np.abs((phi[:, None] - geo["sipm_phi"][None, :] + np.pi) % (2 * np.pi) - np.pi)
            at_sipm = ((dphi * geo["r_cage"] <= geo["sipm_half"]) &
                       (np.abs(z[wall, None] - geo["sipm_z"][None, :]) <= geo["sipm_half"])).any(axis=1)
            code[np.flatnonzero(wall)] = np.where(at_sipm, SIPM, WALL)
        code[(code < 0) & ~in_ptfe & (r >= geo["r_cage"] + 4.5)] = OUT
        done = code >= 0
        end[active[done]] = code[done]
        active = active[~done]
        if k % 500 == 0:
            log(f"  step {k}: {len(active)} electrons still drifting ({time.time() - t0:.0f} s)")
    return dict(end=end, t_us=t.astype(np.float32), x_gate=xg.astype(np.float32), y_gate=yg.astype(np.float32),
                crossed=crossed, path_mm=path.astype(np.float32), end_xyz=p.astype(np.float32))


def compute(res: Resolved, field_file=None, dxy: float = GRID["dxy"], dz: float = GRID["dz"], log=print) -> dict:
    """The drift map of a state (field_file: another field map, e.g. in tests; dxy, dz: grid step in mm)."""
    from . import fieldmap
    geo = geometry_numbers(res)
    field = _Field(field_file or fieldmap.path(res))
    x = np.round(np.arange(-geo["r_cage"], geo["r_cage"] + 1e-9, dxy), 4)
    z = np.round(np.arange(geo["z_min"], geo["z_max"] + 1e-9, dz), 4)
    X, Y, Z = np.meshgrid(x, x, z, indexing="ij")
    inside = np.hypot(X, Y) < geo["r_cage"]
    start = np.stack([X[inside], Y[inside], Z[inside]], axis=1)
    log(f"drift map, state {res.state_name}: {inside.sum()} start points ({len(x)} x {len(x)} x {len(z)} grid)")
    tr = track(field, geo, start, velocity_table(res), log=log)
    shape = X.shape
    out = dict(x=x, y=x, z=z)
    fill = {"end": OUT, "t_us": np.nan, "x_gate": np.nan, "y_gate": np.nan, "crossed": False, "path_mm": np.nan}
    for k, v in fill.items():
        a = np.full(shape, v, dtype=tr[k].dtype)
        a[inside] = tr[k]
        out[k] = a
    out["end_xyz"] = np.full(shape + (3,), np.nan, np.float32)
    out["end_xyz"][inside] = tr["end_xyz"]
    out["codes"] = np.array([CODES[i] for i in range(len(CODES))])
    counts = {CODES[c]: int((tr["end"] == c).sum()) for c in CODES}
    log(f"  end points: {counts}")
    return out


def export(res: Resolved) -> dict:
    d = compute(res)
    key = res.map_keys()["drift"]
    rel = f"drift/{key}/{FILE}"
    (MAPS / rel).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(MAPS / rel, **d)
    return register(res, "drift", [rel], producer_version=f"xamssim driftmap, step {STEP_MM} mm")


def path(res: Resolved) -> Path:
    e = find("drift", res.map_keys()["drift"])
    if e is None:
        raise FileNotFoundError(f"no drift map for state '{res.state_name}' (key {res.map_keys()['drift']}): "
                                f"xamssim maps --state {res.state_name} --export drift")
    return MAPS / e["files"][0]


class DriftMap:
    """Look-ups in a drift map at cluster positions (mm): nearest grid point (end codes are discrete)."""

    def __init__(self, file):
        d = np.load(file)
        self.x, self.y, self.z = d["x"], d["y"], d["z"]
        self.d = {k: d[k] for k in ("end", "t_us", "x_gate", "y_gate", "crossed", "path_mm")}

    def index(self, x, y, z):
        def nearest(a, v):
            return np.clip(np.rint((np.asarray(v, float) - a[0]) / (a[1] - a[0])).astype(int), 0, len(a) - 1)
        return nearest(self.x, x), nearest(self.y, y), nearest(self.z, z)

    def __call__(self, x, y, z, what):
        i, j, k = self.index(x, y, z)
        return self.d[what][i, j, k]

    def at(self, x, y, z) -> dict:
        """All quantities at the nearest grid point, the continuous ones moved to the exact position: the gate
        crossing shifted by the offset in x, y; the drift time by the offset in z over the mean velocity."""
        x, y, z = (np.asarray(a, float) for a in (x, y, z))
        i, j, k = self.index(x, y, z)
        r = {key: a[i, j, k] for key, a in self.d.items()}
        r["x_gate"] = r["x_gate"] + (x - self.x[i])
        r["y_gate"] = r["y_gate"] + (y - self.y[j])
        t = r["t_us"].astype(float)
        v = np.where(t > 0, r["path_mm"] / np.where(t > 0, t, 1.0), np.nan)
        r["t_us"] = np.where(np.isfinite(v) & (v > 0), np.maximum(t + (self.z[k] - z) / v, 0.0), t)
        return r
