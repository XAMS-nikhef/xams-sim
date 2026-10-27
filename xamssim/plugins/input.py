"""Input plugin: xamsg4 particle-mode output -> fuse `geant4_interactions` (plan S3).

fuse's ChunkInput reads XENONnT ROOT / CSV files. This plugin keeps everything ChunkInput does after loading (removing
events without energy, time ordering, placing events on a timeline at `source_rate`, `cut_delayed`, dynamic chunking)
and only replaces the loading: our binary deposits (`xamssim.g4io`) are turned into the same awkward array the CSV
loader builds.

Translation:
    position   mm -> cm (x, y, z and the primary vertex x_pri, y_pri, z_pri from the event records)
    codes      particle / process codes -> names from the header (`type`, `parenttype`, `creaproc`, `edproc`)
    process    'RadioactiveDecay' / 'Radioactivation' (Geant4 11 names) -> 'RadioactiveDecayBase', the name fuse's
               lineage clustering looks for (decay products)
    track ids  kept int32 here (fuse's reshape only takes int32/64), stored as int16 by fuse; beyond int16: error
    time       ns (each event starts at the decay: xamsg4 resets the clock of decay products)

Lineage: `g4_output_hash` (content of the Geant4 output, from its header) is a tracked option.
Pre-selection: only decays with a deposit inside the field-cage radius (`preselect_r_max_cm`) go to the clustering.

Memory: fuse's loader builds all deposits of a run at once (pandas + awkward with string columns: > 28 GB for 10^7
Na-22 decays). XamsG4Loader.output_chunk does the same steps (`file_loader.output_chunk`) with per-event numbers only
(event selection, time sorting, event times, chunk bounds) and reads and converts the deposits chunk by chunk from the
memory-mapped file, so memory no longer grows with the run size. The output is bit-identical to fuse's: the same single
random draw (event times, in the same order), the same deposit order within a chunk (events ascending, deposits by time
within the event, then a stable sort by time), the same casts (tests/test_chain.py compares both loaders).
Options as in ChunkInput: `path` is the run directory (`<data>/g4/<run>`), `file_name` the stem (`deposits`);
`entry_start` / `entry_stop` select events by their index in the run.
"""
from __future__ import annotations

import numba
import numpy as np
import pandas as pd
import strax
import straxen
from fuse.common import stable_argsort, stable_sort
from fuse.plugins.micro_physics.input import ChunkInput, file_loader

from .. import g4io

export, __all__ = strax.exporter()

PROCESS_ALIASES = {"RadioactiveDecay": "RadioactiveDecayBase", "Radioactivation": "RadioactiveDecayBase"}
# Chunk ceiling: fuse starts a new chunk only at a gap > separation_scale (0.1 s) between decays. At a high source rate
# (e.g. 1000 Hz with 1.7 M decays that deposit energy) such gaps never occur and the whole run becomes one chunk
# (990018: 95 M deposits, > 16 GB). A chunk with more deposits than MAX_CHUNK_DEPOSITS is therefore split further at
# gaps of at least MIN_SPLIT_GAP_NS between decays (far longer than a decay with its drift; events are never cut).
# Runs whose chunks stay below the ceiling (every run at the default 100 Hz) are chunked exactly as by fuse.
MAX_CHUNK_DEPOSITS = 2_000_000
MIN_SPLIT_GAP_NS = 1_000_000


@numba.njit(cache=True)
def _dynamic_chunking_sorted(data_sorted, scale, n_min):
    """fuse.common.dynamic_chunking for data that are already sorted (the deposit times here): the same chunk ids,
    without fuse's Python list of one entry per deposit and its two argsorts (95 M deposits: GBs)."""
    out = np.zeros(len(data_sorted), np.int64)
    c = 0
    n_cluster = 0
    for i in range(1, len(data_sorted)):
        value = data_sorted[i] - data_sorted[i - 1]
        if value <= scale:
            n_cluster += 1
        elif n_cluster + 1 < n_min:
            n_cluster += 1
        else:
            c += 1
            n_cluster = 0
        out[i] = c
    return out


def split_large_chunks(t_sorted, starts, max_n=MAX_CHUNK_DEPOSITS, min_gap=MIN_SPLIT_GAP_NS):
    """Chunk start indices (into the sorted deposit times) with every chunk of more than max_n deposits split at
    gaps > min_gap, each piece at least max_n deposits long (the last one may be shorter)."""
    starts = np.asarray(starts, dtype=np.int64)
    ends = np.append(starts[1:], len(t_sorted))
    out = []
    for s, e in zip(starts, ends):
        out.append(s)
        if e - s <= max_n:
            continue
        cand = s + 1 + np.nonzero(np.diff(t_sorted[s:e]) > min_gap)[0]     # a new chunk may start here
        last = s
        for c in cand:
            if c - last >= max_n:
                out.append(c)
                last = c
    return np.asarray(out, dtype=np.int64)


def deposits_frame(path, entry_start: int = 0, entry_stop: int | None = None,
                   r_max_mm: float | None = None) -> tuple[pd.DataFrame, int]:
    """Our deposits as the DataFrame fuse's `_awkwardify_df` takes (cm, names), sorted by event; and the event count.
    r_max_mm: keep only events with at least one deposit at r < r_max_mm (whole events: all their deposits)."""
    h, dep, ev = g4io.read(path, mmap=True)
    n_events = len(ev)
    stop = n_events if entry_stop is None else min(int(entry_stop), n_events)
    sel = (dep["event"] >= int(entry_start)) & (dep["event"] < stop)
    if r_max_mm is not None:
        inner = np.hypot(dep["x"], dep["y"]) < r_max_mm
        keep = np.zeros(n_events, bool)
        keep[np.asarray(dep["event"][inner])] = True
        sel &= keep[np.asarray(dep["event"])]
    d = np.asarray(dep[sel])
    d = d[np.argsort(d["event"], kind="stable")]
    for f in ("track", "parent"):
        if len(d) and d[f].max() > np.iinfo(np.int16).max:
            raise ValueError(f"{path}: track id {d[f].max()} does not fit fuse's int16 '{f}' field")
    particle = np.array(h["codes"]["particle"], dtype=object)
    process = np.array([PROCESS_ALIASES.get(p, p) for p in h["codes"]["process"]], dtype=object)
    # primary vertex per deposit from the event records (event index == event id in our files)
    if not np.array_equal(ev["event"], np.arange(n_events)):
        raise ValueError(f"{path}: event records are not numbered 0..N-1")
    pri = ev[d["event"]]
    df = pd.DataFrame({
        "x": d["x"] / 10.0, "y": d["y"] / 10.0, "z": d["z"] / 10.0,
        "x_pri": pri["x_pri"] / 10.0, "y_pri": pri["y_pri"] / 10.0, "z_pri": pri["z_pri"] / 10.0,
        "t": d["t"], "ed": d["edep"],
        "type": particle[d["particle"]], "trackid": d["track"].astype(np.int32),
        "parenttype": particle[d["parent_particle"]], "parentid": d["parent"].astype(np.int32),
        "creaproc": process[d["creaproc"]], "edproc": process[d["edproc"]],
        "eventid": d["event"],
    })
    return df, n_events


class XamsG4Loader(file_loader):
    """fuse's file loader with our binary format in place of CSV."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_type = "csv"            # routes output_chunk() to _load_csv_file (replaced below)

    r_max_mm = None

    def _load_csv_file(self):
        """fuse's path: all deposits at once (file_loader.output_chunk). Kept as the reference of the tests."""
        df, n_events = deposits_frame(self.file, self.entry_start, self.entry_stop, self.r_max_mm)
        interactions = self._awkwardify_df(df)
        return interactions, n_events, 0, n_events

    def output_chunk(self):
        """file_loader.output_chunk with the deposits read per chunk (module doc). Yields the same chunks."""
        if self.cut_nr_only:
            raise NotImplementedError("nr_only: use fuse's loader (file_loader.output_chunk)")
        h, dep, ev = g4io.read(self.file, mmap=True)
        n_events = len(ev)
        if not np.array_equal(ev["event"], np.arange(n_events)):
            raise ValueError(f"{self.file}: event records are not numbered 0..N-1")
        start = int(self.entry_start or 0)
        stop = n_events if self.entry_stop is None else min(int(self.entry_stop), n_events)
        event = np.asarray(dep["event"])
        sel = (event >= start) & (event < stop)
        if self.r_max_mm is not None:                       # deposits_frame: whole events with a deposit inside r_max
            inner = np.hypot(dep["x"], dep["y"]) < self.r_max_mm
            keep = np.zeros(n_events, bool)
            keep[event[inner]] = True
            sel &= keep[event]
            del inner, keep
        t = np.asarray(dep["t"], dtype=np.float64)
        edep = np.asarray(dep["edep"])
        # events with deposits and with energy (fuse: ak.num > 0 and ak.sum(ed) > 0)
        e_sum = np.bincount(event[sel], weights=edep[sel].astype(np.float64), minlength=n_events)
        ev_kept = np.nonzero(e_sum > 0)[0]
        del e_sum
        is_kept = np.zeros(n_events, bool)
        is_kept[ev_kept] = True
        sel &= is_kept[event]                                  # (np.isin over all deposits: sort-based, GBs)
        del is_kept
        idx = np.nonzero(sel)[0]
        del sel
        # deposits by event, by time within the event (stable: file order on ties) = fuse's flatten order
        idx = idx[np.lexsort((t[idx], event[idx]))]
        ev_of = event[idx]
        first = np.searchsorted(ev_of, ev_kept, "left")
        last = np.searchsorted(ev_of, ev_kept, "right")
        dt = t[idx]
        if self.event_rate > 0 and self.subtract_first_interaction_time:
            dt = dt - np.repeat(dt[first], last - first)
        if self.event_rate > 0:
            if self.fixed_event_spacing:
                ev_t = (np.linspace(start=0, stop=len(ev_kept) / self.event_rate, num=len(ev_kept), endpoint=False)
                        + 1e9).astype(np.int64)
            else:
                # fuse: uniform over [start, stop) of _load_csv_file, which returns 0 and the event count
                ev_t = self.rng.uniform(low=0 / self.event_rate, high=n_events / self.event_rate,
                                        size=len(ev_kept)).astype(np.int64)
                ev_t = stable_sort(ev_t)
            time = dt + np.repeat(ev_t, last - first)
        elif self.event_rate == 0:
            time = dt.copy()
        else:
            raise ValueError("Source rate cannot be negative!")
        del t, edep
        ok = dt < self.cut_delayed                            # fuse: interactions[interactions["t"] < cut_delayed]
        if not ok.all():
            idx, dt, time, ev_of = idx[ok], dt[ok], time[ok], ev_of[ok]
            first = np.searchsorted(ev_of, ev_kept, "left")
            last = np.searchsorted(ev_of, ev_kept, "right")
        del ok
        # chunk bounds as fuse: from all deposit times, sorted (dynamic_chunking on sorted times: chunk ids ascend)
        interaction_time = stable_sort(time).astype(np.int64)
        chunk_idx = _dynamic_chunking_sorted(interaction_time, float(self.separation_scale), float(self.n_interactions_per_chunk))
        _, i0 = np.unique(chunk_idx, return_index=True)
        i0 = split_large_chunks(interaction_time, i0)                    # ceiling (module doc); no-op for normal runs
        unique_chunk_index_values = np.arange(len(i0))
        i1 = np.append(i0[1:], len(chunk_idx)) - 1
        chunk_start, chunk_end = interaction_time[i0], interaction_time[i1]
        del interaction_time, chunk_idx
        if (len(chunk_start) > 1) & (len(chunk_end) > 1):
            gap_length = chunk_start[1:] - chunk_end[:-1]
            gap_length = np.append(gap_length, gap_length[-1] + self.last_chunk_length)
            chunk_bounds = chunk_end + np.int64(self.chunk_delay_fraction * gap_length)
            self.chunk_bounds = np.append(chunk_start[0] - self.first_chunk_left, chunk_bounds)
        else:
            self.log.warning("Only one Chunk created! Only a few events simulated? If no, your chunking parameters "
                             "might not be optimal. Try to decrease the source_rate or decrease the "
                             "n_interactions_per_chunk.")
            self.chunk_bounds = [chunk_start[0] - self.first_chunk_left, chunk_end[0] + self.last_chunk_length]
        # per event: first and last deposit time (fuse: ak.min / ak.max of the time, as int64)
        has = last > first
        ev_kept, first, last = ev_kept[has], first[has], last[has]
        times_min = np.minimum.reduceat(time, first).astype(np.int64)
        times_max = np.maximum.reduceat(time, first).astype(np.int64)
        particle = np.array(h["codes"]["particle"], dtype=object)
        process = np.array([PROCESS_ALIASES.get(p, p) for p in h["codes"]["process"]], dtype=object)
        source_done = False
        self.log.info(f"Simulating data in {len(unique_chunk_index_values)} chunks.")
        for c_ix, chunk_left, chunk_right in zip(unique_chunk_index_values, self.chunk_bounds[:-1],
                                                 self.chunk_bounds[1:]):
            m = np.nonzero((times_min <= chunk_right) & (times_max >= chunk_left))[0]
            if len(m) == 0:
                current_chunk = np.empty(0, dtype=self.dtype)
            else:
                rows = np.concatenate([np.arange(a, b) for a, b in zip(first[m], last[m])])
                current_chunk = self._records(dep, ev, idx[rows], dt[rows], time[rows], particle, process)
            select_times = current_chunk["time"] >= chunk_left
            select_times &= current_chunk["time"] <= chunk_right
            current_chunk = current_chunk[select_times]
            current_chunk = current_chunk[stable_argsort(current_chunk["time"])]
            if c_ix == unique_chunk_index_values[-1]:
                source_done = True
            yield current_chunk, chunk_left, chunk_right, source_done

    def _records(self, dep, ev, rows, dt, time, particle, process):
        """The deposits `rows` (file indices, fuse order) as fuse's numpy chunk (full_array_to_numpy casts)."""
        d = np.asarray(dep[rows])
        for f in ("track", "parent"):
            if len(d) and d[f].max() > np.iinfo(np.int16).max:
                raise ValueError(f"{self.file}: track id {d[f].max()} does not fit fuse's int16 '{f}' field")
        pri = ev[d["event"]]
        out = np.zeros(len(d), dtype=self.dtype)
        for f in ("x", "y", "z"):
            out[f] = d[f] / 10.0
            out[f"{f}_pri"] = pri[f"{f}_pri"] / 10.0
        out["t"], out["ed"], out["time"] = dt, d["edep"], time
        out["type"], out["parenttype"] = particle[d["particle"]], particle[d["parent_particle"]]
        out["trackid"], out["parentid"] = d["track"], d["parent"]
        out["creaproc"], out["edproc"] = process[d["creaproc"]], process[d["edproc"]]
        out["eventid"] = d["event"]
        return out


@export
class XamsG4Input(ChunkInput):
    """`geant4_interactions` from xamsg4 particle-mode output (<data>/g4/<run>/deposits.*)."""

    __version__ = "0.3.0"

    preselect_r_max_cm = straxen.URLConfig(
        type=(int, float), help="keep only decays with a deposit inside this radius (the field cage: nothing outside "
                                "it reaches a volume), so clustering skips the rest [cm]",
    )
    g4_output_hash = straxen.URLConfig(
        type=str, help="content hash of the Geant4 output (xamssim.g4io.output_hash): tracked, so a new Geant4 run "
                       "of the same run file gets new strax data (fuse does not track path / file_name)",
    )

    def setup(self):
        super(ChunkInput, self).setup()   # FuseBasePlugin: rng, logging
        self.file_reader = XamsG4Loader(
            self.path,
            self.file_name,
            self.rng,
            separation_scale=self.separation_scale,
            event_rate=self.source_rate,
            subtract_first_interaction_time=self.subtract_first_interaction_time,
            cut_delayed=self.cut_delayed,
            first_chunk_left=self.first_chunk_left,
            last_chunk_length=self.last_chunk_length,
            n_interactions_per_chunk=self.n_interactions_per_chunk,
            arg_debug=self.debug,
            outer_cylinder=None,
            entry_start=self.entry_start,
            entry_stop=self.entry_stop,
            cut_by_eventid=self.cut_by_eventid,
            cut_nr_only=self.nr_only,
            maximal_er_energy=self.maximal_er_energy,
            fixed_event_spacing=self.fixed_event_spacing,
            log=self.log,
        )
        self.file_reader.r_max_mm = float(self.preselect_r_max_cm) * 10.0
        self.file_reader_iterator = self.file_reader.output_chunk()
