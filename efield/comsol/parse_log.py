#!/usr/bin/env python3
"""Parse the COMSOL batch log of XAMS_efield (CHECK and MAP lines) into
<data>/efield/comsol/checks.json (point checks per case + derived numbers) and maps_rz.npz (the (r, z) plane through
the first SiPM: r > 0 towards the SiPM, r < 0 the opposite side; V, E_r, E_z per case on a regular grid).

    python efield/comsol/parse_log.py efield/comsol/build/run.log
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
from xamssim.config import DATA  # noqa: E402  (outputs: ../simulations/data)
OUT = DATA / "efield" / "comsol"


def main():
    log = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "efield" / "comsol" / "build" / "run.log")
    cases = yaml.safe_load(open(ROOT / "efield" / "cases.yaml"))["cases"]
    checks, misc = defaultdict(dict), {}
    maps = defaultdict(list)
    for line in open(log):
        if line.startswith("CHECK case="):
            kv = dict(t.split("=", 1) for t in line.split()[1:])
            checks[kv["case"]][kv["point"]] = {k: float(v) for k, v in kv.items() if k not in ("case", "point")}
        elif line.startswith("CHECK "):
            k, v = line[6:].strip().split("=", 1)
            misc[k] = v
        elif line.startswith("MAP "):
            t = line.split()
            maps[t[1]].append([float(x) for x in t[2:]])
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"misc": misc, "cases": {}}
    L = 51.8
    for n, pts in checks.items():
        c = cases[n]
        e_nom = (c["G"] - c["C"]) / (L / 10)                 # V/cm, nominal drift field
        d = {"note": c.get("note", ""), "drift_field_nominal_V_cm": round(e_nom, 2)}
        for p, v in pts.items():
            d[p] = {"V": round(v["V"], 2), "E_V_cm": round(v["normE"] / 100, 2), "Ez_V_cm": round(v["Ez"] / 100, 2)}
        if "centre" in pts:
            d["centre_over_nominal"] = round(-pts["centre"]["Ez"] / 100 / e_nom, 4) if e_nom else None
        if "liq_gap" in pts and pts["liq_gap"]["Ez"]:
            d["gas_over_liquid_gap"] = round(pts["gas_gap"]["Ez"] / pts["liq_gap"]["Ez"], 4)
        res["cases"][n] = d
    if not res["cases"]:
        # failed solve (licence, model error): keep the results of the last good run
        raise SystemExit("no CHECK lines in the log (solve failed?); <data>/efield/comsol/ left unchanged")
    json.dump(res, open(OUT / "checks.json", "w"), indent=1)
    if maps:
        out = {}
        for n, rows in maps.items():
            a = np.array(rows)
            r, z = np.unique(a[:, 0].round(3)), np.unique(a[:, 1].round(3))
            shape = (len(r), len(z))
            out["r"], out["z"] = r, z
            for k, name in enumerate(("V", "Er", "Ez"), start=2):
                out[f"{n}_{name}"] = a[:, k].reshape(shape)
        np.savez_compressed(OUT / "maps_rz.npz", **out)
    print(f"cases: {', '.join(res['cases'])}; misc: {misc}")
    for n, d in res["cases"].items():
        print(f"  {n:6s} E_nom {d['drift_field_nominal_V_cm']:7.1f} V/cm  centre/nom {d.get('centre_over_nominal')}  "
              f"gas/liq {d.get('gas_over_liquid_gap')}  V(wall, SiPM height) {d.get('wall_sipm_height', {}).get('V')}")
    print("written", OUT / "checks.json", "and maps_rz.npz" if maps else "(no maps)")


if __name__ == "__main__":
    main()
