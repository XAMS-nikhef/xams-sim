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

Options as in ChunkInput: `path` is the run directory (`<data>/g4/<run>`), `file_name` the stem (`deposits`);
`entry_start` / `entry_stop` select events by their index in the run.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import strax
from fuse.plugins.micro_physics.input import ChunkInput, file_loader

from .. import g4io

export, __all__ = strax.exporter()

PROCESS_ALIASES = {"RadioactiveDecay": "RadioactiveDecayBase", "Radioactivation": "RadioactiveDecayBase"}


def deposits_frame(path, entry_start: int = 0, entry_stop: int | None = None) -> tuple[pd.DataFrame, int]:
    """Our deposits as the DataFrame fuse's `_awkwardify_df` takes (cm, names), sorted by event; and the event count."""
    h, dep, ev = g4io.read(path, mmap=True)
    n_events = len(ev)
    stop = n_events if entry_stop is None else min(int(entry_stop), n_events)
    sel = (dep["event"] >= int(entry_start)) & (dep["event"] < stop)
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

    def _load_csv_file(self):
        df, n_events = deposits_frame(self.file, self.entry_start, self.entry_stop)
        interactions = self._awkwardify_df(df)
        return interactions, n_events, 0, n_events


@export
class XamsG4Input(ChunkInput):
    """`geant4_interactions` from xamsg4 particle-mode output (<data>/g4/<run>/deposits.*)."""

    __version__ = "0.1.0"

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
        self.file_reader_iterator = self.file_reader.output_chunk()
