#!/usr/bin/env python3
"""Step-1 check: point source in liquid xenon, square photocathode (side a, QE 1) at distance d, no absorption /
Rayleigh / reflection. The detected fraction must equal the solid angle of the square / 4 pi:
    Omega = 4 arcsin( a^2 / (a^2 + 4 d^2) )      (square of side a, centred, at distance d)
Run inside the g4 environment from optical_sim/:  python optical/check_step1.py"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "optical"))
from read_output import read  # noqa: E402

BUILD = ROOT / "g4" / "build"
RUN = ROOT / "run" / "step1"


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    a = 48.5
    ok = True
    print(f"{'d [mm]':>7} {'expected':>9} {'simulated':>10} {'± stat':>8} {'pull':>6}")
    for d in (10.0, 30.0, 60.0):
        cfg = RUN / f"config_d{d:.0f}.json"
        subprocess.run([sys.executable, str(ROOT / "optical" / "make_config.py"), "--level", "4.0",
                        "--set", 'geometry_mode="test_box"', "--set", f"test_distance_mm={d}", "--set", "test_qe=1.0",
                        "--set", "optics.lxe.absorption_length_cm=1e9", "--set", "optics.lxe.rayleigh_length_cm=1e9",
                        "--out", str(cfg)], check=True, capture_output=True)
        out = RUN / f"photons_d{d:.0f}.bin"
        subprocess.run([str(BUILD / "xamsopt"), "-c", str(cfg), "-o", str(out), "-s", "1",
                        str(BUILD / "step1_solid_angle.mac")], check=True, capture_output=True, cwd=BUILD)
        rec, _ = read(out)
        n = len(rec)
        f_sim = float((rec["end_code"] == 1).mean())
        err = np.sqrt(f_sim * (1 - f_sim) / n)
        f_exp = 4 * np.arcsin(a * a / (a * a + 4 * d * d)) / (4 * np.pi)
        pull = (f_sim - f_exp) / err
        ok &= abs(pull) < 4
        others = {c: int((rec["end_code"] == c).sum()) for c in np.unique(rec["end_code"])}
        print(f"{d:7.1f} {f_exp:9.5f} {f_sim:10.5f} {err:8.5f} {pull:6.2f}   end codes {others}")
    print("STEP 1 CHECK", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
