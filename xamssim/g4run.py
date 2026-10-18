"""Run the Geant4 particle mode for a simulation run (plan S2).

    xamssim g4 config/runs/cs137_cmb50_001.yaml [--events N] [--seed S] [--out run/g4/<name>] [--dry-run]

Steps: resolve the run (config.py) -> config.json from geometry.yaml + materials.yaml (optical/make_config.py, liquid
level of the state) + mode "particle" + the source -> run.mac -> `xamsopt -m particle` in the conda env with Geant4
(default `g4`, via `conda run`) -> run/g4/<name>/deposits.{bin,events.bin,json} + g4.log. Read the output with
`xamssim.g4io.read(<dir>/deposits)`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .config import ROOT, ConfigError, Resolved, resolve

G4_ENV = os.environ.get("XAMSSIM_G4_ENV", "g4")
XAMSOPT = ROOT / "g4" / "build" / "xamsopt"
# Z of the elements of common calibration sources (fallback: periodictable)
Z = {"H": 1, "Na": 11, "K": 19, "Co": 27, "Kr": 36, "Rb": 37, "Y": 39, "Cs": 55, "Ba": 56, "Eu": 63, "Pb": 82, "Bi": 83,
     "Po": 84, "Rn": 86, "Ra": 88, "Th": 90, "U": 92, "Am": 95}


def isotope_za(name: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*([A-Z][a-z]?)-?(\d+)m?\s*", name)
    if not m:
        raise ConfigError(f"isotope '{name}': expected e.g. 'Cs-137'")
    sym, a = m.group(1), int(m.group(2))
    if sym not in Z:
        try:
            import periodictable
            return getattr(periodictable, sym).number, a
        except Exception as e:  # noqa: BLE001
            raise ConfigError(f"isotope '{name}': unknown element '{sym}'") from e
    return Z[sym], a


def source_config(res: Resolved) -> dict:
    s = res.source
    if s.get("position_mm") is None:
        raise ConfigError(f"source '{res.source_name}' has no position_mm — needed for the particle mode")
    typ = s.get("type", "isotope")
    out = {"type": typ, "position_mm": [float(x) for x in s["position_mm"]], "direction": s.get("direction", "isotropic")}
    if typ == "isotope":
        out["Z"], out["A"] = isotope_za(s["isotope"])
        out["isotope"] = s["isotope"]
    elif typ == "gamma":
        if s.get("energy_keV") is None:
            raise ConfigError(f"source '{res.source_name}': type gamma needs energy_keV")
        out["energy_keV"] = float(s["energy_keV"])
    else:
        raise ConfigError(f"source '{res.source_name}': type must be isotope or gamma")
    if out["direction"] == "cone":
        if typ == "isotope":
            raise ConfigError("direction 'cone' only for type gamma (radioactive decays are isotropic)")
        out["half_angle_deg"] = float(s.get("half_angle_deg", 30.0))
        out["z_target_mm"] = float(s.get("z_target_mm", -25.9))
    return out


def build(res: Resolved, out_dir: Path, n_events: int, seed: int) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = out_dir / "config.json"
    subprocess.run([sys.executable, str(ROOT / "optical" / "make_config.py"), "--level", str(res.state["liquid_level_mm"]),
                    "--out", str(cfg_path)], check=True, capture_output=True, text=True)
    cfg = json.loads(cfg_path.read_text())
    src = source_config(res)
    reach = max(abs(src["position_mm"][0]), abs(src["position_mm"][1])) + 50.0
    cfg.update({
        "mode": "particle",
        "source": src,
        "world_half_mm": [max(300.0, reach), max(300.0, reach), max(300.0, abs(src["position_mm"][2]) + 50.0)],
        "particle": {"production_cut_mm": float(res.run.get("physics", {}).get("production_cut_mm", 0.1))},
        "xamssim": {"run": str(res.run_path), "run_key": res.run_key(), "state": res.state_name, "source": res.source_name,
                    "seed": seed, "n_events": n_events},
    })
    cfg_path.write_text(json.dumps(cfg, indent=1))
    mac = out_dir / "run.mac"
    mac.write_text("\n".join([
        "/control/verbose 0", "/run/verbose 0", "/tracking/verbose 0",
        "/run/initialize",
        f"/run/printProgress {max(1, n_events // 10)}",
        f"/run/beamOn {n_events}", ""]))
    return cfg_path, mac


def run(run_path, n_events: int | None = None, seed: int | None = None, out_dir=None, dry_run: bool = False) -> Path:
    res = resolve(run_path)
    n = int(n_events or res.run["n_events"])
    sd = int(res.run["seed"] if seed is None else seed)
    out = (Path(out_dir) if out_dir else ROOT / "run" / "g4" / Path(run_path).stem).resolve()
    if not XAMSOPT.exists():
        raise FileNotFoundError(f"{XAMSOPT} not built: cmake -S g4 -B g4/build && cmake --build g4/build -j8 (conda env {G4_ENV})")
    cfg, mac = build(res, out, n, sd)
    cmd = [str(XAMSOPT), "-m", "particle", "-c", str(cfg), "-o", str(out / "deposits.bin"), "-s", str(sd), str(mac)]
    if shutil.which("geant4-config") is None:   # not inside the Geant4 env: run through conda
        cmd = ["conda", "run", "-n", G4_ENV, "--no-capture-output"] + cmd
    print("run:", " ".join(cmd))
    if dry_run:
        return out
    t0 = time.time()
    with open(out / "g4.log", "w") as log:
        p = subprocess.run(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise RuntimeError(f"xamsopt failed (exit {p.returncode}); see {out / 'g4.log'}")
    h = json.loads((out / "deposits.json").read_text())
    print(f"done in {time.time() - t0:.0f} s: {h['counts']} -> {out}")
    return out
