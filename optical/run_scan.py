#!/usr/bin/env python3
"""Run a parameter scan of the XAMS optical simulation (production runs, step 5).

    python optical/run_scan.py scans/<name>.yaml [--jobs N] [--dry]

The scan file:
    name: s2_reference
    source: s2                 # s2 (gas gap) | s1 (drift region); uniform in the volume, r < rmax_mm
    rmax_mm: 30
    photons: 2000000           # per scan point
    chunks: 8                  # independent sub-runs per point (own seed), run in parallel
    seed: 1000
    base:                      # config for every point (make_config.py): liquid level + --set overrides
      level: 4.0
      set: {optics.lxe.rayleigh_length_cm: 45}
    grid:                      # every combination is one scan point; 'level' or any config path
      level: [2.0, 3.0, 4.0]
      optics.ptfe_in_liquid.reflectivity: [0.90, 0.95, 0.99]

Output in run/scans/<name>/: point_<i>.json (config), point_<i>_<k>.bin (records of detected photons, with origin),
.summary.json per part (every photon counted by end code and volume), points.json (index). Finished parts are skipped,
so an interrupted scan can be restarted. Read with optical/scan_data.py.
"""
import argparse
import itertools
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "g4" / "build"


def make_points(spec):
    grid = spec.get("grid") or {}
    keys = list(grid)
    points = []
    for i, combo in enumerate(itertools.product(*(grid[k] for k in keys)) if keys else [()]):
        params = dict(zip(keys, combo))
        base = spec.get("base", {})
        level = params.get("level", base.get("level", 4.0))
        sets = dict(base.get("set") or {})
        sets.update({k: v for k, v in params.items() if k != "level"})
        points.append(dict(id=i, params=params, level=level, set=sets))
    return points


def run_part(cmd, log):
    t0 = time.time()
    with open(log, "w") as f:
        r = subprocess.run(cmd, cwd=BUILD, stdout=f, stderr=subprocess.STDOUT)
    return r.returncode, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scan")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    spec = yaml.safe_load(open(a.scan))
    out = ROOT / "run" / "scans" / spec["name"]
    out.mkdir(parents=True, exist_ok=True)
    points = make_points(spec)
    n, chunks = int(spec["photons"]), int(spec.get("chunks", 1))
    per = [n // chunks + (1 if k < n % chunks else 0) for k in range(chunks)]
    macro_t = (BUILD / "production.mac").read_text()
    jobs = []
    for p in points:
        cfg = out / f"point_{p['id']}.json"
        args = [sys.executable, str(ROOT / "optical" / "make_config.py"), "--level", str(p["level"]), "--out", str(cfg)]
        for k, v in p["set"].items():
            args += ["--set", f"{k}={json.dumps(v)}"]
        if not a.dry:
            subprocess.run(args, check=True, capture_output=True)
        p["config"] = cfg.name
        p["parts"] = []
        for k in range(chunks):
            stem = out / f"point_{p['id']}_{k}"
            mac = stem.with_suffix(".mac")
            mac.write_text(macro_t.replace("{shape}", spec["source"]).replace("{rmax}", str(spec.get("rmax_mm", 30)))
                           .replace("{n}", str(per[k])))
            seed = int(spec.get("seed", 1000)) + 1000 * p["id"] + k
            p["parts"].append(dict(file=stem.name + ".bin", seed=seed, photons=per[k]))
            if Path(str(stem) + ".bin.summary.json").exists():
                continue
            cmd = [str(BUILD / "xamsopt"), "-c", str(cfg), "-o", str(stem) + ".bin", "-s", str(seed), "-d", str(mac)]
            jobs.append((cmd, str(stem) + ".log"))
    json.dump(dict(spec=spec, points=points), open(out / "points.json", "w"), indent=1)
    print(f"{spec['name']}: {len(points)} points x {chunks} parts, {n:.2g} photons per point; {len(jobs)} parts to run")
    if a.dry or not jobs:
        return 0
    t0 = time.time()
    with ThreadPoolExecutor(a.jobs) as ex:
        results = list(ex.map(lambda j: run_part(*j), jobs))
    bad = [j[1] for j, r in zip(jobs, results) if r[0] != 0]
    wall = time.time() - t0
    cpu = sum(r[1] for r in results)
    print(f"done in {wall:.0f} s wall ({cpu:.0f} s summed over parts, {a.jobs} parallel)")
    timing = dict(wall_s=wall, part_s_sum=cpu, jobs=a.jobs, parts=len(jobs))
    json.dump(timing, open(out / "timing.json", "w"), indent=1)
    if bad:
        print("FAILED parts (see logs):", *bad, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
