# Implementation plan — full XAMS simulation chain (xams-sim)

Goal: simulate XAMS from the radiation source to processed events — interactions, light and charge, drift,
extraction and electroluminescence, light collection, sensor response, waveforms — and push the result through the
**unchanged** amstrax processing, so simulation and data are compared with the same code and cuts. Every part can also
be run on its own, and **one configuration file** drives a complete simulation.

Status: plan (2026-10-16; fuse clustering and the repository decided 2026-10-18); **S0–S3 done 2026-10-18**.

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

- *one geometry in one place*: Geant4, COMSOL and the event chain all read the detector's `config/detectors/<d>/geometry.yaml`; no consistency
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
`xamssim particle <run>` (config + macro, `xamsg4` started in the `g4` env), `xamssim.g4io.read`; tests. Check:
`validation/s2_particle_check.py` (results in `results/s2_particle/`); the depth comparison with data needs the S4
drift model.

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

### S3. Input, clustering, yields (2 days) — **done 2026-10-18**

Result: `xamssim chain <run>` (`xamssim/chain.py`): strax context with `XamsG4Input` (our binary → fuse's
`geant4_interactions`; process name `RadioactiveDecay` → `RadioactiveDecayBase`), fuse lineage clustering (DBSCAN as
option), `XamsVolumeProperties` / `XamsVolumeSelection` (fuse's drift region, below cathode, gas + the liquid between
gate and surface; all four kept), fuse ElectricField and NestYields; all settings from the run, state, geometry and
materials (`physics` block for clustering and timeline). Field map: `xamssim maps --state <s> --export field`
(first an (r, z) half plane; replaced the same day by the 3D field read from the solved COMSOL model with `mph`,
`XamsElectricField` in (x, y, z); geometry v5 in the data frame, SiPMs from geometry.yaml). Check:
`validation/s3_microphysics_check.py` (results in `results/s3_microphysics/`): yields equal standalone nestpy; the
photopeak SS fraction after merging in z is independent of the clustering settings. Open: NEST beta vs gamma model
for Cs-137 (25 % in charge), from data; the S3 check numbers were made with the (r, z) map and geometry v4 (rerun
with the 3D map once the cmb50 state is solved).

Original task list:
- Input plugin: our binary format → exactly the table fuse's clustering expects (`geant4_interactions`: positions in
  cm, codes translated back to particle / process names), reading file by file in chunks (not the whole run at once),
  placing events on a timeline at the source rate.
- **fuse clustering** with XAMS settings: volume definitions (drift region, below the cathode, outside the field cage,
  gas) with their field / behaviour, cluster size and time window.
- NEST yields per cluster with the **local** field from the field map (fuse's yields plugin or our own, per S0).

**Check:** clusters per Cs-137 event and their volumes (single-scatter / multi-scatter / gamma-X fractions for the
raised source); sensitivity of the photopeak single-scatter fraction to cluster size and time window; yields against
standalone nestpy at fixed fields (100, 145, 500 V/cm); S1/S2 anticorrelation at 662 keV.

### S4. Field maps and drift (2–3 days) — **done 2026-10-18** (options open)

Result: drift map per state (`xamssim maps --state <s> --export drift`, `xamssim/driftmap.py`): one test electron per
grid point (1 × 1 × 0.5 mm inside the field cage) tracked against the 3D field with the NEST drift velocity until the
liquid surface, the bottom screen, the PTFE wall or a SiPM (~15 s per state); `XamsElectronDrift` looks up end point,
drift time and gate crossing per cluster, survival exp(−t/τ) (lifetime of the state) or 0, longitudinal / transverse
diffusion (materials.yaml); `XamsVolumeProperties` takes the regions from the drift map (only the liquid surface and
the field-cage radius remain as settings). Composite field (same day): the full-TPC map plus the gate and cathode
mesh-cell fields tiled near each mesh (`xamssim maps --export cells`): focusing into ~0.4 mm channels at the gate
holes, a ~1 mm layer above the cathode lost through its holes, bar losses only on the solid foil rim. Check (`../simulations/2026-10-18_s4_drift/`): drift time scale within 3 %,
SiPM catchment and wall losses growing with depth as in the data; not reproduced: the gradual S2 loss vs drift time at
large radius and the pile-up near the cathode (nothing leaks up through the cathode in sept; likely the low source
position). Open: partial losses at catchment edges, time-dependent fields (option), delayed-electron model (option),
cmb50 solve, source at cathode height. The Geant4 medium per
deposit was not needed: inside the field cage liquid / gas is exactly z vs the surface.

Original task list:
- efield: the 3D field map exists (S3, `xamssim maps --export field`, via `mph`); add the drift map per state (end
  point, drift time, loss flag on a grid) and the mesh-cell fields near gate, cathode and anode.
- Drift plugin: drift time from v(E), longitudinal / transverse diffusion, lifetime, losses (wall, SiPM, through the
  cathode holes), position at the gate; delayed-electron model as an option (paper).
- Volumes from the geometry and the field instead of z-planes: `XamsVolumeProperties` (S3) re-derives liquid / gas and
  the regions from flat planes and one radius, an approximation of what Geant4 and the field map already know.
  Replace it by: the medium (liquid / gas) from Geant4's volume code per deposit (carried through the input and the
  clustering), and what happens to the electrons from the drift map (end point: gate / surface, cathode, wall, SiPM),
  so "below the cathode", "above the gate" and "outside the field cage" follow from the field, not from fixed planes.
  The z-plane settings (`z_*_cm`, `r_field_cage_cm`) then go away.

**Check:** drift-time profile and maximum drift time against data (drift-profile study,
`../simulations/2026-10-12_efield_sipm_and_spread/`), apparent lifetime vs radius (SiPM checks, same study) for the
Sept state; volumes: clusters per medium equal the Geant4 energy per volume, and electron end points per region.

### S5. Extraction and electroluminescence (1–2 days) — **done 2026-10-19**

Result: extraction / EL map per state (`xamssim maps --export el`, `xamssim/elmap.py`) from the gate + anode cell model:
electrons from the liquid surface over a gate-hole cell tracked to the anode; NEST extraction efficiency, EL photons
per electron (Monteiro 140 E − 116 p_eq), transit time and emission profile with the gas drift velocity;
`XamsExtractionEL` (`extracted_electrons`) per cluster at its gate crossing. Check (`../simulations/2026-10-19_s5_extraction/`,
sept): extraction 0.64, 282 EL photons / e, S2 width at the gate 601 ns vs 605 ns in the data with the gas drift
velocity tuned to 3.1 mm/µs (no measurement at ~9 Td found); g2 (bottom) 6.5 vs 3.48 ± 0.68 PE/e (S2 light per
electron ~1.9× too high); width growth with depth faster in the data than D_L = 25 cm²/s gives. Open: a measured gas
drift velocity, the g2 factor, anode alignment (aligned assumed; shifted cell model exists), single-electron size
with S6 / S7.

Short-fill states (2026-10-19, `../simulations/2026-10-18_example/`): `cmb50` (anode–gate 2.2 kV, 4 mm liquid)
has E_liq 1.70 kV/cm at the surface and NEST extraction ≈ 0, so no S2. `cmb50_a36` (anode +3.6 kV, 3.3 kV) has
E_liq 2.55 / E_gas 4.99 kV/cm, extraction 0.23, 148 EL photons / e, g2 (bottom) 1.19 PE/e (≈ 0.64 with the sept
factor 1.9), about the Flierman-thesis g2 (0.74 PE/e at 3.2 kV); S2 width ≈ 800 ns at the gate.

Original task list:
- Extraction probability vs field below the surface; S2 photons per electron and their timing along the gas path
  (from the mesh-cell model incl. gate–anode alignment); S2 width.

**Check:** S2 width (gate-corrected) and single-electron size against data.

### S6. Light maps (2 days) — **chain step done 2026-10-19**, check against data open

Result: light maps per light key (`xamssim maps --export light`, `xamssim/lightmap.py`) from Geant4 optical runs with
the optics of `materials.yaml` (the fitted values of 2026-10-11, single values since 2026-10-19): S1 on a 2 mm (x, y, z) grid
in the liquid, S2 on a 1 mm (x, y) grid from the gas gap, per channel (bottom, top ch1–ch4, two SiPMs), QE included.
`XamsS1Light` / `XamsS2Light` → `s1_photoelectrons`, `s2_photoelectrons` (target `photoelectrons`). sept maps:
detection 7.8 % (S1) / 7.5 % (S2) on average; cmb50_a36 example: S1 AFT 0.11 → 0.25 from cathode to gate, S2 AFT
0.63 (centre) → 0.53 (r 26–30 mm); photopeak S1 2020 PE, S2 4.9·10⁴ PE (all channels). Open: statistics, the check
below.

Original task list:
- optical: S1 map (x, y, z → expected photons per channel) and S2 pattern map (x, y → per channel) from the fitted
  optical model; loader + photon → channel plugin.

**Check:** AFT vs r and S1 AFT vs depth against data (step 7/8 targets) for S1 and S2.

### S7. Sensors, fast output at peak level (2–3 days) — **chain step done 2026-10-19**, check against data open

Result: `XamsSensorResponse` (`peak_areas`: areas per channel with double-PE, SiPM crosstalk, SPE resolution from the
LED fits; detector `sensors.yaml`) and `XamsEvents` (`xams_events`, target `events`: one row per decay with S1, main /
alt S2, AFT, drift time, position, u, v, cS1 and cS2 corrected with the light maps and the lifetime). cmb50_a36
(2·10⁷ decays): photopeak cS1 2220 PE (10.7 %), cS2 6.2·10⁴ PE (12.8 %). Open: afterpulses, top-PMT non-linearity
(the analysis' top factor), measured double-PE / crosstalk, the comparison with the SR-2026.2 spectra.

Original task list:
- PMT: QE / CE, gain and SPE spectrum, double-PE, afterpulses, non-linearity under load (top PMT); SiPM: PDE,
  crosstalk. A "fast" output straight at peak level (S1, S2 areas per channel, positions) for quick studies.

**Check:** Cs-137 cS1, cS2 spectra and resolution per state (Sept vs CM-B), AFT; separate intrinsic (recombination)
from detector effects.

### S8. Waveforms → amstrax (1–2 weeks) — **first version 2026-10-20**, calibration and comparison open

Result: `XamsRawRecords` (`xamssim/waveforms.py`; target `raw_records`) and `xamssim.amstrax_io` (simulated records under
amstrax's keys, context without run database, the analysis' processing settings). DAQ description `daq.yaml` +
`spe_templates.npz` measured from run 7719 and the LED runs 7682 / 7723 (`../simulations/2026-10-20_s8_waveforms/`).
Test run (sept, 2·10⁵ Cs-137 decays at r 130 mm, z −82 mm): 821 decays with S1 and S2 in the sim, amstrax finds 812
events; S2 width50 ~715 ns, S2 AFT 0.56; 591 S1s stay unclassified (S1 AFT > 0.2, amstrax's limit): the sim's S1
top fraction is higher than in the data (ε_S1 0.74). Open: light calibration (top / bottom, g2, S1 scale), dark counts,
afterpulses, PMT non-linearity, the comparison of event_info with the data.
Gains: the MC is processed with the gains it was simulated with (gains.csv P4; double-PE only for VUV photoelectrons,
as in the data's LED calibration). Optional later: a simulated LED run type (externally triggered, no double-PE) to
run the analysis' LED fit on MC as a closure test of the gain calibration.

Original task list:
- Waveforms per channel (V1725, 4 ns, baseline, noise, thresholds, pre-trigger) → `raw_records` with simulated run
  metadata (DAQ config, gains) given from the config instead of MongoDB.

**Check:** amstrax processes simulated runs unchanged; the same analysis cuts give the same distributions as data
(cS1, cS2, widths, AFT, drift time) within the known differences.

### S9. The whole pipeline correct: validation against data, upstream to downstream — **planned 2026-10-22**

The chain runs end to end (S0–S8); what is open is whether its numbers agree with the data. Known differences (from the
S4–S8 checks, 2026-10-19 … 2026-10-21): geometry / source: source position (z −120 or −82 mm), liquid level (2 or
4 mm), SiPM positions not certain; drift: drift time at the gate 4.5 µs in the sim vs 1.14 µs in data (cathode 37.5 vs
38.3 µs), no S1–S2 anticorrelation in data, more and later alternative S2s in data, S2 width growing faster with depth
in data; EL: g2 ~1.9× too high in the sim; light: S1 scale ~0.5–0.6, top / bottom split (top-PMT effect in data), SiPM
S1 7× too low, sim S1 AFT higher (amstrax leaves S1s unclassified above AFT 0.2); sensors: released v2 gains vs LED
gains (top ~1.2×), top-PMT non-linearity, afterpulses, dark counts not modelled; DAQ: baseline effects and noise
triggers not modelled.

**Principle:** from upstream to downstream, one step at a time, each against a fixed data target: errors pile up (a
wrong liquid level shifts drift times, extraction and EL), so the upstream steps are settled before light or gains are
tuned. Measured quantities stay fixed; only what is not measured is tuned, and every tuned value is written down with the
data it came from.

0. **The comparison first** (was part of S12): a reference set of data runs (e.g. 7719 / 7687, Cs, sept; cmb50 data
   when taken) and a fixed list of observables with their data values: drift-time edges (gate, cathode), S2 width vs
   depth, photopeak cS1 / cS2 and resolutions, AFT vs depth and radius, light per channel incl. SiPMs, anticorrelation
   angle, alternative-S2 fraction, rates. One command that processes data and MC through the same analysis
   (analysis_SR2026.2 `X.context`, the same cuts) and writes a side-by-side report; the comparisons themselves are
   studies in `../simulations/`.
1. **Geometry and source:** liquid level and source position from the data (z distribution and energy spectrum of the
   photopeak events, drift-time edges). The gate discrepancy (4.5 vs 1.14 µs) points here first: liquid level, the field
   above the gate, or the drift velocity at high field.
2. **Drift:** drift-time scale, diffusion (S2 width vs depth), electron lifetime; then the missing anticorrelation and
   the alternative S2s (charge loss, delayed electrons; the model belongs to the paper, open question 5).
3. **Extraction and EL:** the g2 factor (extraction efficiency and EL yield against the gas field); the mesh-cell figure
   of the app belongs here.
4. **Light:** the optical parameters (PTFE reflectivity, absorption and Rayleigh lengths, QE top / bottom) against S1
   light and AFT vs depth and the S2 pattern; then the SiPM S1 deficit (filter efficiency, positions).
5. **Sensors:** one consistent set of gains (LED vs released), SPE resolution, double PE, the top-PMT non-linearity
   (the "top effect" in data).
6. **DAQ / waveforms:** dark counts and afterpulses where they matter for S1 finding and classification; S1
   classification (AFT limit) and event building in amstrax against data.
7. **End to end:** the whole list of observables in one report; then everything is rerun (geometry v5, all maps; old
   outputs are disposable) and the report is the reference for the MC productions.

Alongside: a higher `source_rate_hz` (e.g. 1–2 kHz) in production runs, so that the live-data route does not take
hours (run 900001: 19 048 chunks at 100 Hz, 6 h through amstrax).

Decisions from the user: which data runs are the reference; which parameters are fixed (measured) and which may be
tuned; whether the delayed-electron model is part of "correct" now or later for the paper.

### S10. MC runs as runs: run database, central storage, STBC, dashboard (1–2 weeks) — **planned 2026-10-20**

Goal: one process flow for data and MC. A simulated run is a run like a data run: a number (900000–999999), a run
document in MongoDB, raw records in a central place, processed by amstrax and the analysis in the same way, visible in
the dashboard. **Order: first a full shakedown of the chain (S8) with the file-based bookkeeping of today; database,
central storage and dashboard only after that.**

Now (S8, 2026-10-20): `xamssim amstrax <run>` copies the raw records into `measurements/strax_data` (Mac) with
`<n>-metadata.json` (run document as a file, incl. the `xamssim` section with the truth, not applied) and
`<n>-truth.npz`; amstrax reads the run document from the file (local amstrax branch `rundoc-file-fallback`);
corrections from amstrax_files (global v5: v4 + the true values of the MC runs).

Plan:
1. **Run database:** collection `run.runs_mc` in the XAMS MongoDB (on xams), never `runs_gas`: the dispatcher takes
   the next data run number as max(number) + 1 over `runs_gas`, and auto-processing / copy_live / dashboard read it.
   A run enters `runs_mc` at export (`xamssim amstrax`), when its raw records exist (as a data run enters at run
   start): number, mode, start / end, tags, comments, daq_config, `data[]`, and the `xamssim` section (run file, run
   key, state, source, detector, truth). Numbers handed out by the database (no collisions). Rerun = same number, doc
   updated, old processed data removed; a deleted simulation keeps its doc with tag `deleted` (numbers never reused).
   Writes to production MongoDB: user's OK and a database user that can only write `runs_mc`. Without access the
   export writes the file as now.
   **Cleaning up (decided 2026-10-21):** the separate collection can always be emptied: all at once (drop) or by filter
   (study, number range, tag), through xams-sim (`xamssim db --delete ...`: shows what goes, asks for confirmation,
   removes the database entries and the files in `live_mc` / `mc_*` together), with a dump of `runs_mc` first
   (`mongodb_backup`). The bookkeeping is first tried in a test collection `runs_mc_test`, dropped once it works, so
   that `runs_mc` starts clean. Numbers may be reused during the test phase, never once MC results are used.
2. **amstrax:** run docs of numbers ≥ 900000 from `runs_mc` (rundb.py, `get_rundoc_value`), file fallback kept.
   PR; the STBC production checkout only with the user's OK.
3. **Central MC storage on STBC:** MC in its own folders next to the data folders, readable by everyone in XAMS,
   owner `xamsdata` (production area: user's OK), never inside the data areas (decided 2026-10-21):
   `/data/xenon/xams_v2/live_mc` (simulated live data; next to `live_data`, which the DAQ copy / delete scripts and
   the data auto-processing use), `mc_raw_records` and `mc_processed` (next to `xams_raw_records`, `xams_processed`),
   truth files with the raw records. Deleting all MC = removing these folders. The run doc's `data[]` lists the copies (host, path,
   type), as for data. strax finds data through its storage folders, so contexts on STBC get this folder as a
   read-only frontend; processed MC goes where the user's processing goes (e.g. the personal
   `measurements/strax_data`, as for private data processing). The Mac copy is a working copy.
4. **MC on STBC** (**installed 2026-10-20**, condor test and the sept run 900001 on condor 2026-10-21): xams-sim installed on stbc-i2 (environment like `xamssim`: Geant4 build, fuse / strax, amstrax),
   productions as condor jobs (one job per seed / event block; Claude may submit, at most 10 jobs in the queue at
   once), small tests in the background on stbc-i2; the maps (registry) and COMSOL field maps made on the Mac and
   copied (COMSOL only on the Mac). Output straight into the central MC folder.
5. **Dashboard:** a patch to xams-dashboard (stbc-i1) to list `runs_mc` next to the data runs: the simulation inputs
   (state, source, detector, run key, events, `xamssim show`) and the processing status; new MC runs show up as
   unprocessed (raw records only) and can be processed from there like data. Deployment only with the user's OK.

6. **Live data instead of raw_records (decided 2026-10-20):** xams-sim writes the simulated waveforms in redax's
   live-data format (`live_data/<run>/` chunks of compressed fragments, as redax writes them), and the standard amstrax
   environment converts them to raw_records with its `DAQReader`, exactly as for data. Then xams-sim needs no amstrax
   at all (today it is only used to name the raw_records folder: the lineage hash of amstrax's raw_records), there is
   no amstrax version to keep in sync, and the MC tests the whole data flow from the first step. To do: the exact
   redax format (fragment layout, compression, chunk files and overlap), tested against a real live-data chunk of
   xams; the run document gives what `DAQReader` reads from it. Until it works, the current export (raw_records
   directly, with amstrax in the xamssim environment) stays as the shortcut.
   **Shakedown without the database (started 2026-10-21):** amstrax's `context_for_daq_reader` takes the run document
   from the stored file when there is one (as `get_rundoc_value` since amstrax #346); xams-sim writes live data only
   into a folder named `live_mc` (never `live_data`), now `users/acolijn/xamssim/live_mc`; the run document carries the
   `daq_config` fields `DAQReader` needs (from Science_Rev2.4 / run 7719). Test: 900101 via live data → raw_records →
   event_info, compared with the direct export; also processing with the database connection on (read-only RunDB:
   must fall back to the file, not stop). The auto-processing scripts (status in MongoDB) wait for point 1.
7. **Environments on STBC** (done 2026-10-20): conda envs in the py312 miniforge, as the other XAMS stacks:
   `anaconda/xamssim` (pip packages) and `anaconda/g4` (Geant4, only to build and run `xamsg4`, started by xamssim
   itself); `setup_xamssim.sh`; personal settings in `~/.config/xamssim/env`. Processing and analysis of MC in the
   standard amstrax environment, the same as for data.

**Check:** a data run and an MC run go through the same commands (context, step scripts, EventDisplay) with only the
run number different; another user on STBC can process and read an MC run; the dashboard lists it.

### S11. Simulation app: overview and composer (2–3 weeks, in phases) — **planned 2026-10-20, worked out 2026-10-21**

A web app to see which simulations exist and how they were made, and to compose new ones, instead of reading and
editing YAML by hand. No notebook stage (user, 2026-10-21): a web app from the start. **The text files stay the source
of truth:** what is composed is written as ordinary run / state / source files in `simulations/<study>/` and
committed; nothing lives only in the app.

**Where the code lives:** the logic in the package, `xamssim/compose.py` (choices, draft → check, derived state /
source files, writing run files, starting on condor), usable without the app (`xamssim compose`, tests); the app in
its own folder `web/` in the xams-sim repository, using only `xamssim.compose` and the existing listing / provenance /
maps code, with its web dependencies as an optional extra (`pip install -e .[web]`; the chain and condor jobs do not
need them). Same repository so that core and app change together (one PR, one version); `web/` can move to its own
repository later if it grows or joins the xams-dashboard.

**Where it runs:** for development on the Mac (`xamssim web`); shared on stbc-i1 as xamsdata next to the xams-dashboard
(own port, reached the same way), from `software/xams-sim` in `anaconda/xamssim`, writing run files into a configured
simulations checkout; deployment only with the user's OK. Same stack as the xams-dashboard (to be checked first). It
shows the data folder of the machine it runs on (Mac / STBC); with S10's central MC folder one place for everyone.

**Split with the xams-dashboard:** the app answers which simulations exist and *how* they were made (parameters, maps,
code, current / outdated); the xams-dashboard which *runs* exist, where their data are and how far they are processed.
An MC run with a number appears in both, each from its side, linked ("simulation details" ↔ "processing / data");
simulations without a run number (fast events only, tests, reruns), optical scans and maps only in the app.

Pages:
1. **Simulations overview** (first; read-only, from `xamssim list` and the provenance files, no database): all
   simulations with study, run name, run number, state, source, decays, date, how far (events / waveforms / live
   data), status (current / outdated against run file and maps), size, location; filters on study, state, source,
   status.
2. **Detail page of a simulation:** all parameters as used (voltages per electrode, liquid level, lifetime, source
   position, physics settings, detector and geometry version), the maps with their keys, the code version (commit,
   uncommitted changes), the products with lineage (`xamssim show`), links to the xams-dashboard. Fixed figures, made
   once per simulation and stored next to its provenance file (so a page loads at once), mostly from what exists in
   `view_results.ipynb` and the map exports:
   - *configuration (what went in):*
     1. side cross-section of the TPC (r–z) from `geometry.yaml`: anode, gate, cathode, screens, field cage, PTFE,
        PMTs, SiPMs, liquid level, source position; each electrode with its voltage;
     2. field configuration on that cross-section (the state's field map): |E| in colour with field lines; drift lines
        from the drift map (where electrons end: surface, wall, SiPM, mesh bar; loss regions marked); drift field,
        extraction field in the liquid, field in the gas gap as numbers;
     3. top view (x–y): gate and cathode mesh with hole pattern and rotation, top-PMT sectors ch1–ch4, SiPM positions,
        field-cage radius;
     4. zoom on the mesh cell (cell / EL map): field around the gate holes, extraction efficiency and EL yield per
        position in the cell (u, v);
     5. light maps: S1 detection probability per channel vs depth and radius; S2 pattern on the top sectors in x–y;
     6. the source: isotope, activity, position, spectrum where relevant;
   - *results (what came out; the same fixed set for every simulation, fuller analysis stays in notebooks):* energy
     per decay and where it was deposited (y–z); drift (fraction of electrons arriving, drift time vs depth); cS1 vs
     cS2 around the photopeak; S2 width and AFT vs depth and radius; photoelectrons per channel incl. SiPMs; with
     waveforms one example event.
3. **Compare two simulations:** differing parameters as a table (`xamssim show --diff`), cross-sections side by side
   and the difference of the fields (e.g. sept vs cmb50).
4. **Maps:** which maps exist, for which states, which are missing and how to make them.
5. **Composer:** choose study, state, source, events, seed, how far (fast events, waveforms, live data). Shown before
   anything runs: the resolved configuration, errors, the map status (present / missing with the reason, e.g. "voltage
   G changed → new field map, COMSOL on the Mac"), reuse of Geant4 output with the same key, an estimate of time, disk
   and condor jobs (from measured runs: sept 2·10⁷ decays on condor: Geant4 30 min, chain 53 min), the next free run
   number. New states / sources are derived from existing ones ("sept with cathode −4 kV", "Cs at z = −50 mm"): a new
   file under a proposed name with its difference shown; existing files are never changed. The source position is
   set on the cross-section; the voltages in a table against the state's values.
6. **Start:** on condor with the existing job scripts (`condor/run_xamssim.sh`, `live_process.sh`; at most 10 jobs),
   progress per step.

Phases: (a) overview, detail pages with figures, comparison, maps (read-only); (b) composer writing run / state /
source files; (c) starting on condor; (d) integration with S10 (`runs_mc`, links with the xams-dashboard).

### S12. Overview and docs (2–3 days)
- Validation against data: S9.
- **Detectors (2026-10-19):** `config/detectors/<detector>/geometry.yaml`, `detector:` in every state; keys follow
  the resolved geometry (hole pattern included), COMSOL models carry a geometry tag. Now one detector, `xams2026`.
  For a structurally different detector (e.g. a SiPM top array) still to make generic: Geant4 sensors from a list,
  the chain's channel list, the COMSOL electrodes and sensors; with regression tests that xams2026 stays the same.
- **Provenance (2026-10-19):** every chain run writes `<data>/provenance/<run>/…json` (full resolved configuration,
  maps, Geant4 config, products with lineage, code); `xamssim show <run> [--hash H] [--diff] [--full]`.
- `xamssim list` (**first version 2026-10-19**: runs, Geant4 output, strax products current / old, maps per
  state, `--prune` listing old data, `--delete` removing it after a confirmation; to do: study summary, map staleness per run): overview of everything in the data folder — per run (study, run file, state, source, run key): the
  Geant4 output (events, output hash, xams-sim version), the strax products made with their lineage hashes and whether
  they are current for the run file as it is now (state, maps, settings, Geant4 output), and the maps per state
  (present / missing / stale). Optional: `--prune` lists outdated data that can be removed (never deletes by itself).
- Docs: config reference, how to run each producer and the chain, how to add a state or a source.
- The web page for studies, runs and productions: S11.

## Effort

| Part | Effort |
|---|---|
| S0–S1 (decisions, repo, config, registry) | ~2–3 days |
| S2–S4 (Geant4 particle, yields, drift) | ~6–8 days |
| S5–S7 (extraction/EL, light maps, sensors, fast output) | ~5–7 days |
| S8 (waveforms → amstrax) | 1–2 weeks |
| S9 (validation against data, upstream to downstream) | 2–4 weeks |
| S10 (MC runs as runs: database, central storage, STBC, dashboard) | 1–2 weeks |
| S11 (simulation dashboard) | 2–3 weeks |
| S12 | ~2 days |

After S7 the chain already answers the physics questions (resolution per state, SiPM and cathode effects, gamma-X);
S8 adds the like-for-like comparison through amstrax.

## Open questions

1. fuse beyond clustering: which other plugins (yields, drift, extraction, PMT, waveforms) — per plugin in S0.
2. ~~One repository or separate repositories~~ — decided 2026-10-18: optical_sim → xams-sim (XAMS-nikhef, private).
3. strax / amstrax versions for the simulation environment (STBC runs strax 1.5.4 on Python 3.8).
4. Where the field map comes from in production: COMSOL file export (security setting) or the printed-map route.
5. Delayed-electron model in the drift step: which model (for the paper).
6. Large productions: the Mac for development; condor on Stoomboot for big runs (max 10 jobs at once, S10).
