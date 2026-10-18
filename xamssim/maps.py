"""Map registry: which maps exist for a detector state, where they are, and how to make the missing ones.

Maps live in `maps/` (not in git) and are listed in `maps/manifest.json`:

    {"maps": [{"kind": "field", "key": "<12-char input hash>", "state": "cmb50", "files": ["field/<key>/field.npz"],
               "producer": "efield (COMSOL)", "producer_version": "<git describe>", "created": "<ISO time>",
               "inputs": {...}}]}

The key is `Resolved.map_keys()[kind]`: a hash of exactly the inputs that kind of map depends on, so a map is reused by
every state / run with the same inputs and a change of any input asks for a new map. The registry never starts a slow
producer itself (COMSOL, Geant4 optical scans); it prints the command to run.
"""
from __future__ import annotations

import datetime as _dt
import json
import subprocess
from pathlib import Path

from .config import PRODUCTS, ROOT, Resolved

MAPS = ROOT / "maps"
MANIFEST = MAPS / "manifest.json"

# kind -> producer, command template, step of the plan that adds the export to the registry, first product needing it
KINDS = {
    "field": dict(producer="efield (COMSOL, full TPC)",
                  make="efield/comsol/run.sh --states {state} && xamssim maps --state {state} --export field", export_step="S3",
                  needed_for="quanta"),
    "drift": dict(producer="efield drift (field map + v(E))", make="(from the field map; drift export in S4)", export_step="S4",
                  needed_for="drifted_electrons"),
    "extraction_el": dict(producer="efield mesh cell (COMSOL)", make="efield/comsol/run_cell.sh stack --states {state}",
                          export_step="S5", needed_for="extracted_electrons"),
    "s1_light": dict(producer="optical (Geant4 optical scan)", make="python optical/run_scan.py optical/scans/fit_s1.yaml",
                     export_step="S6", needed_for="photoelectrons"),
    "s2_pattern": dict(producer="optical (Geant4 optical scan)", make="python optical/run_scan.py optical/scans/fit_s2.yaml",
                       export_step="S6", needed_for="photoelectrons"),
}


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"maps": []}
    with open(MANIFEST) as f:
        return json.load(f)


def save_manifest(man: dict) -> None:
    MAPS.mkdir(exist_ok=True)
    tmp = MANIFEST.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(man, f, indent=1)
    tmp.replace(MANIFEST)


def find(kind: str, key: str, man: dict | None = None) -> dict | None:
    man = man or load_manifest()
    for e in man["maps"]:
        if e["kind"] == kind and e["key"] == key and all((MAPS / p).exists() for p in e["files"]):
            return e
    return None


def git_version() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "describe", "--always", "--dirty", "--tags"], text=True).strip()
    except Exception:
        return "unknown"


def register(res: Resolved, kind: str, files: list, producer_version: str | None = None) -> dict:
    """Add a produced map to the manifest (files relative to maps/). Used by the producers' export steps (S4-S6)."""
    if kind not in KINDS:
        raise ValueError(f"unknown map kind '{kind}' (known: {list(KINDS)})")
    missing = [p for p in files if not (MAPS / p).exists()]
    if missing:
        raise FileNotFoundError(f"map files not in {MAPS}: {missing}")
    man = load_manifest()
    key = res.map_keys()[kind]
    man["maps"] = [e for e in man["maps"] if not (e["kind"] == kind and e["key"] == key)]
    entry = dict(kind=kind, key=key, state=res.state_name, files=list(files), producer=KINDS[kind]["producer"],
                 producer_version=producer_version or git_version(),
                 created=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                 inputs=res.map_inputs()[kind])
    man["maps"].append(entry)
    save_manifest(man)
    return entry


def needed(stop_after: str) -> list:
    """Map kinds needed to produce `stop_after`."""
    upto = PRODUCTS.index(stop_after)
    return [k for k, v in KINDS.items() if PRODUCTS.index(v["needed_for"]) <= upto]


def status(res: Resolved, kinds: list | None = None) -> list:
    """One row per map kind: present or missing, with the files or the command to make it."""
    man = load_manifest()
    keys = res.map_keys()
    rows = []
    for kind in kinds or list(KINDS):
        e = find(kind, keys[kind], man)
        k = KINDS[kind]
        rows.append(dict(kind=kind, key=keys[kind], present=e is not None, files=e["files"] if e else [],
                         make=k["make"].format(hv_case=res.state["hv_case"], state=res.state_name),
                         note="" if e else f"registry export added in {k['export_step']}"))
    return rows
