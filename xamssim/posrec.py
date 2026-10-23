"""Monte Carlo study of the position reconstruction (plan S9): a fast toy from the maps, no Geant4, no chain.

    xamssim posrec --state sept [--n 300000] [--sizes 30,300,3000,30000] [--data-map pos_rec_map_v1.json] [--out f.png]

Per event, as in the detector and in amstrax:
  1. a true position, uniform in the drift region (r < field-cage radius, cathode < z < gate);
  2. the drift map of the state: where the electron crosses the gate (x_gate, y_gate) and when (drift time); events
     whose electron does not reach the surface are dropped; transverse diffusion over the drift time is added
     (sigma = sqrt(2 D_T t), D_T of materials.yaml);
  3. the S2 light pattern (s2_pattern map: detection probability per top sector at the extraction position, emitted
     uniformly over the gas gap) -> the expected fractions of the top light in ch1..ch4;
  4. photon statistics for an S2 of N detected top photoelectrons: a multinomial draw over the sectors, plus the
     single-PE area resolution of the top PMT;
  5. u = 2 (ch1 + ch3) / top - 1, v = 2 (ch1 + ch2) / top - 1 (amstrax peak_positions), then (x, y) from a
     (u, v) -> (x, y) map with amstrax's bilinear lookup.

Two maps are compared: the data map (amstrax_files pos_rec_map, the latest range) and a map built here from the MC
(mean extraction position per (u, v) bin of a high-statistics sample; amstrax's format: uv_min, step, n, x, y), which
the command writes as a candidate pos_rec_map (`<data>/posrec/pos_rec_map_mc_<state>.json`). The MC map reconstructs
the *extraction* position; the difference to the true interaction position is the field distortion of the drift.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .config import DATA, Resolved, resolve_state

TOP = (1, 2, 3, 4)                      # s2_pattern channel index of ch1..ch4 (lightmap.CHANNELS = 0, 1, 2, 3, 4, 6, 7)
SPE_RES_TOP = 0.4                       # single-PE area resolution of the top PMT (sensors.yaml order of magnitude)
UV_MIN, UV_STEP, UV_N = -1.0, 0.005, 401  # amstrax pos_rec_map grid


# ---------------------------------------------------------------------------------------------------------- inputs
class Maps:
    """The state's drift map and S2 light pattern, interpolated."""

    def __init__(self, res: Resolved):
        from scipy.interpolate import RegularGridInterpolator as RGI

        from . import driftmap, lightmap
        g = res.geometry
        z = {m["name"]: m["z_mm"] for m in g["meshes"]}
        self.z_gate, self.z_cathode = z["gate"], z["cathode"]
        self.r_cage = g["ptfe_cylinder"]["inner_diameter_mm"] / 2
        s2 = np.load(lightmap.path(res, "s2_pattern"))
        self.light = [RGI((s2["x"], s2["y"]), s2["p"][i], bounds_error=False, fill_value=None) for i in TOP]
        dm = np.load(driftmap.path(res))
        grid = (dm["x"], dm["y"], dm["z"])
        self.end = RGI(grid, dm["end"].astype(float), method="nearest", bounds_error=False, fill_value=0)
        self.xg = RGI(grid, dm["x_gate"], bounds_error=False, fill_value=np.nan)
        self.yg = RGI(grid, dm["y_gate"], bounds_error=False, fill_value=np.nan)
        self.t = RGI(grid, dm["t_us"], bounds_error=False, fill_value=np.nan)
        self.d_t = float(res.materials["materials"]["liquid_xenon"]["transport"]["diffusion_transverse_cm2_s"])

    def fractions(self, x, y):
        q = np.stack([np.clip(f(np.c_[x, y]), 0, None) for f in self.light], axis=1)
        return q / np.maximum(q.sum(axis=1, keepdims=True), 1e-30)


def true_positions(m: Maps, n: int, rng) -> np.ndarray:
    r = m.r_cage * np.sqrt(rng.random(n))
    phi = 2 * np.pi * rng.random(n)
    z = rng.uniform(m.z_cathode + 0.5, m.z_gate - 0.5, n)
    return np.c_[r * np.cos(phi), r * np.sin(phi), z]


def extraction(m: Maps, p: np.ndarray, rng, diffusion: bool = True):
    """Extraction (x, y) of the electrons from true positions; mask of those that reach the surface."""
    from .driftmap import SURFACE
    ok = m.end(p).round() == SURFACE
    xe, ye, t = m.xg(p), m.yg(p), m.t(p)
    ok &= np.isfinite(xe) & np.isfinite(ye) & np.isfinite(t)
    if diffusion:
        sig = np.sqrt(2 * m.d_t * 1e2 * np.clip(np.nan_to_num(t), 0, None) * 1e-6)   # cm²/s -> mm²/µs: x100 x1e-6
        xe = xe + rng.normal(0, 1, len(p)) * sig
        ye = ye + rng.normal(0, 1, len(p)) * sig
    return xe, ye, ok


def uv(m: Maps, xe, ye, n_top: float | None, rng):
    """u, v of S2s at extraction positions (xe, ye) with n_top detected top photoelectrons (None: expected values)."""
    f = m.fractions(xe, ye)
    if n_top is None:
        c = f
    else:
        c = np.array([rng.multinomial(int(n_top), fi) for fi in f], float)
        c = c + rng.normal(0, 1, c.shape) * SPE_RES_TOP * np.sqrt(c)
        c = np.clip(c, 0, None)
    top = np.maximum(c.sum(axis=1), 1e-30)
    return 2 * (c[:, 0] + c[:, 2]) / top - 1, 2 * (c[:, 0] + c[:, 1]) / top - 1


# ---------------------------------------------------------------------------------------------------------- maps
def lookup(u, v, grid: dict):
    """amstrax's grid_lookup: bilinear (u, v) -> (x, y), (u, v) clipped to the grid."""
    u0, step = float(grid["uv_min"]), float(grid["step"])
    gx, gy = np.asarray(grid["x"], float), np.asarray(grid["y"], float)
    n = gx.shape[0]
    fu = (np.clip(u, u0, -u0) - u0) / step
    fv = (np.clip(v, u0, -u0) - u0) / step
    i = np.clip(np.floor(fu).astype(int), 0, n - 2)
    j = np.clip(np.floor(fv).astype(int), 0, n - 2)
    t, s = fu - i, fv - j
    out = []
    for g in (gx, gy):
        out.append((1 - t) * (1 - s) * g[i, j] + t * (1 - s) * g[i + 1, j] + (1 - t) * s * g[i, j + 1] + t * s * g[i + 1, j + 1])
    return out[0], out[1]


def build_map(u, v, x, y, smooth_bins: float = 2.0, min_count: int = 5, r_max: float | None = None,
              n_rays: int = 720, fit_width: float = 0.06) -> dict:
    """(u, v) -> mean (x, y) on amstrax's grid.

    Cells with at least `min_count` events get the mean position of their events. Beyond the simulated range (and in
    poorly filled cells at the edge) the map is extrapolated along rays from the centre of the (u, v) plane: per
    direction, the radius of the last `fit_width` (in |(u, v)|) of well-filled cells is fitted with a straight line in
    |(u, v)| and continued outwards at the azimuth of the edge, capped at `r_max` (the PTFE wall). So events whose
    light sharing lies beyond what the simulation covered are spread up to the wall, not piled up at the map's border.
    Isolated empty cells inside take the nearest filled cell. Then a light Gaussian smoothing (`smooth_bins` cells)."""
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    edges = UV_MIN - UV_STEP / 2 + UV_STEP * np.arange(UV_N + 1)
    cnt, _, _ = np.histogram2d(u, v, bins=(edges, edges))
    sx, _, _ = np.histogram2d(u, v, bins=(edges, edges), weights=x)
    sy, _, _ = np.histogram2d(u, v, bins=(edges, edges), weights=y)
    filled = cnt >= min_count
    mx = np.where(filled, sx / np.maximum(cnt, 1), np.nan)
    my = np.where(filled, sy / np.maximum(cnt, 1), np.nan)
    c = UV_MIN + UV_STEP * np.arange(UV_N)
    U, V = np.meshgrid(c, c, indexing="ij")
    rho, theta = np.hypot(U, V), np.arctan2(V, U)
    if r_max is None:
        r_max = float(np.nanmax(np.hypot(mx, my)))
    # per ray: the edge of the well-filled region and the radial slope there
    ab = ((theta + np.pi) / (2 * np.pi) * n_rays).astype(int) % n_rays
    rho_edge = np.full(n_rays, np.nan); r_edge = np.full(n_rays, np.nan)
    slope = np.full(n_rays, np.nan); phi_edge = np.full(n_rays, np.nan)
    R = np.hypot(mx, my)
    for k in range(n_rays):
        m = (ab == k) & filled
        if m.sum() < 5:
            continue
        re = np.max(rho[m])
        sel = m & (rho > re - fit_width)
        if sel.sum() >= 3 and np.ptp(rho[sel]) > 0:
            b1, b0 = np.polyfit(rho[sel], R[sel], 1)
        else:
            b1, b0 = 0.0, float(np.mean(R[sel]))
        rho_edge[k], slope[k] = re, max(b1, 0.0)
        r_edge[k] = b0 + b1 * re
        far = sel & (rho > re - fit_width / 3)
        phi_edge[k] = np.arctan2(np.mean(my[far]), np.mean(mx[far]))
    ok = np.isfinite(rho_edge)                                      # rays without data: from their neighbours
    idx = np.arange(n_rays)
    for arr in (rho_edge, r_edge, slope, phi_edge):
        if arr is phi_edge:
            cs, sn = np.interp(idx, idx[ok], np.cos(arr[ok]), period=n_rays), np.interp(idx, idx[ok], np.sin(arr[ok]), period=n_rays)
            arr[:] = np.arctan2(sn, cs)
        else:
            arr[:] = np.interp(idx, idx[ok], arr[ok], period=n_rays)
    outside = ~filled & (rho >= rho_edge[ab])
    rr = np.minimum(r_edge[ab] + slope[ab] * (rho - rho_edge[ab]), r_max)
    mx = np.where(outside, rr * np.cos(phi_edge[ab]), mx)
    my = np.where(outside, rr * np.sin(phi_edge[ab]), my)
    holes = ~np.isfinite(mx)                                        # isolated empty cells inside
    if holes.any():
        _, (ii, jj) = distance_transform_edt(holes, return_indices=True)
        mx, my = mx[ii, jj], my[ii, jj]
    mx, my = gaussian_filter(mx, smooth_bins), gaussian_filter(my, smooth_bins)
    rr = np.hypot(mx, my)                                           # the smoothing must not push past the wall
    f = np.where(rr > r_max, r_max / np.maximum(rr, 1e-9), 1.0)
    mx, my = mx * f, my * f
    return dict(uv_min=UV_MIN, step=UV_STEP, n=UV_N, x=np.round(mx, 3).tolist(), y=np.round(my, 3).tolist())


def data_map(name: str = "pos_rec_map_v1.json") -> dict:
    """The latest range of an amstrax_files position map (local file or from amstrax_files on GitHub)."""
    p = Path(name)
    if p.exists():
        d = json.loads(p.read_text())
    else:
        import amstrax
        d = amstrax.get_correction(name)
    key = sorted(k for k in d if d[k] is not None)[-1]
    return d[key]


# ---------------------------------------------------------------------------------------------------------- study
def run(state: str = "sept", n: int = 300_000, sizes=(30, 300, 3000, 30000), data_map_name: str = "pos_rec_map_v1.json",
        seed: int = 1, out: str | None = None) -> dict:
    rng = np.random.default_rng(seed)
    res = resolve_state(state)
    m = Maps(res)
    p = true_positions(m, n, rng)
    xe, ye, ok = extraction(m, p, rng)
    p, xe, ye = p[ok], xe[ok], ye[ok]
    print(f"{state}: {ok.mean():.1%} of the electrons reach the surface; {len(p)} events")

    # the MC map: high statistics (n_top 1e5) per event, extraction position as reference
    u_hi, v_hi = uv(m, xe, ye, 1e5, rng)
    mc = build_map(u_hi, v_hi, xe, ye, r_max=m.r_cage)
    dm = data_map(data_map_name)
    folder = DATA / "posrec"
    folder.mkdir(parents=True, exist_ok=True)
    mc_file = folder / f"pos_rec_map_mc_{state}.json"
    mc_file.write_text(json.dumps({"000000-999999": mc}))

    r_true = np.hypot(p[:, 0], p[:, 1])
    r_ext = np.hypot(xe, ye)
    summary = dict(state=state, events=len(p), reach_surface=float(ok.mean()), mc_map=str(mc_file), maps={})
    results = {}
    for name, grid in (("data map", dm), ("MC map", mc)):
        per = {}
        for size in sizes:
            u, v = uv(m, xe, ye, size, rng)
            x, y = lookup(u, v, grid)
            per[size] = dict(x=x, y=y)
        results[name] = per
        hi = per[max(sizes)]
        rr = np.hypot(hi["x"], hi["y"])
        edges = np.linspace(0, m.r_cage, 8)
        rows = []
        for lo, up in zip(edges[:-1], edges[1:]):
            s = (r_ext >= lo) & (r_ext < up)
            rows.append(dict(r=(lo + up) / 2, bias_vs_extraction=float(np.median(rr[s] - r_ext[s])),
                             bias_vs_true=float(np.median(rr[s] - r_true[s]))))
        res_by_size = {int(sz): float(np.sqrt(np.mean((per[sz]["x"] - xe) ** 2 + (per[sz]["y"] - ye) ** 2) / 2))
                       for sz in sizes}
        summary["maps"][name] = dict(radial=rows, resolution_mm=res_by_size)

    if out is not None or True:
        f = figure(m, p, xe, ye, results, sizes, state)
        out = Path(out) if out else folder / f"posrec_{state}.png"
        f.savefig(out, dpi=120)
        summary["figure"] = str(out)
    (folder / f"posrec_{state}.json").write_text(json.dumps(summary, indent=1))
    _print(summary)
    return summary


def _print(s: dict) -> None:
    print(f"MC map: {s['mc_map']}; figure: {s.get('figure')}")
    for name, d in s["maps"].items():
        print(f"{name}: radial bias (median r_reco - r) for the largest S2, per r of the extraction position:")
        print("   r [mm]  " + "  ".join(f"{row['r']:5.1f}" for row in d["radial"]))
        print("   vs extr " + "  ".join(f"{row['bias_vs_extraction']:+5.1f}" for row in d["radial"]))
        print("   vs true " + "  ".join(f"{row['bias_vs_true']:+5.1f}" for row in d["radial"]))
        print("   resolution per coordinate [mm] vs S2 top PE: " +
              ", ".join(f"{k}: {v:.2f}" for k, v in d["resolution_mm"].items()))


def figure(m: Maps, p, xe, ye, results, sizes, state):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    big = max(sizes)
    fig, ax = plt.subplots(2, 3, figsize=(16, 10))
    # (a, b) arrows extraction -> reconstructed for a subset, data map and MC map
    rng = np.random.default_rng(3)
    sel = rng.choice(len(xe), size=min(700, len(xe)), replace=False)
    for k, name in enumerate(("data map", "MC map")):
        a = ax[0, k]
        r = results[name][big]
        a.quiver(xe[sel], ye[sel], r["x"][sel] - xe[sel], r["y"][sel] - ye[sel], angles="xy", scale_units="xy", scale=1,
                 width=0.002, color="tab:blue" if k == 0 else "tab:green")
        a.add_patch(plt.Circle((0, 0), m.r_cage, fill=False, color="0.4"))
        a.set(xlim=(-36, 36), ylim=(-36, 36), aspect="equal", xlabel="x [mm]", ylabel="y [mm]",
              title=f"{name}: extraction → reconstructed ({big} top PE)")
    # (c) r reconstructed vs r of the extraction position
    a = ax[0, 2]
    re = np.hypot(xe, ye)
    for name, c in (("data map", "tab:blue"), ("MC map", "tab:green")):
        rr = np.hypot(results[name][big]["x"], results[name][big]["y"])
        edges = np.linspace(0, m.r_cage + 2, 20)
        mid = 0.5 * (edges[1:] + edges[:-1])
        med = [np.median(rr[(re >= lo) & (re < up)]) if np.any((re >= lo) & (re < up)) else np.nan
               for lo, up in zip(edges[:-1], edges[1:])]
        a.plot(mid, med, "o-", color=c, ms=3, label=name)
    a.plot([0, m.r_cage], [0, m.r_cage], "k:", lw=0.8)
    a.axvline(m.r_cage, color="0.6", lw=0.6)
    a.set(xlabel="r of the extraction position [mm]", ylabel="median reconstructed r [mm]",
          title=f"radial response ({big} top PE)")
    a.legend(fontsize=8)
    # (d) resolution vs S2 size
    a = ax[1, 0]
    for name, c in (("data map", "tab:blue"), ("MC map", "tab:green")):
        sig = [np.sqrt(np.mean((results[name][s]["x"] - xe) ** 2 + (results[name][s]["y"] - ye) ** 2) / 2) for s in sizes]
        a.plot(sizes, sig, "o-", color=c, label=name)
    a.set(xscale="log", yscale="log", xlabel="S2 top photoelectrons", ylabel="rms per coordinate [mm]",
          title="resolution (vs extraction position)")
    a.legend(fontsize=8)
    # (e) true interaction -> extraction (field distortion of the drift)
    a = ax[1, 1]
    rt = np.hypot(p[:, 0], p[:, 1])
    h = a.hist2d(rt, re - rt, bins=[np.linspace(0, m.r_cage, 60), np.linspace(-15, 5, 80)], cmap="viridis", cmin=1)
    a.set(xlabel="r of the true position [mm]", ylabel="r extraction − r true [mm]",
          title="field distortion of the drift (incl. diffusion)")
    # (f) u, v of the sample
    a = ax[1, 2]
    u, v = uv(m, xe, ye, big, np.random.default_rng(5))
    a.hist2d(u, v, bins=[np.linspace(-1, 1, 200)] * 2, cmap="magma", cmin=1)
    a.set(xlabel="u", ylabel="v", aspect="equal", title="u, v of a uniform sample")
    fig.suptitle(f"Position reconstruction toy, state {state}: uniform in the drift region, drift map, S2 light pattern, "
                 "photon statistics", fontsize=10)
    fig.tight_layout()
    return fig
