"""Provenance: with which parameters a run's data were made, kept next to the data and readable later.

Every `xamssim chain` run writes `<data>/provenance/<run id>/<date-time>_<run key>_<content>.json` (skipped when the newest file
of that run has the same content): the run file, state, source and detector as resolved at the time (full geometry,
materials, HV case), the chain settings incl. the electron lifetime, the maps used (key, files, producer version), the
Geant4 configuration the input was made with (`config.json`) and its output hash, every strax product made with its
lineage hash and lineage, and the xams-sim code (commit, uncommitted changes). It survives a change of geometry.yaml,
a rerun of Geant4 and `xamssim list --delete`.

    xamssim show <run> [--product T | --hash H | --n N] [--diff] [--full]
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
from pathlib import Path

from .config import DATA, ROOT, Resolved, short_hash

PROV = DATA / "provenance"


def code_info() -> dict:
    def git(*a):
        return subprocess.check_output(["git", "-C", str(ROOT), *a], text=True).strip()
    try:
        changed = [ln[3:] for ln in git("status", "--porcelain").splitlines() if ln.strip()]
        diff = git("diff", "HEAD") if changed else ""
        return dict(commit=git("rev-parse", "HEAD"), describe=git("describe", "--always", "--dirty", "--tags"),
                    uncommitted=changed, uncommitted_diff_sha=hashlib.sha256(diff.encode()).hexdigest()[:12] if diff else None)
    except Exception:
        return dict(commit="unknown")


def record(res: Resolved, st, run_id: str, products: list, settings: dict, g4_dir: Path) -> dict:
    from .chain import physics
    from .maps import find
    maps = {}
    for kind, key in res.map_keys().items():
        e = find(kind, key)
        maps[kind] = dict(key=key, present=e is not None, **({k: e[k] for k in ("files", "producer", "producer_version",
                                                                                 "created")} if e else {}))
    g4 = {}
    try:
        g4["config"] = json.loads((Path(g4_dir) / "config.json").read_text())
        g4["output_hash"] = settings.get("g4_output_hash")
        g4["counts"] = json.loads((Path(g4_dir) / "deposits.json").read_text()).get("counts")
    except (OSError, ValueError):
        pass
    prods = {}
    for t in products:
        try:
            k = st.key_for(run_id, t)
            prods[t] = dict(lineage_hash=k.lineage_hash, lineage=k.lineage)
        except Exception as e:                                           # pragma: no cover
            prods[t] = dict(error=str(e)[:200])
    return dict(run_id=run_id, run_key=res.run_key(), run_file=str(Path(res.run_path).resolve()), run=res.run,
                state_name=res.state_name, state=res.state, source_name=res.source_name, source=res.source,
                detector=res.detector, geometry_file=str(res.geometry_path), geometry=res.geometry,
                materials=res.materials, hv_case=res.hv_case, hv_global=res.hv_global, physics=physics(res),
                settings={k: v for k, v in settings.items() if k != "nest_width_parameters"},
                maps=maps, geant4=g4, products=prods, code=code_info())


def _content_hash(rec: dict) -> str:
    return short_hash({k: v for k, v in rec.items() if k not in ("created", "code")} | {"code": rec.get("code", {}).get("commit")})


def write(rec: dict) -> Path:
    d = PROV / rec["run_id"]
    d.mkdir(parents=True, exist_ok=True)
    h = _content_hash(rec)
    for f in sorted(d.glob("*.json"), reverse=True)[:1]:                 # newest file: same content -> keep it
        try:
            if _content_hash(json.loads(f.read_text())) == h:
                return f
        except (OSError, ValueError):
            pass
    rec = dict(created=_dt.datetime.now().isoformat(timespec="seconds"), **rec)
    f = d / f"{rec['created'].replace(':', '').replace('-', '')}_{rec['run_key']}_{h[:6]}.json"
    f.write_text(json.dumps(rec, indent=1, default=str))
    return f


def entries(run_id: str) -> list:
    d = PROV / run_id
    return sorted(d.glob("*.json")) if d.exists() else []


def _flat(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flat(v, f"{prefix}.{k}" if prefix else str(k)))
    else:
        out[prefix] = d
    return out


def diff(old: dict, new: dict, limit: int = 60) -> list:
    """Differences between two nested configurations: (path, old, new); long lists summarised."""
    a, b = _flat(old), _flat(new)
    rows = []
    for k in sorted(set(a) | set(b)):
        if a.get(k, "<absent>") != b.get(k, "<absent>"):
            va, vb = a.get(k, "<absent>"), b.get(k, "<absent>")
            if isinstance(va, list) and len(va) > 8 or isinstance(vb, list) and len(vb) > 8:
                va = f"list of {len(va) if isinstance(va, list) else '-'}"
                vb = f"list of {len(vb) if isinstance(vb, list) else '-'} (changed)"
            rows.append((k, va, vb))
    return rows[:limit] + ([("...", f"{len(rows) - limit} more", "")] if len(rows) > limit else [])


SECTIONS = ("run", "state", "source", "detector", "geometry", "materials", "hv_case", "physics")


def show(run: str, product: str | None = None, lineage_hash: str | None = None, n: int | None = None,
         full: bool = False, with_diff: bool = False) -> int:
    run_id = Path(run).stem
    files = entries(run_id)
    if not files:
        print(f"no provenance for run '{run_id}' in {PROV / run_id} (written by xamssim chain since 2026-10-19)")
        return 1
    recs = [json.loads(f.read_text()) for f in files]
    print(f"provenance of run {run_id} ({PROV / run_id}):")
    for i, (f, r) in enumerate(zip(files, recs)):
        c = r.get("code", {})
        print(f"  [{i}] {r['created']}  detector {r['detector']}, state {r['state_name']}, source {r['source_name']}, "
              f"{r['run']['n_events']:.0e} events; xams-sim {c.get('describe', c.get('commit', '?'))}; "
              f"{len(r['products'])} products")
    pick = len(recs) - 1
    if n is not None:
        pick = n
    elif lineage_hash or product:
        hits = [i for i, r in enumerate(recs) for t, p in r["products"].items()
                if (not product or t == product) and (not lineage_hash or p.get("lineage_hash") == lineage_hash)]
        if not hits:
            print(f"no entry with {product or ''} {lineage_hash or ''}".rstrip())
            return 1
        pick = hits[-1]
    r = recs[pick]
    print(f"\nentry [{pick}], {files[pick].name}")
    if full:
        print(json.dumps(r, indent=1))
        return 0
    g, hv, s = r["geometry"], r["hv_case"], r["state"]
    c = r.get("code", {})
    print(f"  code       {c.get('commit', '?')[:10]} ({c.get('describe')})"
          + (f"; uncommitted changes in {len(c['uncommitted'])} files (diff {c.get('uncommitted_diff_sha')})"
             if c.get("uncommitted") else ""))
    print(f"  run file   {r['run_file']}" + (f" (run number {int(r['run']['run_number']):06d})"
                                              if r["run"].get("run_number") is not None else ""))
    print(f"  detector   {r['detector']} ({r['geometry_file']}, geometry version {g.get('meta', {}).get('version')})")
    print(f"  state      {r['state_name']}: level {s['liquid_level_mm']} mm, lifetime {r['settings'].get('electron_lifetime_us')} µs; "
          f"HV A {hv['A']:+g} G {hv['G']:+g} C {hv['C']:+g} BS {hv['BS']:+g} V")
    print(f"  source     {r['source_name']}: {r['source'].get('isotope')} at {r['source'].get('position_mm')} mm; "
          f"{r['run']['n_events']:.3g} events, seed {r['run']['seed']}")
    o = r["materials"].get("optics", {})
    print(f"  optics     PTFE R {o.get('ptfe_in_liquid', {}).get('reflectivity')}, steel R "
          f"{o.get('stainless_steel_reflectivity')}, Rayleigh {o.get('lxe', {}).get('rayleigh_length_cm')} cm")
    print(f"  geant4     output hash {r['geant4'].get('output_hash')}, counts {r['geant4'].get('counts')}")
    ph = r.get("physics", {})
    print("  physics    " + ", ".join(f"{k} {v}" for k, v in ph.items()))
    cs = ph.get("cloud_samples")
    print("  splitting  " + ("not in this version (made before cloud splitting, 2026-10-19)" if cs is None else
                             f"on: {cs} points per cluster, track sigma {ph.get('cloud_track_sigma_mm')} mm" if cs > 1 else
                             "off (cloud_samples 1)"))
    vers = {}
    for p in r["products"].values():
        for t, lin in (p.get("lineage") or {}).items():
            if isinstance(lin, (list, tuple)) and len(lin) >= 2 and str(lin[0]).startswith("Xams"):
                vers[lin[0]] = lin[1]
    if vers:
        print("  plugins    " + ", ".join(f"{k} {v}" for k, v in sorted(vers.items())))
    print("  maps       " + ", ".join(f"{k} {v['key']}{'' if v['present'] else ' (missing)'}" for k, v in r["maps"].items()))
    print("  products   " + ", ".join(f"{t} {p.get('lineage_hash')}" for t, p in r["products"].items()))
    if with_diff:
        from .config import resolve
        try:
            now = resolve(r["run_file"])
        except Exception as e:
            print(f"\ncannot resolve the run file now: {e}")
            return 1
        cur = dict(run=now.run, state=now.state, source=now.source, detector=now.detector, geometry=now.geometry,
                   materials=now.materials, hv_case=now.hv_case, physics=__import__("xamssim.chain").chain.physics(now))
        cur = json.loads(json.dumps(cur, default=str))              # as stored (dates as text, tuples as lists)
        rows = diff({k: r[k] for k in SECTIONS}, cur)
        print(f"\nchanged since then (entry -> now): {len(rows)}" if rows else "\nunchanged: the run file resolves to the "
                                                                          "same configuration now")
        for k, a, b in rows:
            print(f"  {k}: {a} -> {b}")
    return 0
