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
        if c.startswith("mesh foil"):
            c = "mesh foils"
        loss[c] += k / n
    return dict(config=label(p), top=t, bottom=b, sipm=si, total=t + b, top_fraction=top_fraction(rec)[0],
                rings=loss["mesh rings (+ foil rim)"] + loss["copper field-shaping rings"], leaves=loss["leaves the TPC region"], ptfe=loss["PTFE"],
                bars=loss["mesh foils"], pmt_frame=loss["PMT frame / body"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    lines = ["# Design study: extra PTFE cylinders (2026-10-05, geometry v3)", "",
             "Simulation (geometry v3: drawings incl. the 456-hole mesh pattern, level 4 mm, middle optics: PTFE R 0.945 in liquid / 0.75 in gas,",
             "steel R 0.35, copper R 0.3, QE 0.33). Extra cylinders with the radii of the drift-region PTFE (r 31–36 mm,",
             "inside the ring bores): gate–anode z 0.075–7.925 mm (foil to foil, split at the liquid surface, gas part with",
             "the gas reflectivity), anode–top screen 8.075–17.925 mm, cathode–bottom screen −59.525 to −51.875 mm. Scans",
             "`scans/design_ptfe_s2.yaml`, `_s1.yaml` (8·10⁶ photons each). Light collection = detected / emitted, QE",
             "included.", ""]
    for src in ("s2", "s1"):
        s = load(f"design_ptfe_{src}")
        rows = [row(p) for p in s["points"]]
        base = rows[0]
        res[src] = rows
        lines += [f"## {'S2 (gas gap)' if src == 's2' else 'S1 (drift region)'}", "",
                  "| extra PTFE | top | bottom | total | gain vs now | top fraction | rings (steel + copper) | leaves | PTFE absorbed |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['config']} | {100 * r['top']:.2f} % | {100 * r['bottom']:.2f} % | {100 * r['total']:.2f} % | "
                         f"{100 * (r['total'] / base['total'] - 1):+.0f} % | {r['top_fraction']:.3f} | {100 * r['rings']:.1f} % | "
                         f"{100 * r['leaves']:.1f} % | {100 * r['ptfe']:.1f} % |")
        lines.append("")
    s2, s1 = res["s2"], res["s1"]
    g = lambda rows, i: 100 * (rows[i]["total"] / rows[0]["total"] - 1)  # noqa: E731
    lines += ["## Reading", "",
              f"- S2: light collection {g(s2, 1):+.0f} % (gate–anode) / {g(s2, 2):+.0f} % (anode–top screen) alone, "
              f"**{g(s2, 4):+.0f} % with both**, {g(s2, 5):+.0f} % with all three; the light leaving sideways or ending on "
              f"the rings drops from {100 * (s2[0]['rings'] + s2[0]['leaves']):.0f} % to {100 * (s2[5]['rings'] + s2[5]['leaves']):.0f} %. "
              f"The top fraction hardly changes ({min(r['top_fraction'] for r in s2):.2f}–{max(r['top_fraction'] for r in s2):.2f}).",
              f"- S1: {g(s1, 1):+.0f} / {g(s1, 2):+.0f} / {g(s1, 3):+.0f} % alone, {g(s1, 5):+.0f} % with all three; "
              "cathode–bottom screen helps S1 most (bottom PMT).",
              "- In absolute terms: S2 detected light goes from "
              f"{100 * s2[0]['total']:.1f} % to {100 * s2[5]['total']:.1f} % of the emitted photons (factor "
              f"{s2[5]['total'] / s2[0]['total']:.2f}) — most rescued photons still end on meshes, PMT frames or in the photocathode (QE).",
              "- Caveats: everything outside |x|, |y| < 60 mm is black (the real sideways loss may be smaller, and the gain",
              "  with it); PTFE reflectivity in gas (0.75) is free (0.60–0.90); the three gate–anode pillars are not modelled.",
              "  Not looked at: HV (PTFE across 5 kV gate–anode: surface paths, charge-up in the extraction region), mechanics.",
              ""]
    json.dump(res, open(OUT / "summary.json", "w"), indent=1, default=float)
    (OUT / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
