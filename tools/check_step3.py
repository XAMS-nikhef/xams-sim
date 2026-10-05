#!/usr/bin/env python3
"""Step-3 check: open fraction of one mesh versus angle.
A beam crosses a mesh (square holes h, bars w, pitch p = h + w, foil thickness t) at polar angle theta and azimuth phi
(measured from the mesh x bars). The bars parallel to y shadow t |tan(theta) cos(phi)| of each hole in x, those
parallel to x shadow t |tan(theta) sin(phi)| in y:
    T = (h - t |tan(theta) cos(phi)|) (h - t |tan(theta) sin(phi)|) / p^2      (0.888 at normal incidence)
The bars are black (no optical surface yet), so a photon either passes or stops on a bar.
Two comparisons: (1) per photon, the straight path through the foil (|z| < t/2) is traced analytically against the bar
lattice (bar centre lines at k p, crossing on the axis); Geant4 must agree photon by photon; (2) the transmitted
fraction against the formula above (the 25 mm beam disc averages over ~290 cells, so a small sampling offset remains).
Run inside the g4 environment from optical_sim/:  python tools/check_step3.py"""
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from read_output import read  # noqa: E402

BUILD = ROOT / "build"
RUN = ROOT / "run" / "step3"
H, W, T = 2.45, 0.15, 0.15
P = H + W


def expected(theta, phi):
    tt = np.tan(np.radians(theta))
    return max(H - T * abs(tt * np.cos(np.radians(phi))), 0) * max(H - T * abs(tt * np.sin(np.radians(phi))), 0) / P**2


def blocked(x0, y0, z0, d):
    """Analytic: does the straight path from (x0, y0, z0) along d cross a bar inside the foil |z| < t/2?"""
    s0, s1 = (-T / 2 - z0) / d[2], (T / 2 - z0) / d[2]
    hit = np.zeros(len(x0), bool)
    for c0, dc in ((x0, d[0]), (y0, d[1])):
        a, b = c0 + s0 * dc, c0 + s1 * dc
        lo, hi = np.minimum(a, b) - W / 2, np.maximum(a, b) + W / 2
        hit |= np.floor(hi / P) >= np.ceil(lo / P)
    return hit


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    cfg = RUN / "config.json"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_config.py"), "--level", "4.0",
                    "--set", 'geometry_mode="test_mesh"', "--set", "optics.lxe.absorption_length_cm=1e9",
                    "--set", "optics.lxe.rayleigh_length_cm=1e9", "--out", str(cfg)], check=True, capture_output=True)
    macro = (BUILD / "step3_mesh.mac").read_text()
    ok = True
    print(f"{'theta':>6} {'phi':>5} {'per-photon agree':>17} {'formula T':>10} {'simulated T':>12} {'± stat':>8} {'pull':>6}")
    for phi in (0, 45, 29.4):
        for th in (0, 20, 40, 60, 75):
            t, f = np.radians(th), np.radians(phi)
            d = np.array([np.sin(t) * np.cos(f), np.sin(t) * np.sin(f), np.cos(t)])
            p = -2.0 * d / d[2]                        # start 2 mm below the mesh, beam centre hits the origin
            m = RUN / f"t{th}_p{phi}.mac"
            m.write_text(macro.replace("{px}", f"{p[0]:.6f}").replace("{py}", f"{p[1]:.6f}")
                         .replace("{pz}", f"{p[2]:.6f}").replace("{dx}", f"{d[0]:.8f}")
                         .replace("{dy}", f"{d[1]:.8f}").replace("{dz}", f"{d[2]:.8f}"))
            out = RUN / f"photons_t{th}_p{phi}.bin"
            subprocess.run([str(BUILD / "xamsopt"), "-c", str(cfg), "-o", str(out), "-s", "3", str(m)],
                           check=True, capture_output=True, cwd=BUILD)
            rec, _ = read(out)
            passed = (rec["end_code"] == 4) & (rec["z1"] > 1)  # escaped above the mesh (not stopped on a bar)
            agree = float((passed == ~blocked(rec["x0"], rec["y0"], rec["z0"], d)).mean())
            ok &= agree > 0.9999
            tr = float(passed.mean())
            err = max(np.sqrt(tr * (1 - tr) / len(rec)), 1 / len(rec))
            exp = expected(th, phi)
            pull = (tr - exp) / err
            ok &= abs(pull) < 5
            print(f"{th:6.1f} {phi:5.1f} {agree:17.6f} {exp:10.5f} {tr:12.5f} {err:8.5f} {pull:6.2f}")
    print("STEP 3 CHECK", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
