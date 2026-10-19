"""`xamssim list`: what is in the data folder and whether it is current (plan S9, first version).

Per run (run id = run file name; run files in `<simulations>/*/runs/` and `config/runs/`):
    the run file (study, state, source, events), the Geant4 output (events, made for the Geant4 key the run file gives
    now or not, xams-sim version) and the strax products with their lineage hashes, each marked current (the hash the
    chain would compute now for the run file, its state, maps and settings) or old.
Per state: the maps (present / missing); maps in the registry that no state uses any more are listed as old.
`--prune` lists what is old with its size; `--delete` deletes it after a confirmation (`--yes`: without).

    xamssim list [filter] [--prune | --delete [--yes]]
"""
from __future__ import annotations

import contextlib
import io
import json
import warnings
from pathlib import Path

from .config import DATA, ROOT, ConfigError, resolve, resolve_state

STRAX = DATA / "strax"
G4 = DATA / "g4"


def _size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else (p.stat().st_size if p.exists() else 0)


def _mb(n: int) -> str:
    return f"{n / 1e6:.0f} MB" if n >= 1e6 else f"{n / 1e3:.0f} kB"


def run_files() -> dict:
    """run id -> run file paths (studies in the simulations folder, examples in xams-sim/config/runs)."""
    out: dict = {}
    for f in sorted(list(DATA.parent.glob("*/runs/*.yaml")) + list((ROOT / "config" / "runs").glob("*.yaml"))):
        out.setdefault(f.stem, []).append(f)
    return out


def strax_products() -> dict:
    """run id -> [(data type, lineage hash, folder)]."""
    out: dict = {}
    if STRAX.exists():
        for d in sorted(STRAX.iterdir()):
            parts = d.name.rsplit("-", 2)
            if d.is_dir() and len(parts) == 3:
                out.setdefault(parts[0], []).append((parts[1], parts[2], d))
    return out


def _stored_lifetimes(products) -> list:
    """Electron lifetimes in the lineage of the stored drift products (for states without a measured one)."""
    lts = set()
    for dtype, h, d in products:
        for m in d.glob("*-metadata.json"):
            try:
                lin = json.loads(m.read_text())["lineage"].get("drifted_electrons")
            except (OSError, ValueError, KeyError):
                continue
            if lin:
                lts.add(lin[2].get("electron_lifetime_us"))
    return sorted(x for x in lts if x is not None)


def current_hashes(run_path: Path, products) -> tuple[dict, str]:
    """data type -> set of lineage hashes the chain gives now (one per candidate lifetime); note if not computable."""
    from . import chain
    res = resolve(run_path)
    lifetimes = [None] if res.state.get("electron_lifetime_us") else (_stored_lifetimes(products) or [None])
    out: dict = {}
    note = ""
    for lt in lifetimes:
        over = {"electron_lifetime_us": float(lt)} if lt else {}
        try:
            with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
                warnings.simplefilter("ignore")
                st, rid = chain.context(run_path, **over)
                for dtype in {p[0] for p in products}:
                    try:
                        out.setdefault(dtype, set()).add(st.key_for(rid, dtype).lineage_hash)
                    except Exception:
                        pass
        except (FileNotFoundError, ConfigError) as e:
            note = str(e).splitlines()[0][:120]
    return out, note


def collect(flt: str = "") -> dict:
    rf, sp = run_files(), strax_products()
    ids = sorted(set(sp) | {d.name for d in G4.iterdir() if d.is_dir()} if G4.exists() else set(sp))
    runs = []
    for rid in ids:
        if flt and flt not in rid:
            continue
        r = dict(id=rid, files=rf.get(rid, []), g4=None, products=[], note="")
        g = G4 / rid
        if (g / "config.json").exists():
            x = json.loads((g / "config.json").read_text()).get("xamssim", {})
            counts = {}
            if (g / "deposits.json").exists():
                counts = json.loads((g / "deposits.json").read_text()).get("counts", {})
            r["g4"] = dict(key=x.get("g4_key"), version=x.get("code_version"), events=counts.get("events"),
                           size=_size(g), dir=g)
        prods = sp.get(rid, [])
        cur: dict = {}
        if len(r["files"]) == 1:
            run_path = r["files"][0]
            try:
                res = resolve(run_path)
                r.update(study=run_path.parent.parent.name, state=res.state_name, source=res.source_name,
                         n_events=res.run["n_events"], g4_key_now=res.g4_key())
                cur, r["note"] = current_hashes(run_path, prods) if prods else ({}, "")
            except ConfigError as e:
                r["note"] = f"run file invalid: {str(e)[:120]}"
        elif len(r["files"]) > 1:
            r["note"] = "run id in several run files: " + ", ".join(str(f.relative_to(DATA.parent.parent)) for f in r["files"])
        else:
            r["note"] = "no run file with this name"
        for dtype, h, d in prods:
            state = "current" if h in cur.get(dtype, set()) else ("?" if dtype not in cur else "old")
            r["products"].append(dict(type=dtype, hash=h, state=state, size=_size(d), dir=d))
        runs.append(r)
    return dict(runs=runs, maps=map_overview(runs))


def map_overview(runs) -> dict:
    from .maps import KINDS, load_manifest, status
    states = sorted(p.stem for p in (ROOT / "config" / "states").glob("*.yaml"))
    used = {r.get("state") for r in runs}
    per_state, keys_now = {}, {}
    for s in states:
        try:
            res = resolve_state(s)
        except ConfigError as e:
            per_state[s] = dict(error=str(e)[:120])
            continue
        rows = status(res)
        per_state[s] = dict(rows=rows, used=s in used)
        for row in rows:
            keys_now.setdefault(row["kind"], set()).add(row["key"])
    old = []
    for e in load_manifest()["maps"]:
        if e["key"] not in keys_now.get(e["kind"], set()):
            from .maps import MAPS
            old.append(dict(kind=e["kind"], key=e["key"], state=e.get("state"), created=e.get("created", "")[:10],
                            size=sum(_size(MAPS / f) for f in e["files"]), files=e["files"]))
    return dict(states=per_state, old=old, kinds=list(KINDS))


def old_items(d) -> list:
    """Everything old in a collect() result: Geant4 output made for another Geant4 key, strax products whose lineage
    the chain no longer gives, maps no state has the key of. Products that could not be checked ('?') and runs without
    a run file are never included."""
    from .maps import MAPS
    items = []
    for r in d["runs"]:
        g = r["g4"]
        if g and r.get("g4_key_now") and g["key"] != r["g4_key_now"]:
            items.append(dict(kind="g4", path=g["dir"], size=g["size"]))
        items += [dict(kind="strax", path=p["dir"], size=p["size"]) for p in r["products"] if p["state"] == "old"]
    for m in d["maps"]["old"]:
        items.append(dict(kind="map", path=MAPS / m["files"][0].rsplit("/", 1)[0], size=m["size"], map=(m["kind"], m["key"]),
                          note=f"{m['kind']} {m['key']}, state {m['state']}, {m['created']}; and its manifest entry"))
    return items


def remove(items) -> None:
    """Delete the items of old_items() (folders) and the manifest entries of the old maps."""
    import shutil
    from .maps import load_manifest, save_manifest
    for it in items:
        if not str(it["path"]).startswith(str(DATA)):
            raise RuntimeError(f"refusing to delete outside the data folder: {it['path']}")
        shutil.rmtree(it["path"], ignore_errors=True) if Path(it["path"]).is_dir() else Path(it["path"]).unlink(missing_ok=True)
    gone = {it["map"] for it in items if it["kind"] == "map"}
    if gone:
        man = load_manifest()
        man["maps"] = [e for e in man["maps"] if (e["kind"], e["key"]) not in gone]
        save_manifest(man)


def show(flt: str = "", prune: bool = False, delete: bool = False, yes: bool = False) -> int:
    d = collect(flt)
    print(f"data folder {DATA}")
    for r in d["runs"]:
        head = f"\n{r['id']}"
        if "state" in r:
            head += f"   study {r['study']}, state {r['state']}, source {r['source']}, {r['n_events']:.0e} events"
        print(head)
        if r["note"]:
            print(f"  note: {r['note']}")
        g = r["g4"]
        if g:
            now = r.get("g4_key_now")
            ok = "current" if now and g["key"] == now else ("old (Geant4 key " + str(g["key"]) + ", run file now "
                                                             + str(now) + ")" if now else "?")
            print(f"  geant4   {g['events'] or '?':>9} events  {_mb(g['size']):>7}  {ok}  (xams-sim {g['version']})")
        else:
            print("  geant4   none")
        for p in sorted(r["products"], key=lambda p: p["type"]):
            print(f"  {p['type']:<24} {p['hash']}  {_mb(p['size']):>7}  {p['state']}")
    print("\nmaps per state (registry <data>/maps/manifest.json):")
    for s, v in d["maps"]["states"].items():
        if "error" in v:
            print(f"  {s:<12} {v['error']}")
            continue
        have = [row["kind"] for row in v["rows"] if row["present"]]
        miss = [row["kind"] for row in v["rows"] if not row["present"]]
        print(f"  {s:<12} {'(used by runs) ' if v['used'] else ''}present: {', '.join(have) or '-'}"
              + (f"; missing: {', '.join(miss)}" if miss else ""))
    old_maps = d["maps"]["old"]
    print(f"  old maps (no state has their key now): {len(old_maps)}, {_mb(sum(m['size'] for m in old_maps))}")
    if prune or delete:
        items = old_items(d)
        print(f"\nold data ({'to delete' if delete else 'not deleted; xamssim list --delete removes it'}):")
        for it in items:
            print(f"  {_mb(it['size']):>7}  {it['path']}" + (f"   ({it['note']})" if it.get("note") else ""))
        tot = sum(it["size"] for it in items)
        print(f"  total {_mb(tot)} in {len(items)} items")
        if delete and items:
            if not yes:
                try:
                    ok = input(f"delete these {len(items)} items ({_mb(tot)})? [y/N] ").strip().lower() == "y"
                except EOFError:
                    ok = False
                if not ok:
                    print("nothing deleted")
                    return 0
            remove(items)
            print(f"deleted {len(items)} items, {_mb(tot)}")
    return 0
