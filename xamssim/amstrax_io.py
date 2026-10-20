"""Simulated runs for amstrax (plan S8): the chain's raw records under amstrax's own keys, and a matching context.

    from xamssim import amstrax_io
    st, run_id = amstrax_io.context("runs/s8_cs137_sept_small.yaml")      # exports the raw records if needed
    e = st.get_array(run_id, "event_info")

amstrax reads `raw_records` / `raw_records_sipm` from a DataDirectory (`<data>/amstrax/`; its DAQReader is never run,
the keys follow its fixed lineage). There is no run database: the values amstrax would take from it or from the
correction files are given from the simulation: channel map (detector daq.yaml), single-PE gains (daq.yaml ->
gain_to_pe_array), electron lifetime (state or --lifetime-us), drift velocity and the drift times of gate and cathode
(the state's drift map). Everything else is amstrax's default, as for data.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .config import DATA, Resolved, resolve

STORE = DATA / "amstrax"
RAW = {"raw_records": "xams_raw_records", "raw_records_sipm": "xams_raw_records_sipm"}


def amstrax_config(res: Resolved, lifetime_us: float | None = None) -> dict:
    from . import driftmap
    from .waveforms import load_daq
    daq = load_daq(res)
    chans = {int(k): v for k, v in daq["channels"].items()}
    to_pe = [1.0 / chans[c]["gain"] if c in chans else 0.0 for c in range(8)]
    tau = lifetime_us or res.state.get("electron_lifetime_us")
    if not tau:
        raise ValueError(f"state {res.state_name} has no electron lifetime: give lifetime_us")
    # drift velocity and gate / cathode drift times from the drift map (centre of the TPC)
    dm = np.load(driftmap.path(res))
    g = driftmap.geometry_numbers(res)
    x0 = int(np.argmin(np.abs(dm["x"])))
    t = dm["t_us"][x0, x0, :]
    zg, zc = g["z_gate"], g["z_cathode"]
    t_gate = float(np.interp(zg - 0.5, dm["z"], t))
    t_cath = float(np.interp(zc + 0.5, dm["z"], t))
    v = (zg - zc - 1.0) / max(t_cath - t_gate, 1e-6)                        # mm/µs between gate and cathode
    return dict(channel_map={k: tuple(v_) for k, v_ in daq["channel_map"].items()},
                gain_to_pe_array=to_pe, elife=float(tau) * 1e3,
                electron_drift_velocity=v * 1e-4,                             # cm/ns
                drift_time_gate=t_gate * 1e3, drift_time_cathode=t_cath * 1e3)


def _new_context(cfg: dict):
    import amstrax
    from immutabledict import immutabledict
    STORE.mkdir(parents=True, exist_ok=True)
    st = amstrax.contexts.xams(output_folder=str(STORE), init_rundb=False)
    cfg = dict(cfg, channel_map=immutabledict(cfg["channel_map"]))
    st.set_config(cfg)
    return st


def processing_config(processing) -> dict:
    """Processing settings of an analysis (its processing.json: base_config + event_config, e.g.
    analysis_SR2026.2/config/processing.json), so that MC and data are processed alike. Gains and the gate /
    cathode drift times stay those of the simulation."""
    if processing is None:
        return {}
    p = json.loads(Path(processing).read_text())
    cfg = {**p.get("base_config", {}), **p.get("event_config", {})}
    for k in ("gain_to_pe_array", "drift_time_gate", "drift_time_cathode", "channel_map"):
        cfg.pop(k, None)
    return cfg


def export(run_path, lifetime_us: float | None = None, processing=None, log=print) -> tuple:
    """Copy the chain's raw records of a run under amstrax's keys; (amstrax context, run id). processing: an
    analysis' processing.json (classification, event windows, ...) applied on top of the simulation's values."""
    import strax

    from . import chain
    res = resolve(run_path)
    over = {"electron_lifetime_us": float(lifetime_us)} if lifetime_us else {}
    sim, run_id = chain.context(run_path, **over)
    ax = _new_context({**amstrax_config(res, lifetime_us), **processing_config(processing)})
    sf = [s for s in ax.storage if isinstance(s, strax.DataDirectory) and Path(s.path).resolve() == STORE.resolve()][0]
    # amstrax's lineage does not see the content of the raw records: remember which simulated records were copied,
    # and remove all amstrax data of the run when they change (else records / peaks / events would be reused)
    src = {t: sim.key_for(run_id, t).lineage_hash for t in RAW.values()}
    tag = STORE / f"{run_id}.xamssim.json"
    if not tag.exists() or json.loads(tag.read_text()) != src:
        import shutil
        for d in STORE.glob(f"{run_id}-*"):
            shutil.rmtree(d, ignore_errors=True)
        tag.unlink(missing_ok=True)
    for ax_type, sim_type in RAW.items():
        if not sim.is_stored(run_id, sim_type):
            raise RuntimeError(f"{sim_type} of {run_id} not made: xamssim chain {run_path} --target raw_records")
        key = ax.key_for(run_id, ax_type)
        if ax.is_stored(run_id, ax_type):
            continue
        plugin = ax._get_plugins((ax_type,), run_id)[ax_type]
        md = plugin.metadata(run_id, ax_type)
        saver = sf.saver(key, md)
        n = 0
        for i, c in enumerate(sim.get_iter(run_id, sim_type, progress_bar=False)):
            ch = strax.Chunk(start=c.start, end=c.end, data=c.data, data_type=ax_type, data_kind=ax_type,
                             dtype=c.data.dtype, run_id=run_id, target_size_mb=c.target_size_mb)
            saver.save(chunk=ch, chunk_i=i)
            n += len(c.data)
        saver.close()
        log(f"  {ax_type}: {n} records -> {STORE / str(key)}")
    tag.write_text(json.dumps(src))
    return ax, run_id


def context(run_path, lifetime_us: float | None = None, processing=None):
    """amstrax context for a simulated run (raw records exported if needed) and its run id; processing: an
    analysis' processing.json (see processing_config)."""
    return export(run_path, lifetime_us, processing, log=lambda *a: None)
