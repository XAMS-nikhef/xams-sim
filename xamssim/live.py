"""Simulated runs as redax live data (plan S9, point 6).

    xamssim live <run file>            # after: xamssim chain <run file> --target raw_records

writes the chain's simulated raw records of a run with a `run_number` as the DAQ (redax) writes a run, so that amstrax
makes raw_records from them with its DAQReader exactly as for data (`amstrax.contexts.context_for_daq_reader`):

    <live>/<run>/000000, 000000_post, 000001_pre, 000001, ...   one folder per chunk: 10 s of data, then 0.5 s of
                                                                overlap written to both _post and the next _pre
    <live>/<run>/THE_END                                         the run is complete
    each folder: one lz4 file per readout thread (strax raw_record dtype, 110 samples), times relative to the run start,
    PMT and SiPM channels together (the DAQReader splits them by the channel map)

as found in the live data of run 7719 (STBC /data/xenon/xams_v2/live_data/007719). The run document (`<run>-metadata.json`
in the store, as `xamssim amstrax` writes it) gets the DAQ fields the DAQReader needs (processing_threads,
strax_output_path, chunk length / overlap, payload, compressor) and the truth file goes next to it. No amstrax needed.

<live> is $XAMSSIM_LIVE, else `live_mc` next to the store; it must be called `live_mc`: never the DAQ's `live_data`,
which the copy / delete scripts and the data auto-processing watch.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np

from .config import ConfigError, resolve

THREAD = "xams-CELSIUS-J5010_reader_0"       # the reader on xams (thread name in the live data of run 7719)
FILE_ID = "000000000000000"                 # redax appends a thread id; any number
CHUNK_NS, OVERLAP_NS = 10_000_000_000, 500_000_000
RECORD_SAMPLES = 110
COMPRESSOR = "lz4"
LIVE_NAME = "live_mc"


def live_root(store: Path) -> Path:
    root = Path(os.environ["XAMSSIM_LIVE"]).resolve() if os.environ.get("XAMSSIM_LIVE") else store.parent / LIVE_NAME
    if root.name != LIVE_NAME:
        raise ConfigError(f"simulated live data go only into a folder called '{LIVE_NAME}', not {root} (the DAQ's "
                          "live_data is watched by the copy / delete scripts and the data auto-processing)")
    return root


def chunk_folders(rel: np.ndarray) -> dict:
    """time since run start [ns] -> {folder name: index array}: central chunks and the overlaps (_post = next _pre)."""
    period = CHUNK_NS + OVERLAP_NS
    i = rel // period
    central = (rel - i * period) < CHUNK_NS
    n = int(i.max()) + 1 if len(rel) else 1
    out = {}
    for k in range(n):
        out[f"{k:06d}"] = np.flatnonzero((i == k) & central)
        if k + 1 < n:
            post = np.flatnonzero((i == k) & ~central)
            out[f"{k:06d}_post"] = post
            out[f"{k + 1:06d}_pre"] = post
    return out


def write(run_path, lifetime_us: float | None = None, store: Path | None = None, log=print) -> str:
    """Write the simulated raw records of a run as live data, with run document and truth file; returns the run id."""
    import strax

    from . import amstrax_io, chain
    if store is None and amstrax_io.STORE is None:
        raise ConfigError("XAMSSIM_AMSTRAX_STORE is not set (setup_xamssim.sh does)")
    store = Path(store or amstrax_io.STORE)
    store.mkdir(parents=True, exist_ok=True)
    live = live_root(store)
    res = resolve(run_path)
    rid = amstrax_io.run_number(res)
    over = {"electron_lifetime_us": float(lifetime_us)} if lifetime_us else {}
    sim, sim_id = chain.context(run_path, **over)
    for t in amstrax_io.RAW.values():
        if not sim.is_stored(sim_id, t):
            raise RuntimeError(f"{t} of {sim_id} not made: xamssim chain {run_path} --target raw_records")
    r = np.concatenate([sim.get_array(sim_id, t, progress_bar=False) for t in amstrax_io.RAW.values()])
    r = r[np.argsort(r["time"], kind="stable")]
    # run start: before the first record, on a whole second (amstrax's DAQReader adds only the whole seconds of the
    # run start to the live-data times), so that amstrax's times equal the simulation's (truth file)
    t0 = max(0, int(r["time"][0]) - amstrax_io.FIRST_MARGIN_NS) // 1_000_000_000 * 1_000_000_000 if len(r) else 0
    r["time"] -= t0
    out = live / rid
    if out.exists():                                     # simulated live data of an earlier export of this run
        shutil.rmtree(out)
    out.mkdir(parents=True)
    folders = chunk_folders(r["time"])
    for name, idx in folders.items():
        (out / name).mkdir()
        strax.save_file(str(out / name / f"{THREAD}_{FILE_ID}"), r[idx], compressor=COMPRESSOR)
    (out / "THE_END").mkdir()
    (out / "THE_END" / f"{THREAD}_{FILE_ID}").write_text("...my only friend\n")
    n_central = sum(1 for k in folders if "_" not in k)
    log(f"  live data: {len(r)} records in {n_central} chunks -> {out}")
    sf = strax.DataDirectory(str(store), provide_run_metadata=True)
    amstrax_io._write_run_metadata(sf, res, rid, sim_id, sim, lifetime_us, start_ns=t0, daq_extra={
        "processing_threads": {THREAD: 1}, "strax_output_path": str(live),
        "strax_fragment_payload_bytes": 2 * RECORD_SAMPLES, "strax_chunk_length": CHUNK_NS / 1e9,
        "strax_chunk_overlap": OVERLAP_NS / 1e9, "compressor": COMPRESSOR})
    amstrax_io._write_truth(store, res, rid, sim_id, sim)
    return rid
