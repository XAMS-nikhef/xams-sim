# Implementation plan — full XAMS simulation chain (xams-sim)

Goal: simulate XAMS from the radiation source to processed events — interactions, light and charge, drift,
extraction and electroluminescence, light collection, sensor response, waveforms — and push the result through the
**unchanged** amstrax processing, so simulation and data are compared with the same code and cuts. Every part can also
be run on its own, and **one configuration file** drives a complete simulation.

Status: plan (2026-10-16; fuse clustering and the repository decided 2026-10-18); **S0, S1 and S2 done 2026-10-18**.

## Principles

- **One source per kind of information.** Geometry: `geometry.yaml`. Materials and optics: `materials.yaml`.
  A detector setting (HV, level, pressure, lifetime, gains): one *state* file. A simulation: one *run* config that
  names a state and a source. Nothing is typed twice.
- **Two kinds of software.**
  - *Map producers* — standalone packages that turn geometry + state into maps, slowly, once per state:
    field (COMSOL), light collection (Geant4 optical), mesh-cell extraction / EL. Each has its own command line and can
    be run by hand; the chain calls them only through their command line and reads their output files.
  - *The event chain* — strax plugins that simulate events quickly, using those maps.
- **amstrax is not changed.** The chain stops at `raw_records`; from there the normal amstrax plugins take over.
- **fuse (XENONnT) as a library, not a fork.** Decision 2026-10-18: use **fuse's clustering** (Geant4 steps →
  clusters, interaction type, assignment to volumes); the other fuse plugins are decided one by one. Unchanged plugins
  are imported, XAMS versions are subclasses in xams-sim, missing ones are our own. All settings come from our config.
  fuse plugins are strax plugins, so the chain runs in a strax context; amstrax stays independent (xams-sim uses it,
  never the other way round).
- **No ROOT, no CSV.** Geant4 writes fixed-size binary records + a JSON header (as optical_sim now); particle and
  process names stored as small integer codes with the lookup table in the header; our input plugin turns them into
  fuse's table. CSV only for small tests (fuse's CSV reader loads the whole file into memory; text is 3–5× larger,
  slow and rounds numbers). Parquet / HDF5 only if compression or partial reading is needed later. Maps are `.npz` /
  HDF5 with a JSON manifest.
- **Provenance everywhere.** Every map and every simulated run records the config, the state, the code versions and
  the date; strax lineage does this automatically for the chain.
- Each step ends with a check; a step is done when its check passes. Rough effort in brackets.

## Overview

```
                 ┌────────────────────────── config ──────────────────────────┐
                 │ geometry.yaml   materials.yaml   states/<state>.yaml        │
                 │ sources/<source>.yaml            runs/<run>.yaml  (one file │
                 │                                  names state + source + N…) │
                 └───────────────┬─────────────────────────────┬──────────────┘
          MAP PRODUCERS (standalone, once per state)           │  EVENT CHAIN (strax, per simulation run)
   ┌───────────────────────────────────────────┐               │
   │ efield   (COMSOL)  → field map |E|(x,y,z)  │──┐            ▼
   │                     drift map (end point,  │  │   xams-g4 particle mode → deposits (binary records)
   │                     time, loss) per state  │  │            │
   │ efield cell (COMSOL) → extraction / EL map │  │            ▼
   │ optical (Geant4 optical) → S1 light map,   │  ├──▶ [deposits] → [clusters] → [quanta: NEST, local field]
   │                     S2 pattern map / chan. │  │            → [drifted electrons] → [extracted e⁻ + S2 photons]
   │ (later) gains, noise, SPE from data        │──┘            → [photons per channel] → [photoelectrons]
   └───────────────────────────────────────────┘                → [PMT / SiPM response] → [raw_records]
                                                                          │
                                                                          ▼
                                                     amstrax (unchanged): records → peaks → events
```

## Software in the chain

| Software | Role | Kind | Language / tool | Input | Output | Status |
|---|---|---|---|---|---|---|
| **config** | geometry, materials, states, sources, runs | data | YAML | — | — | geometry.yaml exists (optical_sim) |
| **xams-g4** | Geant4 app, two modes: *particle* (interactions) and *optical* (photon transport) | standalone + called by the chain (particle mode) | C++ / Geant4 | geometry, source | deposits (binary) / photon records | optical mode exists (optical_sim); particle mode new |
| **efield** | electric field, drift lines, mesh cells | map producer (standalone) | Python → COMSOL Java | geometry, state (HV) | field map, drift map, extraction/EL map | exists (optical_sim/efield), needs map export |
| **optical maps** | light collection per channel from Geant4 optical scans | map producer (standalone) | Python on xams-g4 output | geometry, materials (fitted optics) | S1 map (x,y,z → channel), S2 pattern map (x,y → channel) | scans exist (optical_sim step 6–8); map format new |
| **nestpy** | light and charge yields per cluster vs local field | library | Python (NEST) | energy, type, field | photons, electrons | external |
| **fuse** | XENONnT simulation plugins; **clustering used** (decided), others (yields, drift, extraction, PMT, waveforms) per plugin | library | Python / strax | deposits table | clusters with type and volume | external; check in S0 |
| **xams-sim** | the event chain: XAMS plugins, context, CLI, map registry, validation | chain | Python / strax | run config + maps | strax data up to `raw_records` | new |
| **strax** | plugin framework, lineage, caching | library | Python | — | — | external (STBC: 1.5.4) |
| **amstrax** (+ amstrax_files) | processing of `raw_records` | library, **unchanged** | Python / strax | raw_records | peaks, events | existing |

## The single configuration

A simulation run is one file; everything else is referenced:

```yaml
# runs/cs137_cmb50_001.yaml
state: cmb50              # -> states/cmb50.yaml: HV case, liquid level, pressure, electron lifetime, gains, noise
source: cs137_raised      # -> sources/cs137_raised.yaml: isotope, activity, position, collimator
n_events: 200000          # or: live_time_s
seed: 1
stop_after: raw_records   # or any intermediate product: quanta, drifted_electrons, photoelectrons, ...
physics:                  # only overrides; defaults live in materials.yaml / the plugin configs
  nest_model: default
  diffusion: on
```

`xamssim run runs/cs137_cmb50_001.yaml` then:

1. resolves the state → which maps are needed (field, drift, extraction/EL, S1, S2), looks them up in the **map
   registry** (`maps/manifest.json`: state hash → files + provenance);
2. for a missing map, runs the producer (`efield …`, `optical-maps …`) or stops with the exact command to run (COMSOL
   and Geant4 optical scans can take long — default: tell, not run);
3. runs xams-g4 in particle mode for the source (or reuses deposits with the same source/geometry/seed);
4. builds the strax context (XAMS plugins + chosen fuse plugins + amstrax) with **all** settings from the config, and
   produces the requested data type.

Each producer and each stage can also be run alone, e.g. `efield field --state cmb50`, `xams-g4 particle
--source cs137_raised -n 1e5`, or in Python `st.get_array(run, "drifted_electrons")`.

## Repository layout

```
XAMS-nikhef/xams-sim
  config/        geometry.yaml (moved from optical_sim), materials.yaml, states/, sources/, runs/
  g4/            Geant4 application (particle + optical mode; the optical_sim C++ code moves here)
  efield/        COMSOL generators, drift, mesh cells (from optical_sim/efield), + map export
  optical/       optical scans -> light maps (from optical_sim tools)
  xamssim/       Python package
    config.py    load + validate config, resolve state/source, hash for provenance
    maps.py      map registry and loaders
    context.py   the strax context (XAMS + fuse + amstrax plugins)
    plugins/     XAMS plugins: input reader (our binary format → fuse's input table), drift, extraction/EL, light,
                 sensors, waveforms (clustering comes from fuse)
    cli.py       xamssim run / maps / status
  maps/          generated maps + manifest (not in git; large) 
  validation/    comparisons with data (step 7/8 targets, Cs spectra, AFT, drift profile, S2 width)
  docs/
```

**Decision (2026-10-18): one repository — optical_sim is renamed and restructured into xams-sim**, not a new repo
and not separate repositories per producer:

- *one geometry in one place*: Geant4, COMSOL and the event chain all read `config/geometry.yaml`; no consistency
  problem between repositories when a dimension changes;
- *history kept*: optical fits, mesh / field studies, notes and results keep their commits (logbook links stay valid);
- *least work*: a rename plus a few move commits; the producers (efield, optical) stay standalone through their own
  command lines inside the repository;
- *home*: transferred from `acolijn/xams-optical-sim` to the **XAMS-nikhef** organisation as a **private** repository
  (next to amstrax; access for students managed there); GitHub redirects the old URL;
- *when*: at the start of S1, after the fuse read-through; until then work continues in optical_sim as now.

## Steps

### S0. Decisions and fuse read-through (1 day) — **done 2026-10-18**

Result: `xamssim_s0/README.md` (scripts `list_configs.py`, `micro_test.py`, settings list `fuse_settings_1.6.3.txt`).
One environment works: Python 3.12, strax 2.2.3, straxen 4.1.1, xenon-fuse 1.6.3, **nestpy 2.0.6** (fuse fails with
2.1.x), amstrax master. fuse's micro-physics runs offline with XAMS settings (volumes, COMSOL field map, default
NEST); **lineage clustering** chosen (DBSCAN defaults split tracks into µm clusters → ~50 % too much light at 662 keV);
input = own plugin providing fuse's `geant4_interactions` table.

Original task list:
- Clone fuse (read only), list its plugins and all settings (`st.show_config`) in a throwaway environment.
- Per plugin: usable via config / needs a XAMS subclass / tied to XENON infrastructure (database, URL configs,
  hard-coded PMT counts, 10 ns sampling).
- Clustering (decided to use, verify): its input table (fields, units, particle / process codes) — this fixes the
  Geant4 particle-mode output (S2); volumes configurable for XAMS (drift region r < 31 mm gate–cathode, region below
  the cathode with reverse field, LXe outside the field cage, gas) rather than hard-coded XENONnT geometry; cluster
  size / time window and their defaults; no hidden database access.
- Which NEST version and settings does fuse use; any XENONnT tunings (their field ~23 V/cm, ours 100–150 V/cm)?
- Versions: strax / amstrax (STBC: strax 1.5.4, Python 3.8) vs what fuse needs → one environment or chain and
  amstrax in separate steps (raw_records written to disk in between).

**Check:** clustering confirmed usable with XAMS settings (else: copy its code into xams-sim with the BSD-3 notice);
decision per other fuse plugin written down; environment and versions fixed (one environment, or the chain and amstrax
separately with `raw_records` on disk in between).

### S1. Repository, config and map registry (1–2 days) — **done 2026-10-18**

Result: repository renamed and transferred to `XAMS-nikhef/xams-sim` (private; tag `optical-sim-final` = last state
before the restructure); layout `config/`, `g4/`, `optical/`, `efield/`, `xamssim/`, `maps/`; Geant4 build in
`g4/build`; check_step1–3 pass (check_step4 / 5 fail as before the move); conda env `xamssim` (Python 3.12, strax 2.2.3,
straxen 4.1.1, xenon-fuse 1.6.3, nestpy 2.0.6, amstrax master, `pip install -e .[test]`); `xamssim status | maps |
validate`, 8 tests. States reference the HV cases in `efield/cases.yaml` (not duplicated); map keys are hashes of
exactly the inputs per map kind (light maps shared by all HV states).

Original task list:
- Repository move (decision above), in one go:
  1. rename `acolijn/xams-optical-sim` → `xams-sim` and transfer it to XAMS-nikhef (private);
  2. restructure in a few commits: `geometry.yaml` → `config/`, the Geant4 code → `g4/`, scan tools and step 6–8 →
     `optical/`, `efield/` stays, new `xamssim/`; `results/`, `notes/`, `docs/` stay; check that the existing scripts and
     the MkDocs build still run after each move;
  3. update the local folder name, the remote, `AGENTS.md` (systems + repositories tables), links in the logbook and
     the docs site.
- Config schema (states, sources, runs), loader with validation and hashing.
- Map registry: manifest with state hash → files, producer version, date; `xamssim maps --state X` lists what exists
  and what is missing (with the command to make it).
- Conda environment `xamssim` on the Mac (strax, amstrax, nestpy, fuse if chosen); Geant4 stays in `g4`.

**Check:** `xamssim status runs/<run>.yaml` shows the resolved state, source and the map status.

### S2. Geant4 particle mode (2–3 days) — **done 2026-10-18**

Result: `xamsg4 -m particle` (g4/include/ParticleMode.hh): EM option 4 + decay + radioactive decay (decay-time threshold
raised for Cs-137), source = ion at rest in a 1 mm steel capsule (or a gamma, isotropic or cone), decay products at
t = 0; one 46-byte record per energy deposit in LXe / GXe + one event record + JSON header (code tables, units, config,
seed, counts); particle-mode materials: PMT bodies / frames kovar, dead crosses steel, world ±300 mm. Python:
`xamssim particle <run>` (config + macro, runs in the `g4` env), `xamssim.g4io.read`; 15 tests. Check
(`results/s2_particle/`): photopeak 662 keV, Compton edge 477 keV, photopeak fraction ≈ 0.20, photopeak rate vs source
height; the depth comparison with September data needs the S4 drift model (data z distorted by the slow drift near
cathode and gate). 2·10⁶ decays ≈ 35 s.

Original task list:
- xams-g4 with a particle mode: source from `sources/` (isotope via Geant4 radioactive decay, position, collimator),
  full XAMS geometry incl. the region below the cathode and the gas; output per step: event id, x, y, z, t, dE,
  particle, process, track / parent id → binary records + JSON header. Record layout (one C++ struct per step,
  ~40–50 bytes): event id, x, y, z [mm], t [ns], dE [keV], particle code, parent particle code, track id, parent id,
  creation-process code, deposit-process code; per event the primary position. The JSON header holds the code → name
  tables (Geant4 particle / process names), units, geometry hash, source, seed, Geant4 and code versions. Python
  reads a file with `np.fromfile(path, dtype)`.

**Check:** Cs-137 deposit spectrum (photopeak fraction, Compton edge) and the depth profile for the raised source;
compare the photopeak depth profile with data (orphan-S1 / source-position analyses).

### S3. Input, clustering, yields (2 days)
- Input plugin: our binary format → exactly the table fuse's clustering expects (`geant4_interactions`: positions in
  cm, codes translated back to particle / process names), reading file by file in chunks (not the whole run at once),
  placing events on a timeline at the source rate.
- **fuse clustering** with XAMS settings: volume definitions (drift region, below the cathode, outside the field cage,
  gas) with their field / behaviour, cluster size and time window.
- NEST yields per cluster with the **local** field from the field map (fuse's yields plugin or our own, per S0).

**Check:** clusters per Cs-137 event and their volumes (single-scatter / multi-scatter / gamma-X fractions for the
raised source); sensitivity of the photopeak single-scatter fraction to cluster size and time window; yields against
standalone nestpy at fixed fields (100, 145, 500 V/cm); S1/S2 anticorrelation at 662 keV.

### S4. Field maps and drift (2–3 days)
- efield: export of the 3D field map and a drift map per state (end point, drift time, loss flag on a grid), from the
  COMSOL model (needs "File system access: All files", or the printed-map route).
- Drift plugin: drift time from v(E), longitudinal / transverse diffusion, lifetime, losses (wall, SiPM, through the
  cathode holes), position at the gate; delayed-electron model as an option (paper).

**Check:** drift-time profile and maximum drift time against data (`results/drift_profile`), apparent lifetime vs
radius (`results/sipm_checks`) for the Sept state.

### S5. Extraction and electroluminescence (1–2 days)
- Extraction probability vs field below the surface; S2 photons per electron and their timing along the gas path
  (from the mesh-cell model incl. gate–anode alignment); S2 width.

**Check:** S2 width (gate-corrected) and single-electron size against data.

### S6. Light maps (2 days)
- optical: S1 map (x, y, z → expected photons per channel) and S2 pattern map (x, y → per channel) from the fitted
  optical model; loader + photon → channel plugin.

**Check:** AFT vs r and S1 AFT vs depth against data (step 7/8 targets) for S1 and S2.

### S7. Sensors, fast output at peak level (2–3 days)
- PMT: QE / CE, gain and SPE spectrum, double-PE, afterpulses, non-linearity under load (top PMT); SiPM: PDE,
  crosstalk. A "fast" output straight at peak level (S1, S2 areas per channel, positions) for quick studies.

**Check:** Cs-137 cS1, cS2 spectra and resolution per state (Sept vs CM-B), AFT; separate intrinsic (recombination)
from detector effects.

### S8. Waveforms → amstrax (1–2 weeks)
- Waveforms per channel (V1725, 4 ns, baseline, noise, thresholds, pre-trigger) → `raw_records` with simulated run
  metadata (DAQ config, gains) given from the config instead of MongoDB.

**Check:** amstrax processes simulated runs unchanged; the same analysis cuts give the same distributions as data
(cS1, cS2, widths, AFT, drift time) within the known differences.

### S9. Validation suite and docs (2 days)
- `validation/`: one command per comparison (data targets from analysis_SR2026.2), report per state.
- Docs: config reference, how to run each producer and the chain, how to add a state or a source.

## Effort

| Part | Effort |
|---|---|
| S0–S1 (decisions, repo, config, registry) | ~2–3 days |
| S2–S4 (Geant4 particle, yields, drift) | ~6–8 days |
| S5–S7 (extraction/EL, light maps, sensors, fast output) | ~5–7 days |
| S8 (waveforms → amstrax) | 1–2 weeks |
| S9 | ~2 days |

After S7 the chain already answers the physics questions (resolution per state, SiPM and cathode effects, gamma-X);
S8 adds the like-for-like comparison through amstrax.

## Open questions

1. fuse beyond clustering: which other plugins (yields, drift, extraction, PMT, waveforms) — per plugin in S0.
2. ~~One repository or separate repositories~~ — decided 2026-10-18: optical_sim → xams-sim (XAMS-nikhef, private).
3. strax / amstrax versions for the simulation environment (STBC runs strax 1.5.4 on Python 3.8).
4. Where the field map comes from in production: COMSOL file export (security setting) or the printed-map route.
5. Delayed-electron model in the drift step: which model (for the paper).
6. Large productions: the Mac for development; stbc-i2 in the background for big runs (no condor).
