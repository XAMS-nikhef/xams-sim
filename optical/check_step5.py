#!/usr/bin/env python3
"""Step-5 check: light sources and production runs.
(a) Sources: S2 uniform from the liquid surface to just below the anode foil, S1 uniform from just above the cathode
    foil to just below the gate foil, both r < rmax: z range follows the config (liquid levels 2 and 4 mm); z, r^2 and
    phi uniform (Kolmogorov-Smirnov).
(b) Bookkeeping of the production output: every photon counted once in the summary; one record per detected photon.
(c) Precision and speed, from the reference scans scans/step5_reference*.yaml (run them first with
    optical/run_scan.py): statistical precision of the top fraction per scan point < 0.5 % (relative); photons needed
    for 0.5 % per bin (S2 in 5 mm rings of r, S1 in 2 mm slices of z); photons per second.
Run inside the g4 environment from optical_sim/:  python optical/check_step5.py"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "optical"))
from read_output import read  # noqa: E402
from scan_data import load, top_fraction  # noqa: E402

BUILD = ROOT / "g4" / "build"
RUN = ROOT / "run" / "step5"


def ks_uniform(x, lo, hi):
    u = np.sort((x - lo) / (hi - lo))
    d = np.max(np.abs(np.arange(1, len(u) + 1) / len(u) - u))
    return float(min(1.0, 2 * np.exp(-2 * len(u) * d**2)))


def part_a():
    print("(a) sources")
    ok = True
    macro = (BUILD / "production.mac").read_text()
    for shape, level, zlo, zhi in (("s2", 4.0, 4.0, 7.915), ("s2", 2.0, 2.0, 7.915), ("s1", 4.0, -51.715, -0.085)):
        cfg = RUN / f"cfg_{level}.json"
        subprocess.run([sys.executable, str(ROOT / "optical" / "make_config.py"), "--level", str(level), "--out",
                        str(cfg)], check=True, capture_output=True)
        m = RUN / f"src_{shape}_{level}.mac"
        m.write_text(macro.replace("{shape}", shape).replace("{rmax}", "30").replace("{n}", "100000"))
        out = RUN / f"src_{shape}_{level}.bin"
        subprocess.run([str(BUILD / "xamsopt"), "-c", str(cfg), "-o", str(out), "-s", "7", str(m)], check=True,
                       capture_output=True, cwd=BUILD)
        rec, _ = read(out)
        z, r2, phi = rec["z0"], rec["x0"] ** 2 + rec["y0"] ** 2, np.arctan2(rec["y0"], rec["x0"])
        pz, pr, pp = ks_uniform(z, zlo, zhi), ks_uniform(r2, 0, 900), ks_uniform(phi, -np.pi, np.pi)
        inside = z.min() >= zlo - 1e-3 and z.max() <= zhi + 1e-3 and r2.max() <= 900 + 1e-2
        ok &= inside and min(pz, pr, pp) > 1e-3
        print(f"  {shape} level {level}: z {z.min():8.3f} .. {z.max():7.3f} (expected {zlo} .. {zhi}),"
              f" r max {np.sqrt(r2.max()):.2f}; KS p z {pz:.2f}, r^2 {pr:.2f}, phi {pp:.2f}")
    return ok


def part_bc():
    ok = True
    print("(b) bookkeeping and (c) precision / speed")
    for name, binvar, edges in (("step5_reference", "r", np.arange(0, 31, 5)),
                                ("step5_reference_s1", "z", np.arange(-52, 0.1, 2))):
        s = load(name)
        p = s["points"][0]
        rec = p["rec"]
        n_tally = sum(p["tally"].values())
        n_det = sum(v for (code, _), v in p["tally"].items() if code == 1)
        ok_b = n_tally == p["n_photons"] == s["spec"]["photons"] and n_det == len(rec)
        ok &= ok_b
        f, e = top_fraction(rec)
        rate = p["n_photons"] / s["timing"]["part_s_sum"] if s["timing"] else float("nan")
        ok &= e / f < 0.005
        print(f"  {name}: {p['n_photons']:.3g} photons, {len(rec)} detected ({len(rec) / p['n_photons']:.4f});"
              f" bookkeeping {'ok' if ok_b else 'WRONG'}")
        print(f"    top fraction {f:.4f} ± {e:.4f} ({100 * e / f:.2f} %); {rate:.3g} photons/s per process")
        x = np.hypot(rec["x0"], rec["y0"]) if binvar == "r" else rec["z0"]
        need = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            sel = rec[(x >= lo) & (x < hi)]
            fb, eb = top_fraction(sel)
            # photons needed in the whole source for 0.5 % in this bin (error scales with 1/sqrt(N))
            need.append(p["n_photons"] * (eb / fb / 0.005) ** 2)
        print(f"    photons per point for 0.5 % in every {binvar} bin ({edges[1] - edges[0]:.0f} mm): "
              f"{max(need):.2g} (worst bin), {np.median(need):.2g} (median)")
    return ok


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    ok = part_a()
    ok &= part_bc()
    print("STEP 5 CHECK", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
