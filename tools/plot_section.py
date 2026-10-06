"""Draw a geometry cross section written by /xamsopt/section (Geant4 navigator: volume at each grid point).

    python tools/plot_section.py build/section_xz.bin [-o section_xz.png] [--zoom umin umax vmin vmax]
"""
import argparse
import json
import re

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

# volume name (copy suffix and mesh prefix stripped) -> (colour, legend label)
STYLE = [
    (r"^World$|^outside$", "#ffffff", "world (absorber)"),
    (r"Hole$|^Liquid$", "#cfe3f7", "liquid xenon"),
    (r"^Gas$", "#f4f4f4", "gas xenon"),
    (r"Foil$", "#202020", "mesh foil (steel)"),
    (r"^CopperRing$", "#c8743a", "copper field-shaping rings"),
    (r"Ring$|Rim$", "#7a7f8c", "mesh rings (+ foil rim)"),
    (r"^PTFE$|^PTFE_gas$", "#e8d7a8", "PTFE"),
    (r"Window$", "#8fd3ff", "PMT window (silica)"),
    (r"Sector$|Cathode$", "#ff9a1f", "photocathode"),
    (r"Frame$|Body$", "#5a4a6a", "PMT frame / body (absorber)"),
    (r"^SiPM$", "#1fae4a", "SiPM"),
    (r"^Bucket$", "#d9b86c", "PTFE bucket"),
    (r"^Vessel$", "#4a5568", "cryostat vessel (steel)"),
]


def style_of(name, layer_medium):
    for pat, col, lab in STYLE:
        if re.search(pat, name):
            if name.endswith("Hole"):  # mesh hole = medium of the mother
                return layer_medium[name]
            return col, lab
    return "#ff00ff", name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("-o", "--out")
    ap.add_argument("--zoom", nargs=4, type=float, metavar=("UMIN", "UMAX", "VMIN", "VMAX"))
    ap.add_argument("--title", default="")
    a = ap.parse_args()

    meta = json.load(open(a.file + ".json"))
    nu, nv = meta["nu"], meta["nv"]
    m = np.fromfile(a.file, dtype=np.uint16).reshape(nv, nu)
    names = {int(k): v for k, v in meta["volumes"].items()}
    # mesh layers sit in liquid or gas: gas meshes are above the liquid surface (gate is the topmost liquid mesh)
    layer_medium = {}
    for n in names.values():
        if n.endswith("Hole"):
            gas = n.split("Hole")[0] in ("top_screen", "anode")
            layer_medium[n] = ("#f4f4f4", "gas xenon") if gas else ("#cfe3f7", "liquid xenon")

    cols, labels = [], {}
    for i in range(max(names) + 1):
        col, lab = style_of(names.get(i, "?"), layer_medium)
        cols.append(col)
        labels[lab] = col
    present = {style_of(names[i], layer_medium)[1] for i in np.unique(m)}

    u = (meta["umin"], meta["umax"])
    v = (meta["vmin"], meta["vmax"])
    pl = meta["plane"]
    ext = [u[0], u[1], v[0], v[1]]
    fig, ax = plt.subplots(figsize=(8, 8 * (v[1] - v[0]) / (u[1] - u[0]) if pl != "xy" else 8))
    ax.imshow(m, origin="lower", extent=ext, cmap=ListedColormap(cols), vmin=-0.5, vmax=len(cols) - 0.5,
              interpolation="nearest", aspect="equal")
    ax.set_xlabel({"xz": "x", "yz": "y", "xy": "x"}[pl] + " [mm]")
    ax.set_ylabel({"xz": "z", "yz": "z", "xy": "y"}[pl] + " [mm]")
    off = meta["offset_mm"]
    ax.set_title(a.title or f"XAMS optical geometry, plane {pl} at {'y' if pl == 'xz' else 'x' if pl == 'yz' else 'z'} = {off} mm")
    if a.zoom:
        ax.set_xlim(a.zoom[0], a.zoom[1])
        ax.set_ylim(a.zoom[2], a.zoom[3])
    ax.legend(handles=[Patch(facecolor=c, edgecolor="k", lw=0.3, label=l) for l, c in labels.items() if l in present],
              loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, frameon=False)
    fig.tight_layout()
    out = a.out or a.file.replace(".bin", ".png")
    fig.savefig(out, dpi=200)
    print(out)


if __name__ == "__main__":
    main()
