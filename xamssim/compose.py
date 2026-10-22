"""What the simulation app shows and (later) composes (plan S10).

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
                         how_far=_how_far({p["type"] for p in prods if p["state"] != "old"}), status=status,
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
    """Side cross-section (x-z through the axis): meshes with their voltages, PTFE cylinder, field-shaping rings, PMTs,
    SiPMs (at their height, projected), liquid level, source."""
    from matplotlib.patches import Rectangle
    g, hv = rec["geometry"], rec["hv_case"]
    mc = g["mesh_common"]
    r_ring_in, r_ring_out = mc["ring"]["inner_diameter_mm"] / 2, mc["ring"]["outer_diameter_mm"] / 2
    z_gate = next(m["z_mm"] for m in g["meshes"] if m["name"] == "gate")
    level = z_gate + rec["state"]["liquid_level_mm"]
    bucket = g.get("ptfe_bucket", {})
    rb = bucket.get("inner_diameter_mm", 112) / 2
    if liquid:
        ax.add_patch(Rectangle((-rb, -75), 2 * rb, level + 75, color="#1d4f7a", alpha=0.35, lw=0, zorder=0))
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
    fig, ax = plt.subplots(figsize=(9, 7.5), facecolor="#111b2e")
    _style(ax)
    _draw_detector(ax, rec)
    xmax = max(75.0, r_src + 15)
    ax.set_xlim(-xmax, xmax + 30)
    ax.set_ylim(min(-80.0, pos[2] - 15), 45)
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


FIGURE_VERSION = 3              # part of the figure file names: raise it when a figure changes, so old ones are remade
FIGURES = {"cross_section": ("TPC cross-section", fig_cross_section),
           "field": ("Field and drift", fig_field)}


def figure(run_id: str, name: str) -> Path:
    """PNG of a configuration figure of the newest provenance record, made once and kept next to it."""
    recs = records(run_id)
    if not recs:
        raise FileNotFoundError(f"no provenance for {run_id}")
    f, rec = recs[-1]
    out = f.parent / "figures" / f"{name}_v{FIGURE_VERSION}_{f.stem}.png"
    if not out.exists():
        out.parent.mkdir(exist_ok=True)
        fig = FIGURES[name][1](rec)
        fig.savefig(out, dpi=110, facecolor=fig.get_facecolor())
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
