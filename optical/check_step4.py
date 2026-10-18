#!/usr/bin/env python3
"""Step-4 check: optical surfaces.
(a) Single surface (geometry_mode test_surface): a beam in liquid xenon hits a PTFE or steel slab at the origin at
    angle theta. Expected: reflected fraction = R; of the reflected photons a fraction f leaves exactly in the mirror
    direction (spike), the rest Lambertian (sin^2 of the polar angle uniform on [0, 1], mean cos = 2/3).
(b) XAMS with all surfaces black ("surfaces": 0) and with reflectivity 0 must give the same light distribution.
(c) XAMS with PTFE and steel reflectivity 1, no bulk absorption / scattering: the bookkeeping closes — every photon
    ends detected, on an absorber (PMT frame/body, photocathode beyond QE, world) or escaped; none ends on PTFE or
    steel, none undefined.
Run inside the g4 environment from optical_sim/:  python optical/check_step4.py"""
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "optical"))
from read_output import read  # noqa: E402

BUILD = ROOT / "g4" / "build"
RUN = ROOT / "run" / "step4"
CLEAR = ["optics.lxe.absorption_length_cm=1e9", "optics.lxe.rayleigh_length_cm=1e9"]


def config(name, sets):
    cfg = RUN / f"{name}.json"
    args = [sys.executable, str(ROOT / "optical" / "make_config.py"), "--level", "4.0", "--out", str(cfg)]
    for s in sets:
        args += ["--set", s]
    subprocess.run(args, check=True, capture_output=True)
    return cfg


def run(cfg, macro, subs, out, seed=4):
    text = (BUILD / macro).read_text()
    for k, v in subs.items():
        text = text.replace("{" + k + "}", str(v))
    m = out.with_suffix(".mac")
    m.write_text(text)
    subprocess.run([str(BUILD / "xamsopt"), "-c", str(cfg), "-o", str(out), "-s", str(seed), str(m)],
                   check=True, capture_output=True, cwd=BUILD)
    return read(out)


def part_a():
    ok = True
    n = 200000
    print("(a) single surface")
    print(f"{'material':>8} {'R':>5} {'f':>5} {'theta':>5} {'refl':>8} {'pull':>6} {'spike/refl':>10} {'pull':>6}"
          f" {'<cos> diffuse':>13} {'KS p':>6}")
    for mat, r, f in (("ptfe", 0.95, 0.2), ("ptfe", 0.90, 0.0), ("steel", 0.35, 0.0)):
        key = "optics.stainless_steel_reflectivity" if mat == "steel" else "optics.ptfe_in_liquid.reflectivity"
        sets = ['geometry_mode="test_surface"', f'test_surface_material="{mat}"', f"{key}={r}",
                f"optics.ptfe_in_liquid.specular_fraction={f}"] + CLEAR
        cfg = config(f"surface_{mat}_{r}_{f}", sets)
        for th in (0, 30, 60):
            t = np.radians(th)
            d = np.array([np.sin(t), -np.cos(t)])          # downwards onto the slab
            p = -10.0 * d
            rec, _ = run(cfg, "step4_surface.mac", dict(px=f"{p[0]:.6f}", pz=f"{p[1]:.6f}", dx=f"{d[0]:.8f}",
                                                          dz=f"{d[1]:.8f}", n=n), RUN / f"surf_{mat}_{r}_{f}_{th}.bin")
            esc = rec[(rec["end_code"] == 4) & (rec["z1"] > 0)]
            refl = len(esc) / n
            e_r = np.sqrt(r * (1 - r) / n) or 1 / n
            v = np.stack([esc["x1"], esc["y1"], esc["z1"]], 1).astype(float)
            v /= np.linalg.norm(v, axis=1)[:, None]
            mirror = np.array([d[0], 0, -d[1]])
            spike = (v @ mirror) > np.cos(np.radians(0.2))
            fs = spike.mean()
            e_f = np.sqrt(f * (1 - f) / len(esc)) if f > 0 else 1.0
            cosd = v[~spike, 2]
            # Lambertian: sin^2 = 1 - cos^2 uniform on [0, 1]
            u = np.sort(1 - cosd**2)
            ks = np.max(np.abs(np.arange(1, len(u) + 1) / len(u) - u))
            p_ks = float(np.exp(-2 * len(u) * ks**2) * 2)
            pr, pf = (refl - r) / e_r, (fs - f) / e_f
            spike_ok = abs(pf) < 4 if f > 0 else fs < 1e-4  # f = 0: only Lambertian leakage into the 0.2 deg cone
            ok &= abs(pr) < 4 and spike_ok and p_ks > 1e-3 and abs(cosd.mean() - 2 / 3) < 0.005
            print(f"{mat:>8} {r:5.2f} {f:5.2f} {th:5d} {refl:8.5f} {pr:6.2f} {fs:10.5f} {pf if f > 0 else float("nan"):6.2f} {cosd.mean():13.4f}"
                  f" {min(p_ks, 1):6.3f}")
    return ok


def xams(name, sets, n=200000):
    cfg = config(name, sets + CLEAR)
    return run(cfg, "step4_xams.mac", dict(n=n), RUN / f"{name}.bin")


def part_b():
    print("(b) black surfaces vs reflectivity 0 (S2-like source in the gas gap)")
    n = 200000
    a, _ = xams("black", ["surfaces=0"], n)
    b, _ = xams("refl0", ["optics.ptfe_in_liquid.reflectivity=0", "optics.stainless_steel_reflectivity=0"], n)
    ok = True
    for s, lab in ((0, "bottom"), (1, "top I"), (2, "top II"), (3, "top III"), (4, "top IV"), (6, "SiPM 6"),
                   (7, "SiPM 7")):
        ka = int(((a["end_code"] == 1) & (a["sensor"] == s)).sum())
        kb = int(((b["end_code"] == 1) & (b["sensor"] == s)).sum())
        pull = (ka - kb) / np.sqrt(max(ka + kb, 1))
        ok &= abs(pull) < 4
        print(f"  {lab:>8}: black {ka / n:.5f}  R=0 {kb / n:.5f}  pull {pull:5.2f}")
    return ok


def part_c():
    print("(c) PTFE and steel reflectivity 1: bookkeeping")
    n = 100000
    rec, vols = xams("refl1", ["optics.ptfe_in_liquid.reflectivity=1", "optics.stainless_steel_reflectivity=1"], n)
    codes = {c: int((rec["end_code"] == c).sum()) for c in (0, 1, 2, 3, 4)}
    surf = rec[rec["end_code"] == 3]
    names = {vols.get(int(i), str(i)): int((surf["volume"] == i).sum()) for i in np.unique(surf["volume"])}
    bad = {k: v for k, v in names.items() if k == "PTFE" or "Bar" in k or "Ring" in k}
    print(f"  end codes {codes}; surface absorbed on {names}")
    print(f"  mean reflections {rec['n_refl'].mean():.2f}, max {rec['n_refl'].max()}")
    return codes[0] == 0 and codes[2] == 0 and not bad and sum(codes.values()) == n


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    ok = part_a()
    ok &= part_b()
    ok &= part_c()
    print("STEP 4 CHECK", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
