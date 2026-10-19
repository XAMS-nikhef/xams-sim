"""Explainer: how xams-sim is built — the configuration that defines the detector, the producers that make maps from it,
the map registry, and the simulation chain (strax / fuse plugins) that turns Geant4 energy deposits into signals.
Plugin names, versions, inputs, outputs, files and line numbers are read from the code (xamssim.chain, inspect); the
configuration tables from config/ and efield/cases.yaml; map status from maps/manifest.json; plan status from
docs/xams_sim_plan.md. The layout and the short descriptions are written here. No simulation results.
Usage (repository root, env xamssim): python notes/make_overview_note.py [out.pdf]
    (default notes/XAMS_simulation_overview.pdf; figures in notes/figures/)"""
import inspect
import re
import subprocess
import sys
import warnings
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from xamssim import chain, config, maps  # noqa: E402
from xamssim.config import load_yaml  # noqa: E402

FD = "/System/Library/Fonts/Supplemental/"
pdfmetrics.registerFont(TTFont("Arial", FD + "Arial.ttf")); pdfmetrics.registerFont(TTFont("Arial-Bold", FD + "Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", FD + "Arial Italic.ttf"))
registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-Bold")
NAVY, LIGHT, GREEN, AMBER, GRID = (colors.HexColor(c) for c in ("#1F3A5F", "#E8EEF5", "#E3F2E1", "#FFF4D6", "#9AA8B8"))
ss = getSampleStyleSheet()
base = ParagraphStyle("b", parent=ss["Normal"], fontName="Arial", fontSize=9.3, leading=12.3)
small = ParagraphStyle("s", parent=base, fontSize=7.6, leading=9.6)
cap = ParagraphStyle("c", parent=small, textColor=colors.HexColor("#4A5A6A"), spaceAfter=6)
h1 = ParagraphStyle("h1", parent=base, fontName="Arial-Bold", fontSize=17, leading=21, textColor=NAVY)
sub = ParagraphStyle("sub", parent=base, fontSize=9.5, textColor=colors.HexColor("#4A5A6A"), spaceAfter=5)
h2 = ParagraphStyle("h2", parent=base, fontName="Arial-Bold", fontSize=11.5, leading=14.5, textColor=NAVY, spaceBefore=8, spaceAfter=3)
hdr = ParagraphStyle("hdr", parent=small, fontName="Arial-Bold", textColor=colors.white)
W = A4[0] - 30 * mm
FIG = ROOT / "notes" / "figures"
EXAMPLE_RUN = ROOT / "config" / "runs" / "cs137_cmb50_001.yaml"

# what each chain plugin does (written here; a plugin without an entry stops the script)
WHAT = {
    "XamsG4Input": "reads <data>/g4/&lt;run&gt;/deposits.* (binary + JSON header): mm → cm, codes → particle / process names, "
                   "RadioactiveDecay → RadioactiveDecayBase; places events on a timeline at source_rate; dynamic chunks",
    "LineageClustering": "groups the deposits of an event by particle lineage (a gamma's scatters are separate clusters, an "
                         "electron track one cluster); gives each lineage its NEST interaction type",
    "MergeLineage": "one row per cluster: energy-weighted position, summed energy, time",
    "FindCluster": "DBSCAN clustering in space and time (option clustering: dbscan)",
    "MergeCluster": "one row per DBSCAN cluster",
    "XamsVolumeProperties": "volume of each cluster from the drift map (1 drift region, 2 below cathode, 3 gas, 4 liquid "
                            "above the gate) and its xenon density",
    "XamsVolumeSelection": "keeps clusters in the four volumes (fuse itself keeps only 1 and 2)",
    "DefaultSimulation": "applies the selection: interactions_in_roi",
    "XamsElectricField": "|E| at the cluster position (x, y, z) from the state's 3D field map",
    "NestYields": "NEST photons / electrons / excitons with the local field and the volume's density",
    "MicroPhysicsSummary": "all of the above in one table per cluster",
    "XamsExtractionEL": "extraction (NEST efficiency) and EL in the gas per cluster from the state's extraction / EL "
                        "map at its gate-hole position: extracted electrons, S2 photons, S2 time and width",
    "XamsS1Light": "S1 photoelectrons per channel per cluster: NEST photons spread over the channels with the "
                   "state's S1 light map at (x, y, z)",
    "XamsS2Light": "S2 photoelectrons per channel per cluster: S2 photons spread over the channels with the state's S2 "
                   "pattern map at the gate crossing",
    "XamsElectronDrift": "electrons at the liquid surface per cluster from the state's drift map (end point: surface, "
                         "bottom, wall, SiPM; survival exp(−t/τ)), drift time and diffusion spread, position at the gate",
}
# configuration files: what they define (written here); keys and users are read below
CONFIG = [
    ("config/geometry.yaml", "the detector: every dimension, position and angle, in the data frame; version", "Geant4, COMSOL, chain"),
    ("config/materials.yaml", "material properties at the reference conditions (2 bar, 175 K) and the optical parameters",
     "Geant4, COMSOL (permittivities), chain (densities)"),
    ("config/states/*.yaml", "a detector condition: HV case, liquid level, pressure, lifetime", "all (via the run)"),
    ("config/sources/*.yaml", "a source: isotope or gamma, position, direction", "Geant4 particle mode"),
    ("config/runs/*.yaml", "one simulation: state + source + events + seed + last product + physics options", "xamssim"),
    ("efield/cases.yaml", "voltages of the electrodes per HV case (no geometry, no level)", "COMSOL, map keys"),
    ("config/scans/*.yaml", "optical scans: grids of optical parameters and liquid levels", "xamssim optical"),
]


# ------------------------------------------------------------------------------------------------ read the code
def git(*a):
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), *a], text=True).strip()
    except Exception:
        return "?"


def g4_version():
    cache = ROOT / "g4" / "build" / "CMakeCache.txt"
    if cache.exists():
        m = re.search(r"Geant4_DIR:PATH=(.*)", cache.read_text())
        if m:
            cfg = Path(m.group(1)).parent.parent.parent / "bin" / "geant4-config"
            try:
                return subprocess.check_output([str(cfg), "--version"], text=True).strip()
            except Exception:
                pass
    return "?"


def plugin_info(cls):
    f = inspect.getsourcefile(cls)
    line = inspect.getsourcelines(cls)[1]
    rel = Path(f).resolve()
    origin = "xams-sim" if ROOT in rel.parents else "fuse"
    if origin == "xams-sim":
        short = str(rel.relative_to(ROOT))
    else:
        short = "fuse/" + str(rel).split("/fuse/", 1)[1]
    provides = cls.provides if isinstance(cls.provides, (tuple, list)) else (cls.provides,)
    dep = cls.depends_on if isinstance(cls.depends_on, (tuple, list)) else ((cls.depends_on,) if cls.depends_on else ())
    return dict(name=cls.__name__, version=getattr(cls, "__version__", "?"), provides=list(provides), depends=list(dep),
                file=short, line=line, origin=origin, options=set(getattr(cls, "takes_config", {}) or {}))


def plan_status():
    out = []
    for line in (ROOT / "docs" / "xams_sim_plan.md").read_text().splitlines():
        m = re.match(r"### (S\d)\. (.*?)(?: — \*\*(.*?)\*\*(.*))?$", line)
        if m:
            out.append((m.group(1), re.sub(r"\s*\(.*?\)$", "", m.group(2)), ((m.group(3) or "open") + (m.group(4) or "")).strip()))
    return out


def cli_lines():
    """(command, what) pairs from the usage block of xamssim/cli.py (separated by 2+ spaces)."""
    doc = (ROOT / "xamssim" / "cli.py").read_text().split('"""')[1]
    out = []
    for ln in doc.splitlines():
        ln = ln.strip()
        if ln.startswith("xamssim "):
            parts = re.split(r"\s{2,}", re.sub(r"^xamssim\s+(\S+)\s+", r"xamssim \1 ", ln), maxsplit=1)
            out.append((parts[0], parts[1] if len(parts) > 1 else ""))
    return out


# ------------------------------------------------------------------------------------------------ figures
def node(ax, x, y, w, h, text, fc, fs=7.2, bold_first=True):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.01,rounding_size=0.015",
                                fc=fc, ec="#5A6A7A", lw=0.8))
    lines = text.split("\n")
    ax.text(x, y + (len(lines) - 1) * 0.011, lines[0], ha="center", va="center", fontsize=fs + 0.6,
            fontweight="bold" if bold_first else "normal", color="#1F3A5F")
    for i, ln in enumerate(lines[1:], 1):
        ax.text(x, y + (len(lines) - 1) * 0.011 - i * 0.024, ln, ha="center", va="center", fontsize=fs, color="#2A3A4A")


def arrow(ax, p, q, style="-|>", ls="-", color="#4A5A6A"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=9, lw=0.9, ls=ls, color=color))


def fig_architecture(kinds, products):
    fig, ax = plt.subplots(figsize=(10.5, 6.6))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    cfgc, prodc, mapc, chc = "#E3F2E1", "#FFF4D6", "#E8EEF5", "#F3E8F5"
    ax.text(0.10, 0.97, "definition (config/)", ha="center", fontsize=9, fontweight="bold", color="#1F3A5F")
    ax.text(0.40, 0.97, "producers (standalone)", ha="center", fontsize=9, fontweight="bold", color="#1F3A5F")
    ax.text(0.66, 0.97, "map registry (maps/)", ha="center", fontsize=9, fontweight="bold", color="#1F3A5F")
    ax.text(0.89, 0.97, "chain (strax context)", ha="center", fontsize=9, fontweight="bold", color="#1F3A5F")
    ys = [0.86, 0.75, 0.64, 0.53, 0.42, 0.31]
    for (t, y) in zip(["geometry.yaml\nthe detector, data frame", "materials.yaml\nproperties + optics",
                       "states/\nHV case, level, pressure", "efield/cases.yaml\nvoltages per HV case",
                       "sources/\nisotope, position", "runs/\nstate + source + events"], ys):
        node(ax, 0.10, y, 0.17, 0.085, t, cfgc)
    prods = [("xamsg4 -m particle\nGeant4: energy deposits", 0.80), ("xamsg4 (optical)\nGeant4: photon transport", 0.62),
             ("COMSOL (efield/comsol)\nfull TPC + mesh cells", 0.44)]
    for t, y in prods:
        node(ax, 0.40, y, 0.21, 0.09, t, prodc)
    # map kinds from the registry
    ky = {"s1_light": 0.80, "s2_pattern": 0.71, "field": 0.60, "mesh_cells": 0.50, "drift": 0.40, "extraction_el": 0.30}
    for k, v in kinds.items():
        node(ax, 0.66, ky.get(k, 0.2), 0.17, 0.07, f"{k}\nneeded for {v['needed_for']}", mapc, fs=6.6)
    arrow(ax, (0.505, 0.62), (0.575, 0.80)); arrow(ax, (0.505, 0.62), (0.575, 0.71))
    for y in (0.60, 0.50, 0.30):
        arrow(ax, (0.505, 0.44), (0.575, y))
    arrow(ax, (0.66, 0.565), (0.66, 0.435), color="#4A5A6A"); arrow(ax, (0.66, 0.465), (0.66, 0.435), color="#4A5A6A")
    for y in ys[:4]:
        arrow(ax, (0.185, y), (0.295, 0.62 if y in (0.86, 0.75) else 0.44), color="#8A9AAA")
    arrow(ax, (0.185, 0.86), (0.295, 0.80), color="#8A9AAA"); arrow(ax, (0.185, 0.42), (0.295, 0.80), color="#8A9AAA")
    # chain products
    py = [0.88 - i * 0.105 for i in range(len(products))]
    for i, (p, y) in enumerate(zip(products, py)):
        done = p in chain.TARGETS
        node(ax, 0.89, y, 0.17, 0.065, p + ("" if done else "\n(planned)"), chc if done else "#F5F5F5", fs=6.6)
        if i:
            arrow(ax, (0.89, py[i - 1] - 0.033), (0.89, y + 0.033))
    arrow(ax, (0.505, 0.80), (0.805, py[0]), ls="--")
    for k, y in ky.items():
        tgt = products.index(kinds[k]["needed_for"]) if kinds[k]["needed_for"] in products else None
        if tgt is not None:
            arrow(ax, (0.745, y), (0.805, py[tgt]), color="#7A5A9A")
    arrow(ax, (0.185, 0.31), (0.805, 0.93), ls=":", color="#8A9AAA")
    ax.text(0.5, 0.06, "Green: the definition (the only place a number is written). Amber: programs that make data from "
            "it. Blue: maps, keyed by a hash of exactly their inputs.\nPurple: chain products (grey: planned). Dashed: "
            "Geant4 deposits enter the chain; dotted: the run file selects state and source.",
            ha="center", fontsize=7.4, color="#4A5A6A")
    fig.savefig(FIG / "architecture.png", dpi=170, bbox_inches="tight"); plt.close(fig)


def fig_chain(pl):
    fig, ax = plt.subplots(figsize=(8.2, 0.85 * len(pl) + 0.6))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    n = len(pl)
    ys = [1 - (i + 0.5) / n for i in range(n)]
    for i, (p, y) in enumerate(zip(pl, ys)):
        fc = "#F3E8F5" if p["origin"] == "xams-sim" else "#E8EEF5"
        node(ax, 0.5, y, 0.86, 0.72 / n,
             f"{p['name']}  v{p['version']}  ({p['origin']})\nprovides: {', '.join(p['provides'])}    "
             f"← {', '.join(p['depends']) or 'Geant4 files'}\n{p['file']}:{p['line']}", fc, fs=6.8)
        if i:
            arrow(ax, (0.5, ys[i - 1] - 0.36 / n), (0.5, y + 0.36 / n))
    fig.savefig(FIG / "chain.png", dpi=170, bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------------------------------------ PDF helpers
def P(t, st=base):
    return Paragraph(t, st)


def box(flow, bg):
    t = Table([[flow]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("BOX", (0, 0), (-1, -1), 0.6, GRID),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def table(data, widths):
    d = [[Paragraph(str(c), hdr if i == 0 else small) for c in r] for i, r in enumerate(data)]
    t = Table(d, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, GRID), ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")] +
                          [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(data), 2)]))
    return t


def img(name, caption, width=W):
    from reportlab.lib.utils import ImageReader
    p = FIG / name
    iw, ih = ImageReader(str(p)).getSize()
    return KeepTogether([Image(str(p), width=width, height=width * ih / iw), P(caption, cap)])


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(v):
    if isinstance(v, float):
        return f"{v:.6g}"
    s = repr(v) if not isinstance(v, str) else v
    if isinstance(v, str) and "/maps/field/" in v:
        return "maps/field/&lt;key&gt;/efield_xyz.npz"
    if isinstance(v, str) and "/maps/drift/" in v:
        return "maps/drift/&lt;key&gt;/drift_xyz.npz"
    if isinstance(v, str) and v.startswith(str(config.DATA)):
        s = "&lt;data&gt;" + v[len(str(config.DATA)):]
        return s if len(s) <= 46 else s[:44] + "…"
    if isinstance(v, str) and v.startswith(str(ROOT)):
        s = v[len(str(ROOT)) + 1:]
    return esc(s if len(s) <= 34 else s[:32] + "…")


# ------------------------------------------------------------------------------------------------ main
def main():
    FIG.mkdir(parents=True, exist_ok=True)
    out = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "notes" / "XAMS_simulation_overview.pdf")
    commit, dirty = git("rev-parse", "--short", "HEAD"), git("status", "--porcelain")
    gitinfo = commit + (" + local changes" if dirty else "")
    geo = load_yaml(ROOT / "config" / "geometry.yaml")
    res = config.resolve(EXAMPLE_RUN)
    pl = [plugin_info(c) for c in chain.plugins("lineage")]
    alt = [plugin_info(c) for c in chain.plugins("dbscan") if c not in chain.plugins("lineage")]
    missing = [p["name"] for p in pl + alt if p["name"] not in WHAT]
    if missing:
        raise SystemExit(f"no description for plugins {missing}: add them to WHAT")
    gdir = chain.g4_dir(res)
    settings = chain.settings(res, gdir, xams_efield_map=str(ROOT / "maps" / "field" / "KEY" / "efield_xyz.npz"),
                              xams_drift_map=str(ROOT / "maps" / "drift" / "KEY" / "drift_xyz.npz"),
                              g4_output_hash="(content hash of the Geant4 output)")
    fig_architecture(maps.KINDS, list(config.PRODUCTS)); fig_chain(pl)

    # tables read from the configuration
    states = []
    for f in sorted((ROOT / "config" / "states").glob("*.yaml")):
        s = load_yaml(f)
        r = config.resolve_state(f.stem)
        hv = r.hv_case
        st = {row["kind"]: row["present"] for row in maps.status(r)}
        present = ", ".join(k for k in ("field", "mesh_cells", "drift") if st.get(k)) or "–"
        states.append([f"<b>{f.stem}</b>", esc(s.get("description", "")), s["hv_case"],
                       f"A {hv['A']:+g}, G {hv['G']:+g}, C {hv['C']:+g}, SiPM {hv['SIPM']:+g}",
                       f"{s['liquid_level_mm']}", present])
    sources = []
    for f in sorted((ROOT / "config" / "sources").glob("*.yaml")):
        s = load_yaml(f)
        sources.append([f"<b>{f.stem}</b>", esc(s.get("isotope") or s.get("type", "")), esc(s.get("position_mm")),
                        esc(s.get("description", ""))])
    runs = []
    for f in sorted((ROOT / "config" / "runs").glob("*.yaml")):
        s = load_yaml(f)
        runs.append([f"<b>{f.stem}</b>", s["state"], s["source"], f"{s['n_events']:.0e}", s.get("stop_after", "raw_records"),
                     esc(s.get("physics", {}))])
    cfg_rows = [["file", "defines", "read by", "top-level keys"]]
    for f, what, users in CONFIG:
        p = ROOT / f.split("*")[0].rstrip("/")
        if p.is_file():
            keys = ", ".join(k for k in load_yaml(p).keys())
        else:
            keys = f"{len(list(p.glob('*.yaml')))} files" if p.is_dir() else "–"
        cfg_rows.append([f"<b>{esc(f)}</b>", esc(what), esc(users), esc(keys)])
    plug_rows = [["#", "output", "plugin · origin · file:line", "inputs", "settings from the configuration", "what it does"]]
    for i, p in enumerate(pl, 1):
        mine = sorted(k for k in settings if k in p["options"])
        plug_rows.append([str(i), f"<b>{esc(', '.join(p['provides']))}</b>",
                          f"<b>{p['name']}</b> v{esc(p['version'])}<br/>{p['origin']}<br/>{esc(p['file'])}:{p['line']}",
                          esc(", ".join(p["depends"])) or "(Geant4 files)",
                          "<br/>".join(f"{k} = {fmt(settings[k])}" for k in mine) or "–", WHAT[p["name"]]])
    alt_rows = [["plugin", "file:line", "what it does"]] + [[f"<b>{p['name']}</b> v{esc(p['version'])}",
                                                             f"{esc(p['file'])}:{p['line']}", WHAT[p["name"]]] for p in alt]
    map_rows = [["kind", "producer", "needed for", "make", "plan step"]]
    for k, v in maps.KINDS.items():
        map_rows.append([f"<b>{k}</b>", esc(v["producer"]), v["needed_for"], f"<font name='Arial'>{esc(v['make'])}</font>",
                         v["export_step"]])
    plan_rows = [["step", "content", "status"]] + [[s, esc(t), esc(st)] for s, t, st in plan_status()]
    phys_rows = [["option", "default"]] + [[k, esc(v)] for k, v in chain.PHYSICS_DEFAULTS.items()]
    fr = geo["meta"]["version"]

    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title="xams-sim: how the XAMS simulation is built", author="XAMS")
    s = [P("xams-sim: how the XAMS simulation is built", h1),
         P(f"Explainer — configuration, producers, map registry and the simulation chain (xams-sim {esc(gitinfo)}; "
           f"geometry v{fr}; Geant4 {esc(g4_version())}, strax {version('strax')}, fuse {version('xenon-fuse')}, "
           f"nestpy {version('nestpy')}; generated from the code)", sub),
         box(P("<b>In one sentence.</b> A handful of YAML files define the detector and the conditions; standalone "
               "programs (Geant4, COMSOL) turn that definition into energy deposits and maps; a strax context with fuse "
               "and XAMS plugins turns the deposits, step by step, into what the detector would see — every step "
               "configured from the same files, every product traceable to them."), GREEN),
         P("1. Principles", h2),
         table([["principle", "what it means here"],
                ["one definition", "every dimension, position and angle is written once, in config/geometry.yaml; material "
                                   "properties once, in config/materials.yaml; voltages in efield/cases.yaml; the liquid "
                                   "level and the HV case of a condition in its state. Geant4, COMSOL and the chain read "
                                   "them; a missing value is an error, never a built-in default."],
                ["one frame", "geometry.yaml is in the data frame of the position reconstruction (z = 0 at the gate, +x towards "
                              "top-PMT sectors I / III, +y towards I / II). No program converts frames."],
                ["one front door", "everything runs from the xamssim env through the xamssim command (section 7); Geant4 runs "
                                   "in its own env, started automatically."],
                ["maps are keyed", "a map's key is a hash of exactly its inputs (geometry, voltages, level, …); states with the "
                                   "same inputs share it, a changed input asks for a new one."],
                ["standalone producers", "Geant4 and COMSOL are separate programs; the chain only reads their products, so "
                                         "each can be run, checked and replaced on its own."],
                ["docs vs notes", "docs/ is the manual (how to run); results/ and notes/ hold the numbers."]],
               [30 * mm, W - 30 * mm]),
         P("2. The pieces", h2),
         img("architecture.png", "Figure 1. From the definition to the signals. Map kinds and chain products are read from "
             "xamssim/maps.py (KINDS) and xamssim/config.py (PRODUCTS)."),
         PageBreak(),
         P("3. The definition: configuration files", h2),
         table(cfg_rows, [36 * mm, 58 * mm, 36 * mm, W - 130 * mm]),
         P("Detector states", h2),
         table([["state", "description", "HV case", "voltages (V)", "level (mm)", "maps present"]] + states,
               [16 * mm, 62 * mm, 15 * mm, 50 * mm, 15 * mm, W - 158 * mm]),
         P("Sources and runs", h2),
         table([["source", "isotope / type", "position (mm)", "description"]] + sources, [30 * mm, 22 * mm, 30 * mm, W - 82 * mm]),
         Spacer(1, 4),
         table([["run", "state", "source", "events", "last product", "physics"]] + runs,
               [32 * mm, 14 * mm, 28 * mm, 14 * mm, 30 * mm, W - 118 * mm]),
         P("4. Producers", h2),
         table([["producer", "code", "makes", "started by"],
                ["Geant4 particle mode", "g4/src/ParticleMode.cc, XamsGeometry.cc",
                 "one 46-byte record per energy deposit in xenon + one per event, JSON header (code tables, units, config)",
                 "xamssim particle &lt;run&gt;"],
                ["Geant4 optical mode", "g4/src/PhotonActions.cc, Output.cc, XamsGeometry.cc",
                 "one record per photon (start, end, sensor); scans over optical parameters and levels",
                 "xamssim optical &lt;scan&gt;"],
                ["light maps", "xamssim/lightmap.py (Geant4 optical mode)",
                 "per channel the detection probability (QE included) of S1 light on a 2 mm (x, y, z) grid and of S2 "
                 "light on a 1 mm (x, y) grid → maps/s1_light, s2_pattern/&lt;key&gt;/",
                 "xamssim maps --state … --export light"],
                ["COMSOL full TPC", "efield/comsol/make_model.py → Java → comsol batch",
                 "3D electrostatic field of all electrodes, field cage, PTFE and SiPMs (meshes as solid discs); .mph",
                 "efield/comsol/run.sh --states …"],
                ["COMSOL mesh cells", "efield/comsol/make_cell.py",
                 "field through one cell of an etched mesh (gate, cathode, gate + anode stack); extraction and EL (S5)",
                 "efield/comsol/run_cell.sh"],
                ["mesh-cell export", "xamssim/cellmap.py (mph)",
                 "gate and cathode quarter-cell fields of the real etched meshes → maps/mesh_cells/&lt;key&gt;/cells.npz",
                 "xamssim maps --state … --export cells"],
                ["extraction / EL map", "xamssim/elmap.py",
                 "per gate-hole position: extraction efficiency, EL photons per electron, transit time and emission "
                 "profile in the gas, tracked through the gate + anode cell",
                 "xamssim maps --state … --export el"],
                ["drift map", "xamssim/driftmap.py",
                 "electron end points, drift times, gate crossings on a 1 × 1 × 0.5 mm grid, tracked through the "
                 "composite field (full TPC + mesh cells)",
                 "xamssim maps --state … --export drift"],
                ["field export", "xamssim/fieldmap.py (mph: COMSOL's API)",
                 "the state's 3D field on a 0.5 mm grid → &lt;data&gt;/maps/field/&lt;key&gt;/efield_xyz.npz",
                 "xamssim maps --state … --export field"]],
               [30 * mm, 44 * mm, 70 * mm, W - 144 * mm]),
         P("5. Map registry", h2),
         P("maps/manifest.json lists every map with its kind, key, state, files, producer version and inputs. The chain "
           "asks the registry for the key of its state; a missing map is an error with the command that makes it."),
         table(map_rows, [22 * mm, 40 * mm, 26 * mm, W - 110 * mm, 22 * mm]),
         P("6. The simulation chain", h2),
         P("A strax context (xamssim/chain.py: context, settings, plugins) with fuse's micro-physics plugins and the XAMS "
           "plugins in xamssim/plugins/. strax computes only what is missing and stores each product under a hash of the "
           f"plugin versions and settings (&lt;data&gt;/strax/; run id = run file name). Settings below are those of {esc(EXAMPLE_RUN.name)}."),
         img("chain.png", "Figure 2. The chain as implemented (lineage clustering). Purple: XAMS plugins, blue: fuse. Read "
             "from the plugin classes.", width=0.82 * W),
         table(plug_rows, [6 * mm, 26 * mm, 40 * mm, 26 * mm, 42 * mm, W - 140 * mm]),
         Spacer(1, 4),
         P("Alternative clustering (physics.clustering: dbscan):", small),
         table(alt_rows, [40 * mm, 60 * mm, W - 100 * mm]),
         Spacer(1, 4),
         KeepTogether([P("Physics options of a run file (xamssim/chain.py PHYSICS_DEFAULTS)", small),
                       table(phys_rows, [60 * mm, 40 * mm])]),
         P("7. Commands", h2),
         table([["command (from xamssim/cli.py)", "does"]] + [[f"<b>{esc(c)}</b>", esc(w)] for c, w in cli_lines()],
               [95 * mm, W - 95 * mm]),
         P("8. Status (docs/xams_sim_plan.md)", h2),
         table(plan_rows, [12 * mm, 90 * mm, W - 102 * mm]),
         KeepTogether([P("9. Things to know", h2),
                       P("• <b>Geant4 runs in its own env</b> (g4); xamssim/g4bin.py starts it with conda run. Compile in "
                         "g4: cmake --build g4/build.", small),
                       P("• <b>COMSOL</b>: the Java model cannot write files with File system access: Limited; maps are read "
                         "from the saved .mph with mph (Python) instead. Needs the licence (UvA server).", small),
                       P("• <b>fuse 1.6.3</b> needs np.in1d (removed in numpy 2.4): xamssim/plugins adds it back.", small),
                       P("• <b>Old outputs</b> in run/ made before geometry v5 are mirrored in x and are not used; all "
                         "productions are made new once the chain is complete.", small),
                       P("• <b>Renewing</b>: python notes/make_overview_note.py after a change — plugin names, versions, "
                         "lines, settings, states, maps and plan status follow; a new plugin stops the script until it "
                         "gets a description.", small)]),
         ]
    doc.build(s)
    print("written", out)


if __name__ == "__main__":
    main()
