#!/usr/bin/env python3
"""Design study: extra PTFE cylinders (scans design_ptfe_s2 / _s1). Light collection top / bottom, top fraction and
where the light ends, per configuration.   python tools/design_ptfe.py  ->  results/design_ptfe/README.md, summary.json"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from scan_data import load, top_fraction  # noqa: E402
from step6_results import category  # noqa: E402

OUT = ROOT / "results" / "design_ptfe"
TOP = (1, 2, 3, 4)
SHORT = {"gate_anode": "gate–anode", "anode_topscreen": "anode–top screen", "cathode_bottomscreen": "cathode–bottom screen"}


def label(p):
    x = p["params"]["extra_ptfe"]
    return "none (as built)" if not x else " + ".join(SHORT[e["name"]] for e in x)


def row(p):
    rec, n = p["rec"], p["n_photons"]
    t = np.isin(rec["sensor"], TOP).sum() / n
    b = (rec["sensor"] == 0).sum() / n
    si = np.isin(rec["sensor"], (6, 7)).sum() / n
    loss = defaultdict(float)
    for (code, vol), k in p["tally"].items():
        c = category(code, vol)
        if c.startswith("mesh bars"):
            c = "mesh bars"
        loss[c] += k / n
    return dict(config=label(p), top=t, bottom=b, sipm=si, total=t + b, top_fraction=top_fraction(rec)[0],
                rings=loss["mesh rings"], leaves=loss["leaves the TPC region"], ptfe=loss["PTFE"],
                bars=loss["mesh bars"], pmt_frame=loss["PMT frame / body"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    lines = ["# Design study: extra PTFE cylinders (2026-10-05)", "",
             "Simulation (model v1, level 4 mm, middle optics: PTFE R 0.945 in liquid / 0.75 in gas, steel R 0.35, QE 0.33).",
             "Extra cylinders: same radii as the drift-region PTFE (r 30.97–35.97 mm), between the mesh rings: gate–anode",
             "z 0.9–7.1 mm (split at the liquid surface, gas part with the gas reflectivity), anode–top screen 8.9–17.1 mm,",
             "cathode–bottom screen −58.7 to −52.7 mm. Scans `scans/design_ptfe_s2.yaml`, `_s1.yaml` (8·10⁶ photons each).",
             "Light collection = detected / emitted, QE included.", ""]
    for src in ("s2", "s1"):
        s = load(f"design_ptfe_{src}")
        rows = [row(p) for p in s["points"]]
        base = rows[0]
        res[src] = rows
        lines += [f"## {'S2 (gas gap)' if src == 's2' else 'S1 (drift region)'}", "",
                  "| extra PTFE | top | bottom | total | gain vs now | top fraction | rings | leaves | PTFE absorbed |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['config']} | {100 * r['top']:.2f} % | {100 * r['bottom']:.2f} % | {100 * r['total']:.2f} % | "
                         f"{100 * (r['total'] / base['total'] - 1):+.0f} % | {r['top_fraction']:.3f} | {100 * r['rings']:.1f} % | "
                         f"{100 * r['leaves']:.1f} % | {100 * r['ptfe']:.1f} % |")
        lines.append("")
    json.dump(res, open(OUT / "summary.json", "w"), indent=1, default=float)
    (OUT / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
