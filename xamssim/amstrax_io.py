"""Simulated runs as runs for amstrax and the analysis (plan S8).

    xamssim amstrax <run file>        # after: xamssim chain <run file> --target raw_records

copies the chain's raw records of a run with a `run_number` (900000-999999) into the analysis' data folder
(STORE: `<XAMS>/measurements/strax_data`, or $XAMSSIM_AMSTRAX_STORE) under amstrax's own keys (`raw_records`,
`raw_records_sipm`), with a run document and a truth file, so that the run is addressed by its number like a data run:
the analysis' context, `EventDisplay(900001, ...)`, the step scripts. amstrax processes it on request (records, peaks,
events, ...), with the calibration the analysis gives it (correction files of amstrax_files, gains, processing.json),
never with the simulation's own values.

Run document (`<number>-metadata.json`, as the run database has it for data): number, mode, start / end, tags, comment,
the DAQ config (thresholds, channel map, pre-trigger register), and a section `xamssim` with the run file, run key and the
truth constants of the simulation (gains, lifetime, drift velocity, gate / cathode drift times, state, source, detector):
for comparison with what the analysis finds, not applied. Truth file `<number>-truth.npz`: one row per simulated decay
(xams_events: true energy, position, S1 / S2 of the simulation), with the decay time for matching amstrax events.

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

STORE = Path(os.environ.get("XAMSSIM_AMSTRAX_STORE", ROOT.parent / "measurements" / "strax_data")).resolve()
RAW = {"raw_records": "xams_raw_records", "raw_records_sipm": "xams_raw_records_sipm"}


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
        for i, c in enumerate(sim.get_iter(sim_id, sim_type, progress_bar=False)):
            ch = strax.Chunk(start=c.start, end=c.end, data=c.data, data_type=ax_type, data_kind=ax_type,
                             dtype=c.data.dtype, run_id=rid, target_size_mb=c.target_size_mb)
            saver.save(chunk=ch, chunk_i=i)
            n += len(c.data)
            print(f"\r  {ax_type}: copying chunk {i + 1}, {n} records", end="", flush=True)
        saver.close()
        print("\r", end="")
        log(f"  {ax_type}: {n} records -> {store / str(key)}")
    _write_run_metadata(sf, res, rid, sim_id, sim, lifetime_us)
    _write_truth(store, res, rid, sim_id, sim)
    tag.write_text(json.dumps({"run_file": str(Path(run_path).resolve()), "sim_run_id": sim_id, "sources": src}))
    return rid


def _write_run_metadata(sf, res: Resolved, rid: str, sim_id: str, sim, lifetime_us) -> None:
    """A run document for the simulated run, as the run database has it for data."""
    import datetime as dt
    from .waveforms import load_daq
    daq = load_daq(res)
    thr = [500] * 16
    for ch, c in daq["channels"].items():
        thr[int(ch)] = c["threshold"]
    md0 = sim.get_metadata(sim_id, RAW["raw_records"])
    t = lambda ns: dt.datetime.fromtimestamp(ns / 1e9, tz=dt.timezone.utc)   # noqa: E731
    pre = int(daq["digitizer"]["pre_trigger_samples"]) // 4                    # register 0x8038 in units of 4 samples
    sf.write_run_metadata(rid, {
        "name": rid, "number": int(rid), "mode": f"simulation ({res.state_name})", "tags": ["simulation"],
        "start": t(md0["start"]), "end": t(md0["end"]), "detectors": ["tpc"],
        "comments": [{"comment": f"xams-sim run {sim_id}: state {res.state_name}, source {res.source_name}, "
                                 f"{res.run['n_events']:.3g} decays, detector {res.detector} (xamssim show {sim_id})"}],
        "daq_config": {"name": f"simulated {daq['digitizer']['model']}", "thresholds": {"sim": thr},
                       "channel_map": daq["channel_map"],
                       "registers": [{"reg": "8038", "val": f"{pre:x}", "comment": "Pre-trigger (simulated)"}]},
        "xamssim": {"run_name": sim_id, "run_file": str(Path(res.run_path).resolve()), "run_key": res.run_key(),
                    "state": res.state_name, "source": res.source_name, "source_position_mm": res.source.get("position_mm"),
                    "detector": res.detector, "n_events": res.run["n_events"], "seed": res.run["seed"],
                    "truth": truth_constants(res, lifetime_us)},
    })


def _write_truth(store: Path, res: Resolved, rid: str, sim_id: str, sim) -> None:
    """One row per simulated decay (xams_events of the chain) with its time: the truth to match amstrax events to."""
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        e = sim.get_array(sim_id, "xams_events", progress_bar=False)
    np.savez_compressed(store / f"{rid}-truth.npz", events=e,
                        note=np.array(f"xams-sim truth of run {rid} ({sim_id}): xams_events, one row per decay "
                                      f"(times in ns as in the raw records; x, y, z in cm)"))


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
