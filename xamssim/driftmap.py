"""Drift map: where an electron from each point of the TPC goes, and how long it takes (plan S4).

The field is the composite field of the state: the full-TPC 3D field map (xamssim.fieldmap; meshes as solid discs)
with, near the gate and the cathode, the field of the real etched mesh from the mesh-cell models (xamssim.cellmap),
tiled over the mesh with its rotation and hole pattern:
    E = E_cell(position in its cell) + [E_full - cell average] (the bracket taken just outside the foil band)
i.e. the cell's hole structure on top of the large-scale field (SiPMs, field cage); far from a mesh E = E_full.
From every grid point inside the field cage an electron is tracked against this field (electrons move along -E),
with the drift velocity v(|E|) of the liquid from NEST, until it
    1 SURFACE  reaches the liquid surface (through the gate, or directly when it starts above the gate)
    2 BOTTOM   goes down to the bottom screen (below the cathode the field points the other way)
    3 WALL     hits the PTFE wall of the field cage (r = inner radius, between gate and cathode)
    4 SIPM     hits the wall at a SiPM (its 3 x 3 mm opening)
    5 GAS      starts in the gas (not tracked here; extraction and EL: S5)
    6 OUT      leaves the map sideways (below the cathode or above the gate, where there is no PTFE)
    7 MESH     ends on a bar of the gate or cathode mesh
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
CODES = {0: "stuck", 1: "surface", 2: "bottom", 3: "wall", 4: "sipm", 5: "gas", 6: "out", 7: "mesh"}
STUCK, SURFACE, BOTTOM, WALL, SIPM, GAS, OUT, MESH = range(8)
STEP_MM = 0.1
STEP_NEAR_MESH_MM = 0.02           # within NEAR_MESH_MM of a mesh plane (holes 2.45 mm, bars 0.15 mm, channels ~0.5 mm)
NEAR_MESH_MM = 1.0
MAX_STEPS = 2500
GRID = dict(dxy=1.0, dz=0.5)


def mesh_holes(geometry: dict) -> set:
    """(i, j) of the etched holes (hole centre at ((i + 1/2) p, (j + 1/2) p) in the mesh frame)."""
    import json
    from .config import CONFIG
    mc = geometry["mesh_common"]
    holes = mc.get("holes")
    if holes is None:
        holes = json.loads((CONFIG / mc["hole_pattern_file"]).read_text())["holes"]
    return {(int(i), int(j)) for i, j in holes}


def geometry_numbers(res: Resolved) -> dict:
    """Everything the tracking needs, from geometry.yaml and the state (mm)."""
    g = res.geometry
    z = {m["name"]: m["z_mm"] for m in g["meshes"]}
    mc = g["mesh_common"]
    ang = {m["name"]: m.get("angle_to_anodes_deg", 0.0) for m in g["meshes"]}
    pt = g["ptfe_cylinder"]
    sp = g["sipms"]
    pz = [p["window_z_mm"] for p in g["pmts"]]
    return dict(z_gate=z["gate"], z_cathode=z["cathode"], z_bottom_screen=z["bottom_screen"],
                z_surface=z["gate"] + res.state["liquid_level_mm"],
                r_cage=pt["inner_diameter_mm"] / 2, z_ptfe_top=pt["z_top_mm"], z_ptfe_bottom=pt["z_top_mm"] - pt["length_mm"],
                sipm_phi=np.radians(sp["azimuth_deg"]), sipm_z=np.array(sp["z_mm"], float), sipm_half=sp["active_mm"][0] / 2,
                z_min=min(pz), z_max=max(pz),
                meshes={n: dict(z=z[n], angle=np.radians(ang[n])) for n in ("gate", "cathode")},
                pitch=mc["pitch_mm"], hole=mc["hole_size_mm"], foil=mc["foil_thickness_mm"], holes=mesh_holes(g))


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


class _Cell:
    """The field of one etched mesh from its quarter-cell model, tiled over the mesh (rotation, hole pattern)."""

    def __init__(self, data: dict, prefix: str, mesh: dict, geo: dict):
        self.u, self.z = data[f"{prefix}_u"], data[f"{prefix}_z"]
        self.c = [np.nan_to_num(data[f"{prefix}_{k}"]).astype(np.float32) for k in ("Ex", "Ey", "Ez")]
        self.mean = data[f"{prefix}_mean"]
        self.z0, self.cos, self.sin = mesh["z"], np.cos(mesh["angle"]), np.sin(mesh["angle"])
        self.p, self.hole, self.foil, self.holes = geo["pitch"], geo["hole"], geo["foil"], geo["holes"]
        self.du, self.dz = self.u[1] - self.u[0], self.z[1] - self.z[0]
        ij = np.array(sorted(self.holes))
        self.off = int(np.abs(ij).max()) + 1
        self.hmask = np.zeros((2 * self.off + 1, 2 * self.off + 1), bool)
        self.hmask[ij[:, 0] + self.off, ij[:, 1] + self.off] = True

    def window(self, z):
        zl = z - self.z0
        return (zl >= self.z[0]) & (zl <= self.z[-1])

    def local(self, p):
        """Mesh-frame cell coordinates: (u, v) relative to the hole centre, z_loc, hole index (i, j), in-hole flag."""
        xm = self.cos * p[:, 0] + self.sin * p[:, 1]                # world -> mesh frame (mesh rotated by +angle)
        ym = -self.sin * p[:, 0] + self.cos * p[:, 1]
        i, j = np.floor(xm / self.p).astype(int), np.floor(ym / self.p).astype(int)
        u, v = xm - (i + 0.5) * self.p, ym - (j + 0.5) * self.p
        inside = (np.abs(i) < self.off) & (np.abs(j) < self.off)
        etched = np.zeros(len(i), bool)
        etched[inside] = self.hmask[i[inside] + self.off, j[inside] + self.off]
        return u, v, p[:, 2] - self.z0, etched

    def on_bar(self, p):
        u, v, zl, etched = self.local(p)
        in_slab = np.abs(zl) <= self.foil / 2
        in_hole = etched & (np.abs(u) < self.hole / 2) & (np.abs(v) < self.hole / 2)
        return in_slab & ~in_hole

    def field(self, p, full):
        """Composite field at points inside the window: cell field + (full field - cell average) outside the foil."""
        from scipy.ndimage import map_coordinates
        u, v, zl, etched = self.local(p)
        iu = np.abs(u) / self.du
        iv = np.abs(v) / self.du
        iz = (zl - self.z[0]) / self.dz
        idx = np.stack([np.clip(iu, 0, len(self.u) - 1), np.clip(iv, 0, len(self.u) - 1), np.clip(iz, 0, len(self.z) - 1)])
        fu, fv, fz = (map_coordinates(c, idx, order=1, mode="nearest") for c in self.c)
        fu, fv = np.sign(u) * fu, np.sign(v) * fv                     # mirror symmetry of the quarter cell
        fx = self.cos * fu - self.sin * fv                           # mesh frame -> world
        fy = self.sin * fu + self.cos * fv
        cell = np.stack([fx, fy, fz], axis=1)
        # large-scale correction: full field minus the cell's uniform field, both just outside the foil band
        zc = np.where(zl >= 0, np.maximum(zl, 0.6), np.minimum(zl, -0.6))
        q = p.copy()
        q[:, 2] = self.z0 + zc
        mean = np.stack([np.interp(zc, self.z, self.mean[k]) for k in range(3)], axis=1)
        mx = self.cos * mean[:, 0] - self.sin * mean[:, 1]
        my = self.sin * mean[:, 0] + self.cos * mean[:, 1]
        out = cell + full(q) - np.stack([mx, my, mean[:, 2]], axis=1)
        # outside the etched pattern the foil is solid: keep the full-model field there
        solid = ~etched
        if solid.any():
            out[solid] = full(p[solid])
        return out


class _Composite:
    """Full-TPC field, with the mesh cells near the gate and the cathode."""

    def __init__(self, field_file, cells_file, geo: dict):
        self.full = _Field(field_file)
        self.cells = []
        if cells_file is not None:
            d = dict(np.load(cells_file))
            self.cells = [_Cell(d, n, geo["meshes"][n], geo) for n in ("gate", "cathode")]

    def __call__(self, p):
        out = self.full(p)
        for c in self.cells:
            w = c.window(p[:, 2])
            if w.any():
                out[w] = c.field(p[w], self.full)
        return out

    def near_mesh(self, z):
        return np.any([np.abs(z - c.z0) < NEAR_MESH_MM for c in self.cells], axis=0) if self.cells else np.zeros(len(z), bool)

    def on_bar(self, p):
        hit = np.zeros(len(p), bool)
        for c in self.cells:
            w = np.abs(p[:, 2] - c.z0) <= c.foil / 2
            if w.any():
                hit[w] |= c.on_bar(p[w])
        return hit


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
        ds = np.where(field.near_mesh(q[:, 2]), STEP_NEAR_MESH_MM, step_mm) if hasattr(field, "near_mesh") else step_mm
        q_new = q + d * (ds if np.ndim(ds) == 0 else ds[:, None])
        dt = np.where(ok, ds / np.maximum(v, 1e-6), 0.0)
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
        path[active] += np.where(ok, ds, 0.0)
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
        if hasattr(field, "on_bar"):
            bar = (code < 0) & field.on_bar(q_new)
            code[bar] = MESH
        done = code >= 0
        end[active[done]] = code[done]
        active = active[~done]
        if k % 500 == 0:
            log(f"  step {k}: {len(active)} electrons still drifting ({time.time() - t0:.0f} s)")
    return dict(end=end, t_us=t.astype(np.float32), x_gate=xg.astype(np.float32), y_gate=yg.astype(np.float32),
                crossed=crossed, path_mm=path.astype(np.float32), end_xyz=p.astype(np.float32))


def compute(res: Resolved, field_file=None, cells_file="registry", dxy: float = GRID["dxy"], dz: float = GRID["dz"],
            log=print) -> dict:
    """The drift map of a state in its composite field (field_file: another full field map, e.g. in tests;
    cells_file: mesh-cell fields, "registry" = the state's registered ones, None = meshes as solid discs)."""
    from . import cellmap, fieldmap
    geo = geometry_numbers(res)
    field = _Composite(field_file or fieldmap.path(res), cellmap.path(res) if cells_file == "registry" else cells_file, geo)
    x = np.round(np.arange(-geo["r_cage"], geo["r_cage"] + 1e-9, dxy), 4)
    z = np.round(np.arange(geo["z_min"], geo["z_max"] + 1e-9, dz), 4)
    X, Y, Z = np.meshgrid(x, x, z, indexing="ij")
    inside = np.hypot(X, Y) < geo["r_cage"]
    start = np.stack([X[inside], Y[inside], Z[inside]], axis=1)
    log(f"drift map, state {res.state_name}: {inside.sum()} start points ({len(x)} x {len(x)} x {len(z)} grid)")
    tr = track(field, geo, start, velocity_table(res), max_steps=MAX_STEPS + 1000 * bool(field.cells), log=log)
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
    return register(res, "drift", [rel], producer_version=f"xamssim driftmap v2 (composite field), step {STEP_MM} / "
                                                          f"{STEP_NEAR_MESH_MM} mm")


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
