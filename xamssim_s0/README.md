# S0 — fuse read-through and decisions (xams-sim plan)

Step S0 of `docs/xams_sim_plan.md`, done 2026-10-18 on the Mac in a throwaway conda environment `fuse-s0`
(`conda env remove -n fuse-s0` when no longer needed). fuse was cloned read-only (not kept in this repository).

## Environment: one stack works

| Package | Version | Note |
|---|---|---|
| Python | 3.12.15 | same as the new STBC production stack (py312 / strax 2.2.3) |
| strax | 2.2.3 | pinned (constraint file) |
| straxen | 4.1.1 | pulled in by fuse (needs ≥ 2.2.3) |
| xenon-fuse | 1.6.3 (git `04390c1`, 1.6.3-2) | `pip install xenon-fuse` |
| nestpy | **2.0.6** | **fuse 1.6.3 fails with nestpy 2.1.x** (`nestpy.VDetector` removed) → pin `nestpy<2.1` |
| amstrax, amstrax_files | master `e2e1e56` (2.2.0) | local clones, installed as copies; strax-2 compatible since PR #337 |

All five import together. utilix warns that `~/.xenon_config` is missing — harmless: nothing in the micro-physics
chain needs XENON database access once the settings below are given.

## What fuse contains (strax plugins)

- **micro-physics**: `ChunkInput` (Geant4 ROOT or CSV; neither used for XAMS production, see decision 3) → clustering, either `FindCluster` + `MergeCluster`
  (time windows + DBSCAN) or `LineageClustering` + `MergeLineage` (per particle track) → `VolumeProperties`,
  `VolumeSelection`, `DefaultSimulation` (region of interest) → `ElectricField` (field map in r, z) → `NestYields` →
  `MicroPhysicsSummary`.
- **detector physics**: electron drift, propagation to the surface, extraction, secondary scintillation (S2 photons),
  S1 photon hits / propagation, S2 photon propagation; **delayed electrons** (photo-ionization, drift, extraction, S2)
  — relevant for the delayed-electron paper.
- **PMT and DAQ**: afterpulses, photon summary, pulse windows, PMT response and DAQ → `raw_records`.
- **truth information** plugins (cluster / peak / event truth).

Full list of settings with defaults: `fuse_settings_1.6.3.txt` (made by `list_configs.py`; lines marked `XEN` have a
default that loads from XENON resources / xedocs). Per plugin, every XENON default is a normal setting — nothing found
that cannot be overridden. Hard-coded assumptions are settings too (`n_tpc_pmts`, `sample_duration`, digitizer bits /
range, gains). The S1 / S2 / PMT stages need many XAMS values and maps in fuse's formats (pattern maps, gains).

## Offline test with XAMS settings (`micro_test.py`)

Synthetic Cs-137-like events (CSV, mm — fine for a handful of test events, not for productions): a 662 keV photo-absorption, a Compton + photo-absorption pair, a gamma-X pair
(one site in the drift region, one below the cathode) and a deposit in the gas; our COMSOL field map for CM-B (−50 V
margin, `cmb50`) converted to straxen's map format (r, z in cm, |E| in V/cm); XAMS volumes; default NEST.

```bash
conda activate fuse-s0
python xamssim_s0/micro_test.py <work dir> lineage     # or: dbscan
```

XAMS settings used (cm): drift region gate 0 → cathode −5.18, r < 3.1; below the cathode down to the bottom PMT window
−6.41; gas 0.4 → 2.25; LXe density 2.86, gas 0.018 g/cm³; `tag_cluster_by = energy`; NEST ER/NR parameters −1
(defaults), width parameters `{}`.

Results:

| | DBSCAN clustering (fuse default settings) | lineage clustering |
|---|---|---|
| clusters (36 steps, 4 events) | 36 (every step its own cluster: 5 µm / 10 ns scale) | **6** (one per particle track) |
| 662 keV event | 6 × 110 keV → ≈ 33 000 photons in total (NEST yields per small cluster) | 1 × 662 keV → 21 600 photons, 27 100 electrons (NEST mean 21 950 / 26 880 at 101 V/cm) |
| gamma-X event | — | 300 keV in volume 1 (S2) + 362 keV in volume 2 (below the cathode: `create_S2 = False`, 0 electrons, 192 V/cm reverse field) |
| gas event | dropped (not in the region of interest) | dropped |

The field from the COMSOL map is 98–101 V/cm in the drift region; yields agree with standalone NEST within the
fluctuations, with the expected photon / electron anticorrelation.

## Decisions (S0 check)

1. **fuse as a library** for the micro-physics: `LineageClustering` + `MergeLineage`, `VolumeProperties`,
   `VolumeSelection`, `DefaultSimulation`, `ElectricField`, `NestYields`, `MicroPhysicsSummary` — all run offline with
   XAMS settings, no code changes.
2. **Lineage clustering, not DBSCAN.** With fuse's DBSCAN defaults a 662 keV electron track is split into many tiny
   clusters and NEST gives ~50 % more light (and less charge) than for the whole deposit; lineage clustering keeps one
   cluster per particle track — the right choice for photopeak studies. (DBSCAN with a larger distance would also
   merge, but lineage is physically motivated and is fuse's newer method.)
3. **Input**: our own input plugin that provides `geant4_interactions` with fuse's table: x, y, z [cm], t [ns],
   ed [keV], type, trackid, parenttype, parentid, creaproc, edproc (Geant4 process names), eventid, x_pri, y_pri, z_pri.
   This fixes the Geant4 particle-mode output (S2 of the plan): **binary records + JSON header**, particle / process
   names as integer codes with the lookup table in the header, translated by our input plugin. **CSV only for small
   tests** (as here): text is 3–5× larger than binary, slow to write and parse, rounds numbers, carries no metadata,
   and fuse's CSV reader loads the whole file into memory (a Cs-137 production of 10⁶ events is ~3 × 10⁸ steps:
   tens of GB as CSV). No ROOT. Parquet / HDF5 only if compression or partial reading is needed later.
4. **Environment** for S1 (`xamssim`): Python 3.12, strax 2.2.3, straxen 4.1.1, xenon-fuse 1.6.3, nestpy 2.0.6,
   amstrax + amstrax_files from master — one environment for the chain and amstrax.
5. **Other fuse stages** (drift, extraction, S2, S1/S2 photons, delayed electrons, PMT/DAQ): configurable in
   principle; decided per stage in S4–S8, after converting our maps to their formats (or writing XAMS plugins).

## Open points found

- `ElectricField` uses an (r, z) map: fine for the yields (axisymmetric field), but SiPM effects are 3D — the drift
  step (S4) must use our 3D maps / drift maps rather than fuse's (r, z) assumption.
- Classification settings of the lineage clustering (`classify_phot_as_beta`, `classify_ic_as_gamma`, distance
  thresholds) to be checked with real Geant4 Cs-137 events in S3.
- The gas phase is outside the default region of interest (no S2 from gas interactions) — fine for XAMS.
