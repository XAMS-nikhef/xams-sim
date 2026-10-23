"""Simulated runs as runs for amstrax and the analysis (plan S8).

    xamssim amstrax <run file>        # after: xamssim chain <run file> --target raw_records

copies the chain's raw records of a run with a `run_number` (900000-999999) into the analysis' data folder
(STORE: `<XAMS>/measurements/strax_data`, or $XAMSSIM_AMSTRAX_STORE) under amstrax's own keys (`raw_records`,
`raw_records_sipm`), with a run document and a truth file, so that the run is addressed by its number like a data run:
the analysis' context, `EventDisplay(900001, ...)`, the step scripts. amstrax processes it on request (records, peaks,
events, ...), with the calibration the analysis gives it (correction files of amstrax_files, gains, processing.json),
never with the simulation's own values.

Run document (`<number>-metadata.json`, as the run database has it for data): number, mode, start / end, tags, comment,
the DAQ config (thresholds, channel map, pre-trigger register), and a section `xamssim` with the run file, run key,
state, source, detector, condition and the per-run corrections (`xamssim.corrections`: the simulation's truth, later a
calibration; used by amstrax's MC global version, see `corrections.py`). Truth file `<number>-truth.npz`: one row per simulated decay
(xams_events: true energy, position, S1 / S2 of the simulation), with the decay time for matching amstrax events;
in amstrax units (mm, ns), read with `load_truth` (converts older files in cm).

`context(run, calibration="truth")` gives an amstrax context with the simulation's own calibration: a check of the
waveform simulation (xams-sim's S8 notebook), not for the analysis.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import numpy as np

from .config import ROOT, ConfigError, Resolved, resolve

# $XAMSSIM_AMSTRAX_STORE, else the analysis' data folder next to the code (development checkout); a shared installation
# without it has no default (None): the export then asks for $XAMSSIM_AMSTRAX_STORE instead of writing into the software
_default_store = ROOT.parent / "measurements" / "strax_data"
STORE = (Path(os.environ["XAMSSIM_AMSTRAX_STORE"]).resolve() if os.environ.get("XAMSSIM_AMSTRAX_STORE")
         else _default_store.resolve() if _default_store.parent.is_dir() else None)
RAW = {"raw_records": "xams_raw_records", "raw_records_sipm": "xams_raw_records_sipm"}
EXPORT_FORMAT = 2              # 2: first chunk starts FIRST_MARGIN_NS before the first record
FIRST_MARGIN_NS = 1_000_000    # amstrax extends hits / peaks to the left: room before the first record (as in data)


def run_number(res: Resolved) -> str:
    n = res.run.get("run_number")
    if n is None:
        raise ConfigError(f"{res.run_path}: no run_number (900000-999999): needed to run it as a run for amstrax")
    from .listing import run_files
    for rid, files in run_files().items():
        for f in files:
            if Path(f).resolve() != Path(res.run_path).resolve() and resolve_number(f) == n:
                raise ConfigError(f"run_number {n} of {res.run_path} also in {f}")
    return f"{int(n):06d}"


def resolve_number(run_file) -> int | None:
    try:
        from .config import load_yaml
        return load_yaml(run_file).get("run_number")
    except Exception:
        return None


def truth_constants(res: Resolved, lifetime_us: float | None = None) -> dict:
    """The simulation's own values of what the analysis calibrates (for comparison, never applied by default)."""
    from . import driftmap
    from .waveforms import load_daq
    daq = load_daq(res)
    chans = {int(k): v for k, v in daq["channels"].items()}
    tau = lifetime_us or res.state.get("electron_lifetime_us")
    dm = np.load(driftmap.path(res))
    g = driftmap.geometry_numbers(res)
    x0 = int(np.argmin(np.abs(dm["x"])))
    t = dm["t_us"][x0, x0, :]
    zg, zc = g["z_gate"], g["z_cathode"]
    t_gate = float(np.interp(zg - 0.5, dm["z"], t))
    t_cath = float(np.interp(zc + 0.5, dm["z"], t))
    v = (zg - zc - 1.0) / max(t_cath - t_gate, 1e-6)                        # mm/µs between gate and cathode
    return dict(gain_to_pe_array=[1.0 / chans[c]["gain"] if c in chans else 0.0 for c in range(8)],
                elife=float(tau) * 1e3 if tau else None, electron_drift_velocity=v * 1e-4,      # ns, cm/ns
                drift_time_gate=t_gate * 1e3, drift_time_cathode=t_cath * 1e3,
                channel_map={k: list(v_) for k, v_ in daq["channel_map"].items()})


def condition(res: Resolved) -> str:
    """Key of what the true corrections of a run depend on (state and maps): a calibration measured on one run applies
    to all runs with the same condition (xamssim corrections)."""
    from .config import short_hash
    return short_hash({"state": {k: v for k, v in res.state.items() if k != "description"}, "maps": res.map_keys()})


def processing_config(processing) -> dict:
    """Processing settings of an analysis (its processing.json: base_config + event_config)."""
    if processing is None:
        return {}
    p = json.loads(Path(processing).read_text())
    cfg = {**p.get("base_config", {}), **p.get("event_config", {})}
    for k in ("gain_to_pe_array", "drift_time_gate", "drift_time_cathode", "channel_map"):
        cfg.pop(k, None)
    return cfg


def _ax_context(store: Path, cfg: dict | None = None, corrections_version=None):
    import amstrax
    import strax
    from immutabledict import immutabledict
    st = amstrax.contexts.xams(output_folder=str(store), init_rundb=False, corrections_version=corrections_version)
    for f in st.storage:                     # the run documents of simulated runs are files in the store
        if isinstance(f, strax.DataDirectory) and Path(f.path).resolve() == store.resolve():
            f.provide_run_metadata = True
    if cfg:
        cfg = dict(cfg)
        if "channel_map" in cfg:
            cfg["channel_map"] = immutabledict({k: tuple(v) for k, v in cfg["channel_map"].items()})
        st.set_config({k: v for k, v in cfg.items() if v is not None})
    return st


def export(run_path, lifetime_us: float | None = None, store: Path | None = None, log=print) -> str:
    """Copy the chain's raw records of a run under amstrax's keys into the store, with run document and truth file;
    returns the run id (the 6-digit run number)."""
    import strax

    from . import chain
    if store is None and STORE is None:
        raise ConfigError(f"XAMSSIM_AMSTRAX_STORE is not set and there is no measurements folder next to {ROOT}: set "
                          "XAMSSIM_AMSTRAX_STORE (setup_xamssim.sh does)")
    store = Path(store or STORE)
    store.mkdir(parents=True, exist_ok=True)
    res = resolve(run_path)
    rid = run_number(res)
    over = {"electron_lifetime_us": float(lifetime_us)} if lifetime_us else {}
    sim, sim_id = chain.context(run_path, **over)
    ax = _ax_context(store, {"channel_map": truth_constants(res, lifetime_us)["channel_map"]})
    sf = [s for s in ax.storage if isinstance(s, strax.DataDirectory) and Path(s.path).resolve() == store.resolve()][0]
    # amstrax's lineage does not see the content of the raw records: remember which simulated records were copied, and
    # remove all amstrax data of the run when they change (else records / peaks / events would be reused)
    src = {t: sim.key_for(sim_id, t).lineage_hash for t in RAW.values()}
    src["export_format"] = EXPORT_FORMAT
    tag = store / f"{rid}.xamssim.json"
    if not tag.exists() or json.loads(tag.read_text()).get("sources") != src:
        for d in store.glob(f"{rid}-*"):
            shutil.rmtree(d, ignore_errors=True) if d.is_dir() else d.unlink()
        tag.unlink(missing_ok=True)
    for ax_type, sim_type in RAW.items():
        if not sim.is_stored(sim_id, sim_type):
            raise RuntimeError(f"{sim_type} of {sim_id} not made: xamssim chain {run_path} --target raw_records")
        if ax.is_stored(rid, ax_type):
            continue
        key = ax.key_for(rid, ax_type)
        plugin = ax._get_plugins((ax_type,), rid)[ax_type]
        saver = sf.saver(key, plugin.metadata(rid, ax_type))
        n = 0
        t_first = _first_time(sim, sim_id)
        for i, c in enumerate(sim.get_iter(sim_id, sim_type, progress_bar=False)):
            start = max(0, min(c.start, t_first - FIRST_MARGIN_NS)) if i == 0 else c.start
            ch = strax.Chunk(start=start, end=c.end, data=c.data, data_type=ax_type, data_kind=ax_type,
                             dtype=c.data.dtype, run_id=rid, target_size_mb=c.target_size_mb)
            saver.save(chunk=ch, chunk_i=i)
            n += len(c.data)
            print(f"\r  {ax_type}: copying chunk {i + 1}, {n} records", end="", flush=True)
        saver.close()
        print("\r", end="")
        log(f"  {ax_type}: {n} records -> {store / str(key)}")
    _write_run_metadata(sf, res, rid, sim_id, sim, lifetime_us, log=log, data=[
        dict(type=t, host=_host(), location=str(store), protocol="FileSytemBackend") for t in RAW])
    _write_truth(store, res, rid, sim_id, sim)
    tag.write_text(json.dumps({"run_file": str(Path(run_path).resolve()), "sim_run_id": sim_id, "sources": src}))
    return rid


def _host() -> str:
    """Where the data are: stbc for the Nikhef batch file system, else the machine's name."""
    import socket
    h = socket.gethostname()
    return "stbc" if h.startswith(("stbc", "wn-")) or str(STORE or "").startswith("/data/xenon") else h


def _first_time(sim, sim_id) -> int:
    """Earliest record time over both raw types (the first chunk of each starts before it)."""
    return min(sim.get_metadata(sim_id, t)["chunks"][0]["first_time"] for t in RAW.values()
               if sim.get_metadata(sim_id, t)["chunks"] and sim.get_metadata(sim_id, t)["chunks"][0]["n"])


def _write_run_metadata(sf, res: Resolved, rid: str, sim_id: str, sim, lifetime_us, start_ns: int | None = None,
                        daq_extra: dict | None = None, data: list | None = None, log=print) -> None:
    """A run document for the simulated run, as the run database has it for data (start_ns: run start [ns], default
    just before the first record; daq_extra: more daq_config fields, e.g. those of the live data; data: the data
    locations, as data[] of a data run). Written as a file next to the data and, with a writer account, into
    run.runs_mc (xamssim.rundb)."""
    import datetime as dt
    from .waveforms import load_daq
    daq = load_daq(res)
    thr = [500] * 16
    for ch, c in daq["channels"].items():
        thr[int(ch)] = c["threshold"]
    md0 = sim.get_metadata(sim_id, RAW["raw_records"])
    t = lambda ns: dt.datetime.fromtimestamp(ns / 1e9, tz=dt.timezone.utc)   # noqa: E731
    pre = int(daq["digitizer"]["pre_trigger_samples"]) // 4                    # register 0x8038 in units of 4 samples
    doc = {
        "name": rid, "number": int(rid), "mode": f"simulation ({res.state_name})",
        "tags": ["simulation"] + [t_ for t_ in res.run.get("tags", []) if t_ != "simulation"],
        "start": t(start_ns if start_ns is not None else max(0, min(md0["start"], _first_time(sim, sim_id) - FIRST_MARGIN_NS))),
        "end": t(md0["end"]), "detectors": ["tpc"],
        "comments": [{"comment": f"xams-sim run {sim_id}: state {res.state_name}, source {res.source_name}, "
                                 f"{res.run['n_events']:.3g} decays, detector {res.detector} (xamssim show {sim_id})"}],
        "daq_config": {"name": f"simulated {daq['digitizer']['model']}", "thresholds": {"sim": thr},
                       "channel_map": daq["channel_map"],
                       "registers": [{"reg": "8038", "val": f"{pre:x}", "comment": "Pre-trigger (simulated)"}],
                       **(daq_extra or {})},
        "xamssim": {"run_name": sim_id, "run_file": str(Path(res.run_path).resolve()), "run_key": res.run_key(),
                    "made": dt.datetime.now(tz=dt.timezone.utc),       # when exported (the run's start is simulated time)
                    "state": res.state_name, "source": res.source_name, "source_position_mm": res.source.get("position_mm"),
                    "detector": res.detector, "n_events": res.run["n_events"], "seed": res.run["seed"],
                    "supersedes": res.run.get("supersedes"), "maps": res.map_keys(), "condition": condition(res),
                    # per-run corrections (xamssim.corrections): truth now, calibrated after a calibration on the
                    # reconstructed MC; amstrax reads them with an MC global version (MC1) and for_mc_run
                    "corrections": {"truth": truth_constants(res, lifetime_us)}},
        "data": data or [],
    }
    _keep_calibration(sf, rid, doc)
    sf.write_run_metadata(rid, doc)
    from . import rundb
    rundb.register(doc, log=log)


def _keep_calibration(sf, rid: str, doc: dict) -> None:
    """A run number is one fixed simulation (plan S10): writing the run document again (finishing a run, reprocessing)
    keeps its stored calibrations; a different simulation under an existing number is refused (a rerun gets a new
    number)."""
    from bson import json_util
    f = Path(sf.path) / f"{rid}-metadata.json"                      # the file itself: strax returns it flattened
    if not f.exists():
        return
    old = json.loads(f.read_text(), object_hook=json_util.object_hook)
    was, now = old.get("xamssim", {}).get("run_key"), doc["xamssim"]["run_key"]
    if was and was != now:
        raise ConfigError(f"run {rid} already exists as another simulation (run key {was}, now {now}): a rerun gets a "
                          "new run number (run_number in the run file, supersedes: the old one)")
    kept = {k: v for k, v in (old.get("xamssim", {}).get("corrections") or {}).items() if k != "truth"}
    doc["xamssim"]["corrections"].update(kept)


def _write_truth(store: Path, res: Resolved, rid: str, sim_id: str, sim) -> None:
    """One row per simulated decay (xams_events of the chain) with its time: the truth to match amstrax events to."""
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        e = sim.get_array(sim_id, "xams_events", progress_bar=False)
    np.savez_compressed(store / f"{rid}-truth.npz", events=_truth_units(e), units=np.array(TRUTH_UNITS),
                        note=np.array(f"xams-sim truth of run {rid} ({sim_id}): xams_events, one row per decay, in "
                                      "amstrax units (times and drift_time in ns, x, y, z in mm, data frame)"))


# the truth file in the units of amstrax (event_info), so that truth and reconstruction compare directly; the chain
# itself works in fuse's units (cm, drift time in µs). Files without `units` (before 2026-10-23) are in the chain's.
TRUTH_UNITS = "amstrax"
_TO_AMSTRAX = {"x": (10.0, "mm"), "y": (10.0, "mm"), "z": (10.0, "mm"), "drift_time": (1e3, "ns")}


def _truth_units(e: np.ndarray) -> np.ndarray:
    """xams_events with x, y, z in mm and drift_time in ns (titles updated)."""
    descr = []
    for title_name, fmt in e.dtype.descr:
        title, name = title_name if isinstance(title_name, tuple) else (None, title_name)
        if name in _TO_AMSTRAX and title:
            unit = _TO_AMSTRAX[name][1]
            title = title.replace("[cm]", f"[{unit}]").replace("[µs]", f"[{unit}]")
        descr.append(((title, name), fmt) if title else (name, fmt))
    out = np.zeros(len(e), dtype=np.dtype(descr))
    for name in e.dtype.names:
        out[name] = e[name] * _TO_AMSTRAX[name][0] if name in _TO_AMSTRAX else e[name]
    return out


def load_truth(path) -> np.ndarray:
    """The truth events of a simulated run (`<number>-truth.npz`) in amstrax units, also for older files (cm, µs)."""
    f = np.load(path)
    e = f["events"]
    return e if "units" in f.files and str(f["units"]) == TRUTH_UNITS else _truth_units(e)


def context(run_path, lifetime_us: float | None = None, processing=None, calibration: str = "truth"):
    """amstrax context for a simulated run and its run id. calibration="truth": the simulation's own gains, lifetime,
    drift times (a check of the waveform simulation); for the analysis use its own context with the run number."""
    if calibration != "truth":
        raise ValueError("only calibration='truth' here; the analysis processes the run with its own calibration")
    res = resolve(run_path)
    rid = export(run_path, lifetime_us, log=lambda *a: None)
    tc = truth_constants(res, lifetime_us)
    if tc["elife"] is None:
        raise ValueError(f"state {res.state_name} has no electron lifetime: give lifetime_us")
    return _ax_context(STORE, {**tc, **processing_config(processing)}), rid
