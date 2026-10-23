"""What the simulation app shows and (later) composes (plan S11).

Phase (a), read-only: which simulations exist and how they were made, from what xams-sim already keeps:
    simulations()          all simulations in the data folder (`xamssim list`): study, run number, state, source, decays,
                           how far, status (current / outdated), size, date of the last chain run
    detail(run)            one simulation: the summary, its provenance records (`xamssim show`), its products
    compare(a, b)          the differing parameters of two simulations (newest provenance record of each)
    figure(run, name)      a figure of the configuration (FIGURES), made once per provenance record and stored next to it
    optical_maps()         the light maps (S1 light, S2 pattern) per optical key, with the optical parameters they used
    map_figure(kind, key)  a figure of a light map (MAP_FIGURES), made once and stored next to the map
Nothing is written except the figure files under <data>/provenance/<run>/figures/ and <data>/maps/<kind>/<key>/figures/.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from . import listing, provenance
from .config import DATA, STUDIES

MESH_HV = {"top_screen": "TS", "anode": "A", "gate": "G", "cathode": "C", "bottom_screen": "BS"}
_CACHE: dict = {}


def _collect(max_age_s: float = 60.0) -> dict:
    """listing.collect(), kept for a minute (it builds the chain contexts to judge current / outdated)."""
    hit = _CACHE.get("collect")
    if hit and time.time() - hit[0] < max_age_s:
        return hit[1]
    d = listing.collect()
    _CACHE["collect"] = (time.time(), d)
    return d


def _how_far(types: set) -> str:
    if "xams_raw_records" in types:
        return "waveforms"
    if "xams_events" in types:
        return "events"
    if types:
        return "partial chain"
    return "Geant4 only"


def _exported(number) -> dict:
    """Whether the run was exported for amstrax (raw records) or written as live data."""
    if number is None:
        return {}
    from . import amstrax_io
    rid = f"{int(number):06d}"
    out = {}
    if amstrax_io.STORE is not None:
        out["raw_records"] = (amstrax_io.STORE / f"{rid}.xamssim.json").exists()
        try:
            from .live import live_root
            out["live_data"] = (live_root(amstrax_io.STORE) / rid / "THE_END").exists()
        except Exception:
            out["live_data"] = False
    return out


def simulations() -> dict:
    """All simulations in the data folder, one row each (plus the data / studies folders and the map overview)."""
    d = _collect()
    rows = []
    for r in d["runs"]:
        prods = r["products"]
        states = {p["state"] for p in prods}
        status = ("outdated" if "old" in states else "unknown" if "?" in states or not r.get("study") else "current")
        if r["g4"] and r.get("g4_key_now") and r["g4"]["key"] != r["g4_key_now"]:
            status = "outdated"
        files = provenance.entries(r["id"])
        size = (r["g4"]["size"] if r["g4"] else 0) + sum(p["size"] for p in prods)
        rows.append(dict(id=r["id"], study=r.get("study", ""), number=r.get("number"), state=r.get("state", ""),
                         source=r.get("source", ""), n_events=r.get("n_events"),
                         g4_events=r["g4"]["events"] if r["g4"] else None,
                         how_far=_how_far({p["type"] for p in prods}), status=status,   # status says whether it is outdated
                         size_mb=size / 1e6, last_run=files[-1].name[:15] if files else "", note=r.get("note", ""),
                         exported=_exported(r.get("number")), n_records=len(files)))
    return dict(rows=rows, data=str(DATA), studies=str(STUDIES), maps=d["maps"])


def records(run_id: str) -> list:
    return [(f, json.loads(f.read_text())) for f in provenance.entries(run_id)]


def summary(rec: dict) -> dict:
    """The parameters that define a simulation, grouped for display."""
    g, s, src, hv = rec["geometry"], rec["state"], rec["source"], rec["hv_case"]
    run = rec["run"]
    c = rec.get("code", {})
    return {
        "run": {"run file": rec["run_file"], "run key": rec["run_key"], "run number": run.get("run_number"),
                "decays": run.get("n_events"), "seed": run.get("seed"), "stop after": run.get("stop_after"),
                "made": rec.get("created")},
        "state": {"state": rec["state_name"], "detector": rec["detector"],
                  "geometry version": g.get("meta", {}).get("version"),
                  "liquid level above gate [mm]": s.get("liquid_level_mm"),
                  "electron lifetime [µs]": rec.get("settings", {}).get("electron_lifetime_us", s.get("electron_lifetime_us")),
                  "pressure [bar]": s.get("pressure_bar"), "HV case": s.get("hv_case")},
        "voltages [V]": {k: hv.get(k) for k in ("TS", "A", "G", "C", "BS") if k in hv},
        "source": {"source": rec["source_name"], "isotope": src.get("isotope"), "position [mm]": src.get("position_mm"),
                   "description": src.get("description")},
        "physics": rec.get("physics", {}),
        "maps": {k: f"{v['key']}" + ("" if v.get("present") else " (missing)") for k, v in rec.get("maps", {}).items()},
        "code": {"commit": (c.get("commit") or "?")[:10], "describe": c.get("describe"),
                 "uncommitted files": len(c.get("uncommitted") or [])},
    }


def detail(run_id: str) -> dict | None:
    rows = {r["id"]: r for r in simulations()["rows"]}
    recs = records(run_id)
    if run_id not in rows and not recs:
        return None
    prods = next((r["products"] for r in _collect()["runs"] if r["id"] == run_id), [])
    rec = recs[-1][1] if recs else None
    return dict(row=rows.get(run_id), record=rec, summary=summary(rec) if rec else None,
                records=[dict(file=f.name, created=r.get("created"), run_key=r.get("run_key"),
                              commit=(r.get("code", {}).get("commit") or "?")[:10]) for f, r in recs],
                products=[dict(type=p["type"], hash=p["hash"], state=p["state"], size_mb=p["size"] / 1e6) for p in prods])


def compare(a: str, b: str) -> list:
    """Differing parameters of two simulations: [(section, path, a, b)], from their newest provenance records."""
    ra, rb = records(a), records(b)
    if not ra or not rb:
        raise FileNotFoundError(f"no provenance for {a if not ra else b}")
    x, y = ra[-1][1], rb[-1][1]
    out = []
    for sec in ("run", "state_name", "state", "source_name", "source", "detector", "hv_case", "physics", "settings",
                "maps", "geometry", "materials"):
        va, vb = x.get(sec), y.get(sec)
        if va == vb:
            continue
        if isinstance(va, dict) and isinstance(vb, dict):
            out += [(sec, k, v1, v2) for k, v1, v2 in provenance.diff(va, vb)]
        else:
            out.append((sec, "", va, vb))
    return out


# ------------------------------------------------------------------------------------------------ figures
def _style(ax):
    ax.set_facecolor("#0f1729")
    for sp in ax.spines.values():
        sp.set_color("#2a3a58")
    ax.tick_params(colors="#9fb4d8")
    ax.xaxis.label.set_color("#dce7ff")
    ax.yaxis.label.set_color("#dce7ff")
    ax.title.set_color("#dce7ff")


def _draw_detector(ax, rec, labels=True, liquid=True):
    """Side cross-section (x-z through the axis): meshes with their voltages, PTFE cylinder, field-shaping rings, PMTs
    with their PTFE holders, the PTFE bucket, SiPMs (at their height, projected), liquid level, source."""
    from matplotlib.patches import Rectangle
    g, hv = rec["geometry"], rec["hv_case"]
    mc = g["mesh_common"]
    r_ring_in, r_ring_out = mc["ring"]["inner_diameter_mm"] / 2, mc["ring"]["outer_diameter_mm"] / 2
    z_gate = next(m["z_mm"] for m in g["meshes"] if m["name"] == "gate")
    level = z_gate + rec["state"]["liquid_level_mm"]
    bucket = g.get("ptfe_bucket", {})
    rb = bucket.get("inner_diameter_mm", 112) / 2
    PTFE = dict(color="#d9d9d9", alpha=0.8, lw=0, zorder=2)
    z_rim = level + bucket.get("weir_below_rim_mm", 0.0)                 # the weir sets the level (as Geant4 builds it)
    z_bucket = z_rim - bucket.get("height_mm", 0.0)
    bot = bucket.get("bottom_thickness_mm") or 10.0                      # g4config default: = wall
    if liquid:
        ax.add_patch(Rectangle((-rb, z_bucket + bot), 2 * rb, level - z_bucket - bot, color="#1d4f7a", alpha=0.35,
                               lw=0, zorder=0))
    if bucket:                                                           # PTFE bucket: wall and bottom
        rbo = bucket["outer_diameter_mm"] / 2
        for x0 in (-rbo, rb):
            ax.add_patch(Rectangle((x0, z_bucket), rbo - rb, z_rim - z_bucket, **PTFE))
        ax.add_patch(Rectangle((-rb, z_bucket), 2 * rb, bot, **PTFE))
        if labels:
            ax.text(rbo + 1, z_bucket + 4, "PTFE bucket", color="#d9d9d9", fontsize=7, va="bottom")
    ax.axhline(level, color="#4db6ff", lw=0.8, ls="--", zorder=1)
    if labels:
        ax.text(-rb + 1, level + 0.6, f"liquid level (gate +{rec['state']['liquid_level_mm']} mm)", color="#4db6ff",
                fontsize=7, ha="left", va="bottom")
    pt = g["ptfe_cylinder"]
    ri, ro = pt["inner_diameter_mm"] / 2, pt["inner_diameter_mm"] / 2 + pt["wall_thickness_mm"]
    for sgn in (-1, 1):
        x0 = sgn * ri if sgn > 0 else -ro
        ax.add_patch(Rectangle((x0, pt["z_top_mm"] - pt["length_mm"]), ro - ri, pt["length_mm"], color="#d9d9d9",
                               alpha=0.8, lw=0, zorder=2))
    fr = g.get("field_shaping_rings", {})
    for zc in fr.get("z_center_mm", []):
        for sgn in (-1, 1):
            x0 = fr["inner_diameter_mm"] / 2 if sgn > 0 else -fr["outer_diameter_mm"] / 2
            ax.add_patch(Rectangle((x0, zc - fr["thickness_mm"] / 2), (fr["outer_diameter_mm"] - fr["inner_diameter_mm"]) / 2,
                                   fr["thickness_mm"], color="#c87533", lw=0, zorder=2))
    foil = mc["foil_diameter_mm"] / 2
    for m in g["meshes"]:
        z = m["z_mm"]
        ax.plot([-foil, foil], [z, z], color="#f1c40f", lw=1.2, zorder=3)
        for sgn in (-1, 1):
            x0 = r_ring_in if sgn > 0 else -r_ring_out
            ax.add_patch(Rectangle((x0, z - mc["ring"]["thickness_mm"] / 2), r_ring_out - r_ring_in,
                                   mc["ring"]["thickness_mm"], color="#8a96a8", lw=0, zorder=3))
        if labels:
            v = hv.get(MESH_HV.get(m["name"], ""), None)
            ax.text(r_ring_out + 2, z, f"{m['name'].replace('_', ' ')}  {v:+g} V" if v is not None else m["name"],
                    color="#f1c40f", fontsize=7, va="center")
    pc = g["pmt_common"]
    half, h = pc["outer_square_mm"] / 2, pc["height_mm"]
    hp = g.get("pmt_ptfe")
    if hp:                                                               # PTFE holders: plate (opening) + surround (slot)
        ro, ap, t_ring = hp["outer_diameter_mm"] / 2, hp["aperture_square_mm"] / 2, mc["ring"]["thickness_mm"] / 2
        zmesh = {m["name"]: m["z_mm"] for m in g["meshes"]}
        for p in g["pmts"]:
            top_pmt = p["name"] == "top"
            w = p["window_z_mm"]
            sl = hp["slot_square_mm"]
            slot = (sl[p["name"]] if isinstance(sl, dict) else sl) / 2
            plate = (zmesh["top_screen"] + t_ring, w) if top_pmt else (w, zmesh["bottom_screen"] - t_ring)
            block = (w, w + h) if top_pmt else (w - h, w)
            for (lo, hi), inner in ((plate, ap), (block, slot)):
                if hi > lo:
                    for x0 in (-ro, inner):
                        ax.add_patch(Rectangle((x0, lo), ro - inner, hi - lo, **PTFE))
        if labels:
            ax.text(ro + 1, max(p["window_z_mm"] for p in g["pmts"]) + 0.75 * h, "PTFE PMT holder", color="#d9d9d9",
                    fontsize=7, ha="left", va="center")
    for p in g["pmts"]:
        z = p["window_z_mm"]
        up = z > z_gate
        ax.add_patch(Rectangle((-half, z if up else z - h), 2 * half, h, color="#6c5ce7", alpha=0.8, lw=0, zorder=2))
        if labels:
            ax.text(-half - 2, z + (h / 2 if up else -h / 2), f"PMT {p['name']}", color="#b3a7ff", fontsize=7,
                    ha="right", va="center")
    sp = g["sipms"]
    az = np.radians(np.atleast_1d(sp["azimuth_deg"]).astype(float))
    for i, (a, zz) in enumerate(zip(az, np.atleast_1d(sp["z_mm"]))):
        in_plane = abs(np.cos(a)) > 0.5                  # this section is the x-z plane through the axis
        x = np.sign(np.cos(a)) * ri if in_plane else ri
        ax.plot([x], [zz], "s" if in_plane else "s", color="#2ecc71", ms=4, mfc="#2ecc71" if in_plane else "none",
                zorder=4)
        if labels:
            ax.text(x + (2 if x < 0 else -2), zz, f"SiPM {i + 1} ({np.degrees(a):.0f}°"      # inwards, off the wall
                    + ("" if in_plane else ", out of plane") + ")", color="#2ecc71", fontsize=6,
                    ha="left" if x < 0 else "right", va="center")
    pos = rec["source"].get("position_mm")
    if pos is not None:
        r = float(np.hypot(pos[0], pos[1]))
        ax.plot([r], [pos[2]], "*", color="#ff6b6b", ms=12, zorder=5)
        if labels:
            ax.text(r, pos[2] + 3, f"source {rec['source'].get('isotope', '')}\nr = {r:.0f} mm, z = {pos[2]:.0f} mm",
                    color="#ff6b6b", fontsize=7, ha="center", va="bottom")
    return level


def fig_cross_section(rec):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pos = rec["source"].get("position_mm") or [0, 0, 0]
    r_src = float(np.hypot(pos[0], pos[1]))
    xmax = max(75.0, r_src + 15)
    b = rec["geometry"].get("ptfe_bucket", {})
    level = rec["state"]["liquid_level_mm"]                              # above the gate (z = 0)
    z_low = level + b.get("weir_below_rim_mm", 0.0) - b.get("height_mm", 0.0) - 5 if b else -80.0
    xlim, ylim = (-xmax, xmax + 30), (min(-80.0, z_low, pos[2] - 15), 45)
    # The figure takes the shape of what is drawn (equal axes): a fixed 9 x 7.5 left a wide detector-plus-source view
    # with blank space above and below it.
    width = 9.0
    height = width * (ylim[1] - ylim[0]) / (xlim[1] - xlim[0]) + 1.4
    fig, ax = plt.subplots(figsize=(width, max(3.5, height)), facecolor="#111b2e")
    _style(ax)
    _draw_detector(ax, rec)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.set(xlabel="x [mm] (source: at its distance r from the axis)", ylabel="z [mm]",
           title=f"{rec['run_id']}: state {rec['state_name']}, detector {rec['detector']}")
    fig.tight_layout()
    return fig


def fig_field(rec):
    """|E| with field lines (state's field map) and where drifting electrons end (drift map), slice y = 0."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, LogNorm

    from .maps import MAPS, find
    fm = rec["maps"].get("field", {})
    e = find("field", fm.get("key", ""))
    if e is None:
        raise FileNotFoundError(f"field map {fm.get('key')} not in the registry")
    f = np.load(MAPS / e["files"][0])
    x, z = f["x"], f["z"]
    iy = int(np.argmin(np.abs(f["y"])))
    ex, ez = f["Ex"][:, iy, :].T, f["Ez"][:, iy, :].T
    emag = np.sqrt(ex ** 2 + f["Ey"][:, iy, :].T ** 2 + ez ** 2)
    fig, axs = plt.subplots(1, 2, figsize=(14, 7), facecolor="#111b2e", gridspec_kw=dict(wspace=0.25))
    for ax in axs:
        _style(ax)
    ax = axs[0]
    m = ax.pcolormesh(x, z, np.clip(emag, 10, None), norm=LogNorm(10, 2e4), cmap="viridis", shading="auto", zorder=0)
    ax.streamplot(x, z, ex, ez, color="w", linewidth=0.4, density=1.4, arrowsize=0.5, zorder=1)
    cb = fig.colorbar(m, ax=ax, fraction=0.04)
    cb.set_label("|E| [V/cm]", color="#dce7ff")
    cb.ax.tick_params(colors="#9fb4d8")
    level = _draw_detector(ax, rec, labels=False, liquid=False)
    ax.set(xlim=(x[0], x[-1]), ylim=(z[0], z[-1]), xlabel="x [mm]", ylabel="z [mm]",
           title="field strength and field lines (y = 0)")
    ax.set_aspect("equal")
    # numbers on the axis (x = y = 0)
    ix = int(np.argmin(np.abs(x)))
    ezx = np.abs(f["Ez"][ix, iy, :])
    g = rec["geometry"]
    zg = next(mm["z_mm"] for mm in g["meshes"] if mm["name"] == "gate")
    zc = next(mm["z_mm"] for mm in g["meshes"] if mm["name"] == "cathode")
    za = next(mm["z_mm"] for mm in g["meshes"] if mm["name"] == "anode")
    sel = lambda lo, hi: np.median(ezx[(z > lo) & (z < hi)]) if np.any((z > lo) & (z < hi)) else np.nan  # noqa: E731
    nums = dict(drift=sel(zc + 5, zg - 5), liquid_above_gate=sel(zg + 0.5, level - 0.3), gas_gap=sel(level + 0.3, za - 0.5))
    ax = axs[1]
    texts = [f"drift field {nums['drift']:.0f} V/cm",
             f"extraction field (liquid) {nums['liquid_above_gate'] / 1e3:.2f} kV/cm",
             f"gas gap {nums['gas_gap'] / 1e3:.2f} kV/cm"]
    dm = rec["maps"].get("drift", {})
    d = find("drift", dm.get("key", ""))
    if d is not None:
        dd = np.load(MAPS / d["files"][0])
        jy = int(np.argmin(np.abs(dd["y"])))
        end = dd["end"][:, jy, :].T.astype(float)
        names = [str(c) for c in dd["codes"]]
        colors = ["#555555", "#2ecc71", "#8e44ad", "#e67e22", "#ff6b6b", "#4db6ff", "#2a3a58", "#f1c40f"]
        ax.pcolormesh(dd["x"], dd["z"], end, cmap=ListedColormap(colors[:len(names)]), vmin=-0.5,
                      vmax=len(names) - 0.5, shading="auto", zorder=0)
        t = dd["t_us"][:, jy, :].T
        cs = ax.contour(dd["x"], dd["z"], np.where(end == 1, t, np.nan), levels=np.arange(0, 60, 5), colors="w",
                        linewidths=0.5, zorder=1)
        ax.clabel(cs, fontsize=6, fmt="%d µs")
        from matplotlib.patches import Patch
        present = sorted(set(np.unique(end[np.isfinite(end)]).astype(int)))
        ax.legend(handles=[Patch(color=colors[k], label=names[k].lower()) for k in present], loc="lower right",
                  fontsize=7, facecolor="#0f1729", labelcolor="#dce7ff", edgecolor="#2a3a58", title="electron ends at",
                  title_fontsize=7)
        ax.set(xlim=(dd["x"][0], dd["x"][-1]), ylim=(dd["z"][0], dd["z"][-1]))
    else:
        texts.append("(no drift map)")
    _draw_detector(ax, rec, labels=False, liquid=False)
    ax.set(xlabel="x [mm]", ylabel="z [mm]", title="where drifting electrons end; drift time to the surface")
    ax.set_aspect("equal")
    fig.suptitle(f"{rec['run_id']}: state {rec['state_name']}  —  " + ",  ".join(texts), color="#dce7ff", fontsize=10)
    return fig


def fig_top_view(rec):
    """Top view (x-y): the gate mesh with its etched holes (rotated by its angle to the anodes), field cage, mesh ring,
    top-PMT sectors with their channels, SiPMs, the direction of the source; right: zoom on the centre."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib import patheffects
    from matplotlib.patches import Circle, Rectangle

    halo = [patheffects.withStroke(linewidth=3, foreground="#0b1220")]
    g = rec["geometry"]
    mc = g["mesh_common"]
    gate = next(m for m in g["meshes"] if m["name"] == "gate")
    a = np.radians(gate.get("angle_to_anodes_deg", 0.0))
    c, s_ = np.cos(a), np.sin(a)
    p, h = mc["pitch_mm"], mc["hole_size_mm"]
    holes = np.array(mc.get("holes") or [], float)
    sq = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * h / 2
    polys = []
    for i, j in holes:                                       # hole centre ((i + 1/2) p, (j + 1/2) p) in the mesh frame
        corners = sq + [(i + 0.5) * p, (j + 0.5) * p]
        polys.append(np.c_[c * corners[:, 0] - s_ * corners[:, 1], s_ * corners[:, 0] + c * corners[:, 1]])
    pt = g["ptfe_cylinder"]
    r_cage = pt["inner_diameter_mm"] / 2
    pc = g["pmt_common"]
    half = float(pc["photocathode_square_mm"]) / 2
    top = next(q for q in g["pmts"] if q["name"] == "top")
    quad = top.get("sector_quadrant", {})
    chan = {v: k for k, v in top.get("sector_to_channel", {}).items()}
    colors = {"ch1": "#e74c3c", "ch2": "#3498db", "ch3": "#2ecc71", "ch4": "#f39c12"}
    fig, axs = plt.subplots(1, 2, figsize=(13, 6.4), facecolor="#111b2e", gridspec_kw=dict(width_ratios=[1.25, 1]))
    for k, ax in enumerate(axs):
        _style(ax)
        for sec, (sx, sy) in quad.items():                  # top-PMT sectors (photocathode quadrants), channel colours
            ch = chan.get(sec, sec)
            ax.add_patch(Rectangle((0 if sx > 0 else -half, 0 if sy > 0 else -half), half, half,
                                   color=colors.get(ch, "#888"), alpha=0.35, lw=0, zorder=0))
            if k == 0:
                ax.text(sx * half / 2, sy * half / 2, f"{ch}\n({sec})", color=colors.get(ch, "#ddd"), fontsize=11,
                        ha="center", va="center", zorder=3, fontweight="bold", path_effects=halo)
        ax.add_patch(Rectangle((-half, -half), 2 * half, 2 * half, fill=False, ec="#b3a7ff", lw=1, zorder=2))
        # the holes as outlines (the steel bars between them), so the sector colours show through
        ax.add_collection(PolyCollection(polys, facecolors="none", edgecolors="#f1c40f", linewidths=0.35 if k == 0 else 1.4,
                                         alpha=0.8, zorder=1))
        ax.add_patch(Circle((0, 0), r_cage, fill=False, ec="#d9d9d9", lw=1.2, zorder=2))
        ax.set_aspect("equal")
    ax = axs[0]
    ax.add_patch(Circle((0, 0), r_cage + pt["wall_thickness_mm"], fill=False, ec="#d9d9d9", lw=0.8, ls="--", zorder=2))
    ax.add_patch(Circle((0, 0), mc["ring"]["outer_diameter_mm"] / 2, fill=False, ec="#8a96a8", lw=1, zorder=2))
    hp, bk = g.get("pmt_ptfe"), g.get("ptfe_bucket")
    if hp:                                                               # PTFE PMT holder: outline and opening
        ax.add_patch(Circle((0, 0), hp["outer_diameter_mm"] / 2, fill=False, ec="#d9d9d9", lw=0.8, ls=":", zorder=2))
        ap = hp["aperture_square_mm"] / 2
        ax.add_patch(Rectangle((-ap, -ap), 2 * ap, 2 * ap, fill=False, ec="#d9d9d9", lw=0.8, ls=":", zorder=2))
    if bk:                                                               # PTFE bucket wall
        from matplotlib.patches import Wedge
        ax.add_patch(Wedge((0, 0), bk["outer_diameter_mm"] / 2, 0, 360, width=(bk["outer_diameter_mm"] - bk["inner_diameter_mm"]) / 2,
                           color="#d9d9d9", alpha=0.5, lw=0, zorder=2))
        ax.text(0, -bk["outer_diameter_mm"] / 2 + 2, "PTFE bucket", color="#d9d9d9", fontsize=8, ha="center", va="bottom",
                zorder=4, path_effects=halo)
    sp = g["sipms"]
    for i, az in enumerate(np.atleast_1d(sp["azimuth_deg"]).astype(float)):
        x, y = r_cage * np.cos(np.radians(az)), r_cage * np.sin(np.radians(az))
        ax.plot([x], [y], "s", color="#2ecc71", ms=7, mec="w", mew=0.6, zorder=4)
        ax.text(x * 0.8, y * 0.8, f"SiPM {i + 1}\n{az:.0f}°", color="#2ecc71", fontsize=8, ha="center", va="center",
                zorder=4, path_effects=halo)
    pos = rec["source"].get("position_mm")
    lim = 70
    if pos is not None:
        r = float(np.hypot(pos[0], pos[1]))
        if r > lim:                                          # outside the view: an arrow towards it
            ux, uy = pos[0] / r, pos[1] / r
            ax.annotate("", xy=(ux * (lim - 4), uy * (lim - 4)), xytext=(ux * (lim - 14), uy * (lim - 14)),
                        arrowprops=dict(arrowstyle="<-", color="#ff6b6b", lw=1.5))
            ax.text(ux * (lim - 9) + 3, uy * (lim - 9), f"source\nr = {r:.0f} mm", color="#ff6b6b", fontsize=8,
                    ha="left", va="center")
        else:
            ax.plot([pos[0]], [pos[1]], "*", color="#ff6b6b", ms=12, zorder=5)
    ax.set(xlim=(-lim, lim), ylim=(-lim, lim), xlabel="x [mm]", ylabel="y [mm]",
           title=f"top view: gate mesh ({len(polys)} holes, {np.degrees(a):.1f}° to the anodes), "
                 f"field cage r {r_cage:.0f} mm, top PMT, PTFE (dotted: PMT holder)")
    z = 3.5 * p
    axs[1].set(xlim=(-z, z), ylim=(-z, z), xlabel="x [mm]", ylabel="y [mm]",
               title=f"centre: pitch {p} mm, holes {h} mm, bars {mc.get('bar_width_mm')} mm")
    axs[1].axhline(0, color="#b3a7ff", lw=0.6)
    axs[1].axvline(0, color="#b3a7ff", lw=0.6)
    fig.suptitle(f"{rec['run_id']}: state {rec['state_name']}, detector {rec['detector']}", color="#dce7ff", fontsize=10)
    return fig


def fig_field_axis(rec):
    """The field along the axis (x = y = 0) and at two radii, from the state's field map: |E| (log) and the potential,
    with the electrodes, the liquid level and the field per region."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .maps import MAPS, find
    fm = rec["maps"].get("field", {})
    e = find("field", fm.get("key", ""))
    if e is None:
        raise FileNotFoundError(f"field map {fm.get('key')} not in the registry")
    f = np.load(MAPS / e["files"][0])
    x, y, z = f["x"], f["y"], f["z"]
    iy = int(np.argmin(np.abs(y)))
    g = rec["geometry"]
    zm = {m["name"]: m["z_mm"] for m in g["meshes"]}
    level = zm["gate"] + rec["state"]["liquid_level_mm"]
    hv = rec["hv_case"]
    fig, (ax, axv) = plt.subplots(1, 2, figsize=(13, 6.4), facecolor="#111b2e", gridspec_kw=dict(width_ratios=[1.6, 1]))
    for a_ in (ax, axv):
        _style(a_)
    shades = [("drift region", zm["cathode"], zm["gate"], "#1d4f7a"), ("liquid above gate", zm["gate"], level, "#2a6f97"),
              ("gas gap", level, zm["anode"], "#3d3d5c")]
    regions = []
    ix0 = int(np.argmin(np.abs(x)))
    emag0 = np.sqrt(f["Ex"][ix0, iy, :] ** 2 + f["Ey"][ix0, iy, :] ** 2 + f["Ez"][ix0, iy, :] ** 2)
    for name, lo, hi, col in shades:
        for a_ in (ax, axv):
            a_.axvspan(lo, hi, color=col, alpha=0.35, lw=0, zorder=0)
        m = (z > lo + 0.3) & (z < hi - 0.3)
        if name == "drift region":
            m = (z > lo + 5) & (z < hi - 5)
        val = float(np.median(emag0[m])) if m.any() else np.nan
        regions.append((name, val))
    for r, col, lab in ((0.0, "#ffffff", "axis"), (15.0, "#4db6ff", "r = 15 mm"), (25.0, "#f39c12", "r = 25 mm")):
        ix = int(np.argmin(np.abs(x - r)))
        em = np.sqrt(f["Ex"][ix, iy, :] ** 2 + f["Ey"][ix, iy, :] ** 2 + f["Ez"][ix, iy, :] ** 2)
        ax.plot(z, np.clip(em, 1, None), color=col, lw=1.4 if r == 0 else 1.0, label=lab, zorder=3)
        axv.plot(z, f["V"][ix, iy, :] / 1e3, color=col, lw=1.4 if r == 0 else 1.0, label=lab, zorder=3)
    for name, zz in zm.items():
        v = hv.get(MESH_HV.get(name, ""))
        for a_ in (ax, axv):
            a_.axvline(zz, color="#f1c40f", lw=1, zorder=2)
        ax.text(zz, 1.2, f"{name.replace('_', ' ')}\n{v:+g} V" if v is not None else name, color="#f1c40f", fontsize=7,
                ha="center", va="bottom", rotation=90, zorder=4)
    for a_ in (ax, axv):
        a_.axvline(level, color="#4db6ff", lw=0.8, ls="--", zorder=2)
        a_.set_xlim(z[0], z[-1])
    ax.set(yscale="log", ylim=(1, 2e4), xlabel="z [mm]", ylabel="|E| [V/cm]",
           title="field strength along z (dashed: liquid level)")
    leg = ax.legend(loc="lower center", fontsize=8, facecolor="#0f1729", labelcolor="#dce7ff", edgecolor="#2a3a58",
                    title="shaded: drift region, liquid above gate, gas gap", title_fontsize=7)
    leg.get_title().set_color("#9fb4d8")
    axv.set(xlabel="z [mm]", ylabel="potential [kV]", title="potential along z")
    fig.suptitle(f"{rec['run_id']}: state {rec['state_name']}  —  " + ",  ".join(
        f"{n} {v / 1e3:.2f} kV/cm" if v >= 1e3 else f"{n} {v:.0f} V/cm" for n, v in regions), color="#dce7ff", fontsize=10)
    return fig


def _events(rec):
    """xams_events of the simulation (the chain's fast output: one row per decay), as made with this record's settings."""
    import contextlib
    import io

    from . import chain
    life = rec.get("settings", {}).get("electron_lifetime_us")
    over = {} if rec["state"].get("electron_lifetime_us") else ({"electron_lifetime_us": float(life)} if life else {})
    with contextlib.redirect_stdout(io.StringIO()):
        st, sid = chain.context(rec["run_file"], **over)
        if not st.is_stored(sid, "xams_events"):
            raise FileNotFoundError(f"no xams_events of {sid} (xamssim chain {rec['run_file']})")
        return st.get_array(sid, "xams_events", progress_bar=False)


def fig_results(rec):
    """The fixed result set of a simulation, from xams_events: energy, cS1 vs cS2, drift time vs depth, S1 / S2 area
    fraction top, photoelectrons per channel."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    from .lightmap import CHANNEL_NAMES
    e = _events(rec)
    both = (e["s1_area"] > 0) & (e["s2_area"] > 0) & np.isfinite(e["cs1"]) & np.isfinite(e["cs2"])
    peak = both & (e["energy_drift"] > 650)
    fig, axs = plt.subplots(2, 3, figsize=(16, 9), facecolor="#111b2e", gridspec_kw=dict(hspace=0.32, wspace=0.42))
    for ax in axs.flat:
        _style(ax)
    cmap, norm = "viridis", LogNorm()

    def cbar(m, ax):
        from matplotlib.ticker import LogLocator, NullFormatter, NullLocator
        c = fig.colorbar(m, ax=ax, fraction=0.045)
        c.ax.yaxis.set_major_locator(LogLocator(base=10))
        c.ax.yaxis.set_minor_locator(NullLocator())
        c.ax.yaxis.set_minor_formatter(NullFormatter())
        c.set_label("events", color="#9fb4d8")
        c.ax.tick_params(colors="#9fb4d8")

    ax = axs[0, 0]
    ed = e["energy_drift"][e["energy_drift"] > 0]
    ax.hist(ed, bins=np.arange(0, 720, 5), histtype="step", color="#4db6ff")
    ax.hist(e["energy_drift"][both], bins=np.arange(0, 720, 5), histtype="step", color="#2ecc71")
    ax.set(yscale="log", xlabel="energy in the drift region [keV]", ylabel="decays / 5 keV",
           title="energy per decay (blue: all, green: with S1 and S2)")
    ax = axs[0, 1]
    if both.any():
        x, y = e["cs1"][both], e["cs2"][both]
        _, _, _, m = ax.hist2d(x, y, bins=[np.linspace(0, np.percentile(x, 99.8), 120),
                                           np.linspace(0, np.percentile(y, 99.8), 120)], norm=norm, cmap=cmap)
        cbar(m, ax)
    ax.set(xlabel="cS1 [PE]", ylabel="cS2 [PE]", title="cS1 vs cS2 (events with S1 and S2)")
    ax = axs[0, 2]
    if both.any():
        _, _, _, m = ax.hist2d(e["z"][both] * 10, e["drift_time"][both], bins=[120, 120], norm=norm, cmap=cmap)
        cbar(m, ax)
    ax.set(xlabel="true depth z [mm]", ylabel="drift time [µs]", title="drift time vs depth")
    ax = axs[1, 0]
    if both.any():
        _, _, _, m = ax.hist2d(e["z"][both] * 10, e["s1_aft"][both], bins=[100, np.linspace(0, 1, 100)], norm=norm, cmap=cmap)
        cbar(m, ax)
    ax.set(xlabel="true depth z [mm]", ylabel="S1 area fraction top", title="S1 AFT vs depth")
    ax = axs[1, 1]
    if both.any():
        r = np.hypot(e["x"][both], e["y"][both]) * 10
        _, _, _, m = ax.hist2d(r, e["s2_aft"][both], bins=[np.linspace(0, 35, 70), np.linspace(0, 1, 100)], norm=norm, cmap=cmap)
        cbar(m, ax)
    ax.set(xlabel="r at the gate [mm]", ylabel="S2 area fraction top", title="S2 AFT vs radius")
    ax = axs[1, 2]
    sel = peak if peak.sum() > 20 else both
    if sel.any():
        k = np.arange(len(CHANNEL_NAMES))
        ax.bar(k - 0.2, e["s1_area_ch"][sel].mean(axis=0), 0.4, color="#4db6ff", label="S1")
        ax.bar(k + 0.2, e["s2_area_ch"][sel].mean(axis=0) / 100, 0.4, color="#f1c40f", label="S2 / 100")
        ax.set_xticks(k, [c.replace("top_", "") for c in CHANNEL_NAMES], rotation=30)
        ax.legend(fontsize=8, facecolor="#0f1729", labelcolor="#dce7ff", edgecolor="#2a3a58")
    ax.set(yscale="log", ylabel="mean PE per event",
           title="PE per channel (" + ("photopeak" if sel is peak else "all S1 + S2") + " events)")
    med = (lambda a: f"{np.median(a):.0f}" if len(a) else "-")
    fig.suptitle(f"{rec['run_id']}: {len(e)} decays with energy in XAMS, {both.sum()} with S1 and S2, {peak.sum()} in the "
                 f"photopeak (> 650 keV in the drift region): median cS1 {med(e['cs1'][peak])} PE, "
                 f"cS2 {med(e['cs2'][peak])} PE", color="#dce7ff", fontsize=10)
    return fig


RESULT_FIGURES = {"results": ("Results (xams_events)", fig_results)}


FIGURE_VERSION = 8              # part of the figure file names: raise it when a figure changes, so old ones are remade
FIGURES = {"cross_section": ("TPC cross-section", fig_cross_section),
           "field": ("Field and drift", fig_field),
           "top_view": ("Top view", fig_top_view),
           "field_axis": ("Field along z", fig_field_axis)}
FIGURE_ROWS = (("cross_section", "field"), ("top_view", "field_axis"))      # how the detail page groups them (one row each)


def figure(run_id: str, name: str) -> Path:
    """PNG of a configuration figure of the newest provenance record, made once and kept next to it."""
    recs = records(run_id)
    if not recs:
        raise FileNotFoundError(f"no provenance for {run_id}")
    f, rec = recs[-1]
    out = f.parent / "figures" / f"{name}_v{FIGURE_VERSION}_{f.stem}.png"
    if not out.exists():
        out.parent.mkdir(exist_ok=True)
        fig = {**FIGURES, **RESULT_FIGURES}[name][1](rec)
        fig.savefig(out, dpi=110, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.15)
        import matplotlib.pyplot as plt
        plt.close(fig)
    return out


# ------------------------------------------------------------------------------------------------ optical maps
# The light maps (lightmap.py: s1_light, s2_pattern) and the optical parameters they were made with, from the map
# registry. One optical key covers both maps (both depend on the geometry, the optics and the level only).
OPTICS_LABELS = {
    "wavelength_nm": "wavelength [nm]",
    "lxe.refractive_index": "LXe refractive index",
    "lxe.rayleigh_length_cm": "LXe Rayleigh length [cm]",
    "lxe.absorption_length_cm": "LXe absorption length [cm]",
    "gxe.refractive_index": "GXe refractive index",
    "ptfe_in_liquid.reflectivity": "PTFE reflectivity, liquid",
    "ptfe_in_liquid.specular_fraction": "PTFE specular fraction, liquid",
    "ptfe_in_gas.reflectivity": "PTFE reflectivity, gas",
    "ptfe_in_gas.specular_fraction": "PTFE specular fraction, gas",
    "stainless_steel_reflectivity": "stainless-steel reflectivity",
    "copper_reflectivity": "copper reflectivity",
    "pmt_window_refractive_index": "PMT window refractive index",
}
OPTICAL_KINDS = ("s1_light", "s2_pattern")
MAP_FIGURE_VERSION = 1


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flatten(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def optics_table(optics: dict) -> dict:
    """{label: value} for the optical parameters, in OPTICS_LABELS order, anything else after it under its key."""
    flat = _flatten(optics or {})
    out = {OPTICS_LABELS[k]: flat[k] for k in OPTICS_LABELS if k in flat}
    out.update({k: v for k, v in flat.items() if k not in OPTICS_LABELS})
    return out


def optical_maps() -> list:
    """One row per optical key: which maps exist, for which state, the liquid level and the optical parameters."""
    from .maps import MAPS, load_manifest
    in_use = {s: {r["key"] for r in v.get("rows", []) if r["kind"] in OPTICAL_KINDS}
              for s, v in (_collect()["maps"].get("states") or {}).items()}
    keys: dict = {}
    for e in load_manifest()["maps"]:
        if e["kind"] not in OPTICAL_KINDS:
            continue
        row = keys.setdefault(e["key"], dict(key=e["key"], kinds={}, states=set(), created=e.get("created", "")[:16],
                                             inputs=e.get("inputs", {})))
        row["kinds"][e["kind"]] = all((MAPS / f).exists() for f in e["files"])
        row["states"].add(e.get("state", ""))
    rows = []
    for key, row in keys.items():
        inp = row.pop("inputs")
        row.update(states=sorted(row["states"]), level_mm=inp.get("liquid_level_mm"), model=inp.get("model", ""),
                   optics=optics_table(inp.get("optics")),
                   used_by=sorted(s for s, ks in in_use.items() if key in ks))
        rows.append(row)
    return sorted(rows, key=lambda r: r["created"], reverse=True)


def optical_map(key: str) -> dict | None:
    return next((r for r in optical_maps() if r["key"] == key), None)


def _map_file(kind: str, key: str) -> Path:
    from .maps import MAPS, find
    e = find(kind, key)
    if e is None:
        raise FileNotFoundError(f"no {kind} map {key}")
    return MAPS / e["files"][0]


def _masked(p, inside):
    return np.ma.masked_where(~inside.astype(bool), p)


def fig_s2_pattern(key: str):
    """S2: the (x, y) map of the detection probability per channel, and the sum."""
    import matplotlib.pyplot as plt
    d = np.load(_map_file("s2_pattern", key))
    p, x, y, inside = d["p"], d["x"], d["y"], d["inside"]
    names = [str(n) for n in d["channel_names"]]
    panels = [("all channels", p.sum(0))] + list(zip(names, p))
    fig, axs = plt.subplots(2, 4, figsize=(13, 6.6), facecolor="#111b2e",
                            gridspec_kw=dict(wspace=0.35, hspace=0.35))
    ext = (x[0], x[-1], y[0], y[-1])
    for ax, (name, img) in zip(axs.flat, panels):
        _style(ax)
        im = ax.imshow(_masked(img, inside).T, origin="lower", extent=ext, cmap="viridis")
        ax.set_title(name, fontsize=10)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=7)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cb.ax.tick_params(labelsize=7, colors="#9fb4d8")
    for ax in axs[1]:
        ax.set_xlabel("x [mm]", fontsize=8)
    for ax in axs[:, 0]:
        ax.set_ylabel("y [mm]", fontsize=8)
    fig.suptitle("S2: probability that a photon from the gas gap gives a photoelectron", color="#dce7ff", fontsize=11)
    return fig


def fig_s1_light(key: str):
    """S1: total detection probability in x-y at three heights and in x-z through the axis, the fraction seen by
    the top PMT in x-z, and the mean over the cylinder versus z."""
    import matplotlib.pyplot as plt
    d = np.load(_map_file("s1_light", key))
    p, x, y, z, inside = d["p"], d["x"], d["y"], d["z"], d["inside"].astype(bool)
    names = [str(n) for n in d["channel_names"]]
    total = p.sum(0)                                               # (x, y, z)
    top = p[[i for i, n in enumerate(names) if n.startswith("top")]].sum(0)
    fig, axs = plt.subplots(2, 3, figsize=(13, 7.6), facecolor="#111b2e",
                            gridspec_kw=dict(wspace=0.35, hspace=0.38))
    ext = (x[0], x[-1], y[0], y[-1])
    vmax = float(total[inside].max())
    for ax, iz in zip(axs[0], (1, len(z) // 2, len(z) - 2)):
        _style(ax)
        im = ax.imshow(_masked(total[:, :, iz], inside).T, origin="lower", extent=ext, cmap="viridis",
                       vmin=0, vmax=vmax)
        ax.set_title(f"all channels, z = {z[iz]:.0f} mm", fontsize=10)
        ax.set_xlabel("x [mm]", fontsize=8)
        ax.set_ylabel("y [mm]", fontsize=8)
        ax.tick_params(labelsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03).ax.tick_params(labelsize=7, colors="#9fb4d8")
    iy = len(y) // 2
    xz_ext = (x[0], x[-1], z[0], z[-1])
    keep = inside[:, iy][:, None]
    for ax, img, title, cmap in ((axs[1, 0], total[:, iy, :], "all channels, y = 0", "viridis"),
                                 (axs[1, 1], np.divide(top[:, iy, :], total[:, iy, :],
                                                       out=np.zeros_like(top[:, iy, :]), where=total[:, iy, :] > 0),
                                  "fraction on the top PMT, y = 0", "magma")):
        _style(ax)
        im = ax.imshow(np.ma.masked_where(~np.broadcast_to(keep, img.shape), img).T, origin="lower",
                       extent=xz_ext, cmap=cmap, aspect="auto")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("x [mm]", fontsize=8)
        ax.set_ylabel("z [mm]", fontsize=8)
        ax.tick_params(labelsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03).ax.tick_params(labelsize=7, colors="#9fb4d8")
    ax = axs[1, 2]
    _style(ax)
    mean = np.array([total[:, :, k][inside].mean() for k in range(len(z))])
    mtop = np.array([top[:, :, k][inside].mean() for k in range(len(z))])
    ax.plot(mean, z, color="#4db6ff", label="all channels")
    ax.plot(mtop, z, color="#f1c40f", label="top PMT")
    ax.set_xlabel("mean detection probability", fontsize=8)
    ax.set_ylabel("z [mm]", fontsize=8)
    ax.set_title("mean over the cylinder", fontsize=10)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=7, facecolor="#0f1729", labelcolor="#dce7ff", edgecolor="#2a3a58")
    fig.suptitle("S1: probability that a photon from the liquid gives a photoelectron", color="#dce7ff", fontsize=11)
    return fig


MAP_FIGURES = {"s2_pattern": ("S2 pattern", fig_s2_pattern), "s1_light": ("S1 light", fig_s1_light)}


def map_figure(kind: str, key: str) -> Path:
    """PNG of an optical map, made once and kept next to the map in the registry."""
    if kind not in MAP_FIGURES:
        raise FileNotFoundError(kind)
    src = _map_file(kind, key)
    out = src.parent / "figures" / f"{kind}_v{MAP_FIGURE_VERSION}.png"
    if not out.exists():
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out.parent.mkdir(exist_ok=True)
        fig = MAP_FIGURES[kind][1](key)
        fig.savefig(out, dpi=100, facecolor=fig.get_facecolor())
        plt.close(fig)
    return out


# ------------------------------------------------------------------------------------------------ DAQ, live data
# What turned the simulated photoelectrons into DAQ data, as the run used it: the DAQ setup of the waveform step (the
# chain's xams_daq setting, stored in the provenance record: digitizer, per-channel settings, single-PE templates,
# scintillation timing) and the live-data layout of the run (its run document, written by xamssim live).

def daq_settings(rec: dict) -> dict | None:
    s = (rec or {}).get("settings", {})
    d = s.get("xams_daq")
    if not d:
        return None
    dig = d["digitizer"]
    chans = []
    for ch, c in sorted(d["channels"].items(), key=lambda kv: int(kv[0])):
        chans.append({"channel": int(ch), "light": c.get("light"), "data": c.get("raw"), "polarity": c.get("polarity"),
                      "threshold [ADC]": c.get("threshold"), "baseline [ADC]": c.get("baseline"),
                      "noise rms [ADC]": c.get("noise"), "gain [ADC·samples / PE]": c.get("gain"),
                      "samples after last crossing": c.get("post_samples")})
    sc = d.get("scintillation", {})
    return {"digitizer": {"model": dig.get("model"), "sampling [ns]": dig.get("dt_ns"), "bits": dig.get("bits"),
                          "record length [samples]": dig.get("record_length"),
                          "pre-trigger [samples]": dig.get("pre_trigger_samples"),
                          "shortest pulse [samples]": dig.get("min_pulse_samples"),
                          "single-PE templates": dig.get("spe_templates")},
            "photoelectrons": {"singlet / triplet [ns]": f"{sc.get('singlet_ns')} / {sc.get('triplet_ns')}",
                               "singlet fraction": sc.get("singlet_fraction"),
                               "PMT transit-time spread [ns]": d.get("pmt_transit_spread_ns"),
                               "SPE resolution": s.get("spe_resolution"),
                               "double-PE probability (PMTs)": s.get("double_pe_probability"),
                               "crosstalk probability (SiPMs)": s.get("crosstalk_probability")},
            "channels": chans}


def _run_doc(number) -> dict | None:
    from . import amstrax_io
    if number is None or amstrax_io.STORE is None:
        return None
    f = Path(amstrax_io.STORE) / f"{int(number):06d}-metadata.json"
    return json.loads(f.read_text()) if f.exists() else None


def live_settings(rec: dict, number) -> dict | None:
    """The live-data layout of a run with a number (its run document) and how many chunks it wrote."""
    doc = _run_doc(number)
    if doc is None:
        return None
    dc = doc.get("daq_config", {})
    n_chunks = None
    try:
        from . import amstrax_io
        from .live import live_root
        d = live_root(Path(amstrax_io.STORE)) / f"{int(number):06d}"
        if d.is_dir():
            n_chunks = sum(1 for p in d.iterdir() if p.name.isdigit())
    except Exception:
        pass
    return {"chunk length [s]": dc.get("strax_chunk_length"), "chunk overlap [s]": dc.get("strax_chunk_overlap"),
            "chunks written": n_chunks, "payload per record [bytes]": dc.get("strax_fragment_payload_bytes"),
            "compressor": dc.get("compressor"), "reader threads": dc.get("processing_threads"),
            "source rate [Hz] (decays on the timeline)": (rec or {}).get("physics", {}).get("source_rate_hz"),
            "live data folder": dc.get("strax_output_path"), "run start / end": f"{doc.get('start')} / {doc.get('end')}"}


def fig_spe(rec):
    """The single-PE pulse shape per channel as the waveform step used it, with gain, noise and threshold."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = rec["settings"]["xams_daq"]
    dt = float(d["digitizer"]["dt_ns"])
    chans = sorted(d["templates"], key=int)
    fig, axs = plt.subplots(1, len(chans), figsize=(2.6 * len(chans), 2.9), facecolor="#111b2e", sharey=False)
    for ax, ch in zip(np.atleast_1d(axs), chans):
        _style(ax)
        t = np.asarray(d["templates"][ch], float)
        c = d["channels"][ch]
        amp = t * float(c["gain"])                                 # ADC per sample of one PE
        x = (np.arange(len(t)) - 10) * dt
        ax.step(x, amp, where="mid", color="#4db6ff", lw=1.3)
        ax.axhline(float(c["threshold"]), color="#ff6b6b", lw=0.8, ls=":")
        ax.axhspan(-float(c["noise"]), float(c["noise"]), color="#8a96a8", alpha=0.25, lw=0)
        ax.set(title=f"ch{ch} ({c['light']})", xlabel="time from max [ns]", xlim=(-40, 120))
        ax.text(0.97, 0.95, f"gain {c['gain']:g}\nnoise {c['noise']:g} ADC\nthreshold {c['threshold']:g}",
                transform=ax.transAxes, ha="right", va="top", fontsize=7, color="#dce7ff")
    np.atleast_1d(axs)[0].set_ylabel("one PE [ADC per 4 ns sample]")
    fig.suptitle(f"{rec['run_id']}: single-PE response per channel (red dotted: trigger threshold, grey: noise rms)",
                 color="#dce7ff", fontsize=9)
    fig.tight_layout()
    return fig


FIGURES["spe"] = ("Single-PE responses", fig_spe)
FIGURE_ROWS = FIGURE_ROWS + (("spe",),)


# ------------------------------------------------------------------------------------------------ reconstruction
# What amstrax made of a run with a number (plan S11): the stored data types in the raw-records store and the
# processed folder, read from their strax metadata (no amstrax, no database), the corrections the run document holds,
# and a fixed set of figures from event_info (made once per event_info version, next to the provenance).

def processed_dir() -> Path:
    import os
    return Path(os.environ["XAMSSIM_PROCESSED"]) if os.environ.get("XAMSSIM_PROCESSED") else DATA.parent / "processed"


def _stored(number) -> list:
    from . import amstrax_io
    rid = f"{int(number):06d}"
    out = []
    for folder in [Path(amstrax_io.STORE) if amstrax_io.STORE is not None else None, processed_dir()]:
        if folder is None or not folder.is_dir():
            continue
        for d in sorted(folder.glob(f"{rid}-*")):
            if not d.is_dir() or d.name.endswith("_temp"):
                continue
            _, dtype, h = d.name.split("-", 2)
            md = next(iter(d.glob("*metadata.json")), None)
            meta = json.loads(md.read_text()) if md else {}
            chunks = meta.get("chunks", [])
            cal = None
            for plugin, (name, version, cfg) in (meta.get("lineage") or {}).items():
                for v in (cfg or {}).values():
                    if isinstance(v, str) and "calibration=" in v and "xamssim.corrections" in v:
                        cal = int(v.split("calibration=")[1].split("&")[0])
            out.append(dict(type=dtype, hash=h, folder=str(folder), n_chunks=len(chunks),
                            rows=sum(c.get("n", 0) for c in chunks), size_mb=sum(f.stat().st_size for f in d.iterdir()) / 1e6,
                            made=time.strftime("%Y-%m-%d %H:%M", time.localtime(meta["writing_ended"])) if meta.get("writing_ended") else "",
                            calibration=cal, path=str(d)))
    return out


def reconstruction(number) -> dict | None:
    """The amstrax products of a run (data type, lineage hash, chunks, rows, calibration version) and its corrections."""
    if number is None:
        return None
    prods = _stored(number)
    doc = _run_doc(number) or {}
    corr = (doc.get("xamssim") or {}).get("corrections") or {}
    if not corr and (doc.get("xamssim") or {}).get("truth"):
        corr = {"truth": doc["xamssim"]["truth"]}
    keys = ("elife", "drift_time_gate", "drift_time_cathode", "gain_to_pe_array")
    table = [dict(name=k, truth=(corr.get("truth") or {}).get(k), calibrated=(corr.get("calibrated") or {}).get(k))
             for k in keys]
    cal = corr.get("calibrated") or {}
    ev = [p for p in prods if p["type"] == "event_info"]
    return dict(products=prods, corrections=table, calibration_version=cal.get("version", 0),
                calibration=dict(from_run=cal.get("from_run"), method=cal.get("method"), date=cal.get("date")) if cal else None,
                event_info=ev, n_decays=doc.get("xamssim", {}).get("n_events"))


def _load(path: str) -> np.ndarray:
    import ast
    import strax
    d = Path(path)
    meta = json.loads(next(iter(d.glob("*metadata.json"))).read_text())
    dtype = np.dtype([tuple(x) if not isinstance(x[0], list) else (tuple(x[0]), *x[1:]) for x in ast.literal_eval(meta["dtype"])])
    parts = [strax.load_file(str(d / c["filename"]), compressor=meta["compressor"], dtype=dtype)
             for c in meta["chunks"] if c.get("n", 0) > 0]
    return np.concatenate(parts) if parts else np.zeros(0, dtype)


def fig_reconstruction(number, ev_path: str, run_id: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from . import amstrax_io
    ev = _load(ev_path)
    ok = np.isfinite(ev["cs1"]) & np.isfinite(ev["cs2"]) & (ev["cs1"] > 0) & (ev["cs2"] > 0)
    fig, axs = plt.subplots(2, 3, figsize=(16, 9), facecolor="#111b2e")
    for a in axs.flat:
        _style(a)
    kw = dict(norm=LogNorm(), cmap="viridis")
    a = axs[0, 0]
    a.hist2d(ev["cs1"][ok], ev["cs2"][ok], bins=[np.linspace(0, np.nanpercentile(ev["cs1"][ok], 99.5), 120),
                                                  np.linspace(0, np.nanpercentile(ev["cs2"][ok], 99.5), 120)], **kw)
    a.set(xlabel="cS1 [PE]", ylabel="cS2 [PE]", title=f"cS1 vs cS2 ({ok.sum()} events with S1 and S2)")
    a = axs[0, 1]
    a.hist(ev["drift_time"][ok] / 1e3, bins=np.arange(0, 60, 0.25), histtype="step", color="#4db6ff")
    a.set(xlabel="drift time [µs]", ylabel="events", title="drift time")
    a = axs[0, 2]
    a.hist2d(ev["s2_x"][ok & np.isfinite(ev["s2_x"])], ev["s2_y"][ok & np.isfinite(ev["s2_y"])],
             bins=[np.linspace(-35, 35, 141)] * 2, **kw)
    a.set(xlabel="x [mm]", ylabel="y [mm]", title="position of the main S2", aspect="equal")
    a = axs[1, 0]
    a.hist(np.log10(ev["s1_area"][ok]), bins=120, histtype="step", color="#4db6ff")
    a.set(xlabel="log10 S1 area [PE]", ylabel="events", title="S1 spectrum")
    a = axs[1, 1]
    a.hist(np.log10(ev["s2_area"][ok]), bins=120, histtype="step", color="#4db6ff")
    a.set(xlabel="log10 S2 area [PE]", ylabel="events", title="S2 spectrum")
    a = axs[1, 2]                                          # against the simulation's own values (truth file)
    tf = Path(amstrax_io.STORE) / f"{int(number):06d}-truth.npz" if amstrax_io.STORE is not None else None
    if tf is not None and tf.exists():
        t = amstrax_io.load_truth(tf)
        t = t[np.argsort(t["time"])]
        i = np.clip(np.searchsorted(t["time"], ev["time"]), 1, len(t) - 1)
        j = np.where(np.abs(t["time"][i - 1] - ev["time"]) < np.abs(t["time"][i] - ev["time"]), i - 1, i)
        m = ok & (np.abs(t["time"][j] - ev["time"]) < 200_000) & (t["cs2"][j] > 0)
        a.hist2d(ev["drift_time"][m] / 1e3, ev["cs2"][m] / t["cs2"][j][m], bins=[np.arange(0, 60, 0.5), np.linspace(0, 2, 81)], **kw)
        a.axhline(1, color="#ff6b6b", lw=0.8)
        a.set(xlabel="drift time [µs]", ylabel="cS2 amstrax / simulation", title=f"cS2 against the simulation ({m.sum()} matched)")
    else:
        a.text(0.5, 0.5, "no truth file", transform=a.transAxes, ha="center", color="#8a96a8")
    fig.suptitle(f"{run_id} = run {int(number):06d}: amstrax event_info ({Path(ev_path).name.split('-')[-1]})",
                 color="#dce7ff", fontsize=10)
    fig.tight_layout()
    return fig


def reconstruction_figure(run_id: str, number, ev_hash: str) -> Path:
    """PNG of the reconstruction figures for one event_info version, made once next to the run's provenance."""
    ev = next((p for p in _stored(number) if p["type"] == "event_info" and p["hash"] == ev_hash), None)
    if ev is None:
        raise FileNotFoundError(f"no event_info {ev_hash} for run {number}")
    recs = records(run_id)
    base = recs[-1][0].parent if recs else DATA / "provenance" / run_id
    out = base / "figures" / f"reconstruction_v{FIGURE_VERSION}_{ev_hash}.png"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        fig = fig_reconstruction(number, ev["path"], run_id)
        fig.savefig(out, dpi=100, facecolor=fig.get_facecolor(), bbox_inches="tight")
        import matplotlib.pyplot as plt
        plt.close(fig)
    return out


# ------------------------------------------------------------------------------------------------ rerun
# A run number is one fixed simulation (plan S10): a rerun of a run file (new code, maps, ...) is a new run file with
# the next free number and `supersedes: <old number>`, submitted with stbc/submit_production.sh under the account the
# app runs as (private app: private run; production app: production run). The old run stays until it is deleted.
# Submitting from the app needs XAMSSIM_WEB_SUBMIT=1 (set by web/start_stbc.sh on STBC); otherwise the app only shows
# what it would do.
PRIVATE_NUMBERS = (990000, 999999)
PRODUCTION_NUMBERS = (900000, 989999)
SUBMIT = Path(__file__).resolve().parents[1] / "stbc" / "submit_production.sh"


def outdated_reasons(rec: dict) -> list:
    """Why a simulation is outdated: what differs between its newest provenance record and the run file, state,
    source and maps as they are now; [] if nothing found (then only the code can differ)."""
    from .config import resolve
    out = []
    try:
        res = resolve(rec["run_file"])
    except Exception as e:
        return [f"run file cannot be read now: {e}"]
    if res.run != rec.get("run"):
        out.append("run file changed since")
    if res.state != rec.get("state"):
        out.append(f"state {res.state_name} changed")
    if res.source != rec.get("source"):
        out.append(f"source {res.source_name} changed")
    old = {k: v.get("key") for k, v in (rec.get("maps") or {}).items()}
    new = res.map_keys()
    changed = sorted(k for k in new if old.get(k) not in (None, new[k]))
    if changed:
        out.append("maps changed: " + ", ".join(changed))
    if (rec.get("geometry") or {}) != res.geometry:
        out.append("geometry changed")
    return out


def _numbers_in_use() -> set:
    """Run numbers in run files under the studies folder and in the raw-records store."""
    import re
    from . import amstrax_io
    used = set()
    for f in Path(STUDIES).glob("**/runs/*.yaml"):
        m = re.search(r"^run_number:\s*(\d+)", f.read_text(), re.M)
        if m:
            used.add(int(m.group(1)))
    if amstrax_io.STORE is not None and Path(amstrax_io.STORE).is_dir():
        used |= {int(p.name[:6]) for p in Path(amstrax_io.STORE).glob("[0-9]" * 6 + "-metadata.json")}
    return used


def rerun_plan(run_id: str) -> dict:
    """What a rerun of a simulation would do: reasons, new number, new run file and its text."""
    import re
    recs = records(run_id)
    if not recs:
        raise FileNotFoundError(f"no provenance for {run_id}")
    rec = recs[-1][1]
    old = (rec.get("run") or {}).get("run_number")
    if old is None:
        raise ValueError("only runs with a run number can be rerun from the app")
    lo, hi = PRIVATE_NUMBERS if PRIVATE_NUMBERS[0] <= old <= PRIVATE_NUMBERS[1] else PRODUCTION_NUMBERS
    used = _numbers_in_use()
    new = max([n for n in used if lo <= n <= hi] + [old]) + 1
    if new > hi:
        raise ValueError(f"no free run number in {lo}-{hi}")
    src = Path(rec["run_file"])
    stem = re.sub(r"_r\d+$", "", src.stem)
    k = 2
    while (src.parent / f"{stem}_r{k}.yaml").exists():
        k += 1
    dst = src.parent / f"{stem}_r{k}.yaml"
    text = src.read_text() if src.exists() else ""
    if not text:
        raise FileNotFoundError(f"run file {src} not found")
    text = re.sub(r"^run_number:.*$", f"run_number: {new}", text, count=1, flags=re.M)
    text = re.sub(r"^supersedes:.*\n", "", text, flags=re.M)
    text = text.replace(f"run_number: {new}", f"run_number: {new}\nsupersedes: {old}", 1)
    head = f"# Rerun of {src.name} (run {old}) with the code and maps of {time.strftime('%Y-%m-%d')}; same settings and seed.\n"
    return dict(run_id=run_id, old=old, new=new, src=str(src), dst=str(dst), text=head + text,
                reasons=outdated_reasons(rec), private=lo == PRIVATE_NUMBERS[0])


def rerun(run_id: str) -> dict:
    """Write the new run file and submit it (needs XAMSSIM_WEB_SUBMIT=1 and at most 10 own jobs in condor)."""
    import os
    import subprocess
    plan = rerun_plan(run_id)
    if os.environ.get("XAMSSIM_WEB_SUBMIT") != "1":
        raise PermissionError("submitting is off here (XAMSSIM_WEB_SUBMIT is not 1); run by hand: "
                              f"{SUBMIT} {plan['dst']}")
    q = subprocess.run(["condor_q", "-af", "ClusterId"], capture_output=True, text=True, timeout=60)
    n_jobs = len([x for x in q.stdout.split() if x.strip()])
    if n_jobs >= 10:
        raise PermissionError(f"{n_jobs} jobs of this account in condor already (at most 10)")
    dst = Path(plan["dst"])
    if dst.exists():
        raise FileExistsError(dst)
    dst.write_text(plan["text"])
    r = subprocess.run([str(SUBMIT), str(dst)], capture_output=True, text=True, timeout=300, cwd=str(dst.parent.parent))
    _CACHE.clear()
    return dict(plan, returncode=r.returncode, output=(r.stdout + r.stderr)[-3000:])
