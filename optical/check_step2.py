#!/usr/bin/env python3
"""Step-2 check: Fresnel reflection and total internal reflection at the liquid-gas surface.
A beam from inside the liquid (n1 = 1.69) hits the surface (gas n2 = 1.00) at angle theta; with random linear
polarisation the reflected fraction is R = (Rs + Rp) / 2, and R = 1 beyond the critical angle asin(n2/n1) = 36.3 deg.
Run inside the g4 environment from the repository root:  python optical/check_step2.py"""
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from xamssim import g4bin  # noqa: E402  (starts xamsg4 in the g4 env from any env)
sys.path.insert(0, str(ROOT / "optical"))
from read_output import read  # noqa: E402

BUILD = ROOT / "g4" / "build"
RUN = ROOT / "run" / "step2"
N1, N2 = 1.69, 1.00


def fresnel(theta_deg):
    ti = np.radians(theta_deg)
    st = N1 / N2 * np.sin(ti)
    if st >= 1:
        return 1.0
    tt = np.arcsin(st)
    rs = ((N1 * np.cos(ti) - N2 * np.cos(tt)) / (N1 * np.cos(ti) + N2 * np.cos(tt))) ** 2
    rp = ((N1 * np.cos(tt) - N2 * np.cos(ti)) / (N1 * np.cos(tt) + N2 * np.cos(ti))) ** 2
    return 0.5 * (rs + rp)


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    cfg = RUN / "config.json"
    subprocess.run([sys.executable, str(ROOT / "optical" / "make_config.py"), "--level", "4.0",
                    "--set", 'geometry_mode="test_interface"', "--set", "optics.lxe.absorption_length_cm=1e9",
                    "--set", "optics.lxe.rayleigh_length_cm=1e9", "--out", str(cfg)], check=True, capture_output=True)
    macro = (BUILD / "step2_interface.mac").read_text()
    ok = True
    print(f"{'theta':>6} {'expected R':>11} {'simulated R':>12} {'± stat':>8} {'pull':>6}")
    for th in (0, 10, 20, 30, 34, 35.5, 37, 45, 60, 80):
        t = np.radians(th)
        d = np.array([np.sin(t), np.cos(t)])          # towards the surface
        p = -10.0 * d                                  # start 10 mm before the hit point at the origin
        m = RUN / f"theta_{th}.mac"
        m.write_text(macro.replace("{px}", f"{p[0]:.6f}").replace("{pz}", f"{p[1]:.6f}")
                     .replace("{dx}", f"{d[0]:.8f}").replace("{dz}", f"{d[1]:.8f}"))
        out = RUN / f"photons_{th}.bin"
        subprocess.run(g4bin.command(["-c", str(cfg), "-o", str(out), "-s", "2", str(m)]),
                       check=True, capture_output=True, cwd=BUILD)
        rec, _ = read(out)
        refl = float((rec["z1"] < 0).mean())
        err = max(np.sqrt(refl * (1 - refl) / len(rec)), 1 / len(rec))
        exp = fresnel(th)
        pull = (refl - exp) / err
        ok &= abs(pull) < 4
        print(f"{th:6.1f} {exp:11.5f} {refl:12.5f} {err:8.5f} {pull:6.2f}")
    print("STEP 2 CHECK", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
