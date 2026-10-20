# Configuration

Everything that describes the detector and a simulation lives in `config/` (plus the HV cases in `efield/cases.yaml`).
Every kind of information has exactly one place:

```
config/runs/<run>.yaml ─┬─ state ──► config/states/<state>.yaml ─┬─ detector ─► config/detectors/<detector>/geometry.yaml
                        │                                          │               (dimensions; which part is which material)
                        │                                          └─ hv_case ──► efield/cases.yaml (voltages, field cage, SiPMs)
                        ├─ source ─► config/sources/<source>.yaml
                        └─ config/materials.yaml  (all material properties incl. optics)
```

`xamssim validate <run>` loads and checks all of it; `xamssim status <run>` shows the result.

## Detectors — `config/detectors/<detector>/`

One folder per detector: `geometry.yaml` and the files it refers to (`mesh_holes.json`), and `sensors.yaml` (the
sensor response per channel; separate, so a change there renews only the sensor step), `daq.yaml` and
`spe_templates.npz` (digitizer, channels, thresholds, baselines, noise, gains, single-PE pulse shapes: the waveforms, S8). Now one detector,
`xams2026` (the current XAMS). A different detector (e.g. a SiPM top array) is a new folder; its states name it, and
since every key (Geant4, maps, lineage) follows the resolved geometry, runs of one detector never make those of another
old. Small changes for a study belong in a new detector folder too (copy and edit) — never edit the geometry of a
detector whose data you still use, it makes all its runs old.

## `geometry.yaml` — dimensions

Shapes and positions of every part, each value with its source (drawings in `reference/XAMS design/`, thesis,
position reconstruction, the user). Units mm and degrees; z = 0 at the gate foil, z up; x along the edge of the
top-PMT anode sectors. Sections:

| section | content |
|---|---|
| `liquid` | liquid-level scenarios above the gate |
| `mesh_common`, `meshes` | the five etched meshes (foil, holes `mesh_holes.json`, pitch, rings; z, angle, foil side per mesh), `material` |
| `ptfe_cylinder`, `field_shaping_rings` | inner PTFE cylinder, copper rings (z of each ring), `material` |
| `pmt_ptfe`, `ptfe_bucket` | PMT holders, bucket (its weir sets the liquid level), `material` |
| `cryostat_vessel`, `cryostat_outer` | inner vessel (gas; tube, flanges, `center_z_mm`) and outer vessel (vacuum; tube, flanges, `inner_vessel_offset_mm`), `material` |
| `pmt_common`, `pmts`, `sipms` | PMTs (window, photocathode, sectors, QE, window / body material), SiPMs |
| `sources`, `targets` | source shapes of the optical mode; measured data targets for the optical fits |

Details of the model: [Geometry](geometry.md).

## `materials.yaml` — material properties

The single source for densities, Geant4 definitions, electrical role and optics. Reference conditions 2 bar,
175 K (xenon densities from NIST).

```yaml
materials:
  liquid_xenon:
    density_g_cm3: 2.8748
    state: liquid
    temperature_k: 175.0
    pressure_bar: 2.0
    geant4: {composition: {Xe: 1}, molar_mass_g_mol: 131.29}     # or {nist: G4_...} or {composition_by_mass: {...}}
    electrical: {kind: dielectric, relative_permittivity: 1.96}  # or {kind: conductor}
    transport: {drift_velocity: nest, diffusion_longitudinal_cm2_s: 25.0, diffusion_transverse_cm2_s: 55.0,
                extraction: nest}                                            # electrons in the liquid
  gas_xenon:
    ...
    transport: {drift_velocity_mm_us: 3.1, el_yield: monteiro2007}       # electrons in the gas gap (S2)
  ...                     # gas_xenon, ptfe, stainless_steel, copper, silica, aluminium, kovar
optics:                   # refractive indices, Rayleigh / absorption lengths, reflectivities; one value each (scans: --set)
  ...
```

Used by: Geant4 (through `xamssim/g4config.py`), the COMSOL generators (permittivities), xamssim (validation,
map hashes), the chain (densities; drift velocity and diffusion of the liquid for the drift map and drift). Every `material:` in `geometry.yaml` must exist here. Optics: [Optics](optics.md).

## Detector states — `config/states/<name>.yaml`

One operating condition of the detector.

| field | required | meaning |
|---|---|---|
| `detector` | yes | folder in `config/detectors/` (geometry of the detector this state describes) |
| `hv_case` | yes | key in `efield/cases.yaml`: anode, gate, cathode, screens, PMT and SiPM potentials |
| `liquid_level_mm` | yes | liquid level above the gate (must equal `liquid_level_mm` in `efield/cases.yaml`) |
| `pressure_bar` | | gas pressure (EL yield) |
| `electron_lifetime_us` | | electron lifetime in µs (drift; required for `drifted_electrons`), null if unknown |
| `sensors` | | e.g. `pmt_hv_v: {top: -1000, bottom: -1000}` |
| `description` | | free text |

Existing: `sept` (SR-2026.2), `cmb50` (short-fill CM-B with −50 V SiPM margin), `cmb50_a36` (cmb50 with the anode at
+3.6 kV: extraction 0.23 instead of ≈ 0), `refa` (short-fill REF-a).

## HV cases — `efield/cases.yaml`

Electrode voltages per case (`A`, `G`, `C`, `BS`, `TS`, `PMT_T`, `PMT_B`, `SIPM`, in V), the field-cage resistor
chain, the SiPM model and which field maps to export. Shared by the states and the COMSOL models — see
[Electric field](efield.md).

## Sources — `config/sources/<name>.yaml`

| field | meaning |
|---|---|
| `isotope` | e.g. `Cs-137` (required; for `type: gamma` only a label) |
| `type` | `isotope` (default; Geant4 radioactive decay) or `gamma` |
| `energy_keV` | gamma energy (type `gamma`) |
| `position_mm` | `[x, y, z]` in the geometry frame; required for the particle mode, null if unknown |
| `direction` | `isotropic` (default) or `cone` (type `gamma` only) |
| `half_angle_deg`, `z_target_mm` | cone half angle and its target on the axis |
| `activity_bq`, `collimator`, `description` | bookkeeping (collimator not yet modelled) |

Existing: `cs137_raised`, `cs137_r130_cathode`, `cs137_r130_below`,
`cs137_vis_cone` (viewer).

## Simulation runs — `config/runs/<name>.yaml`

| field | required | meaning |
|---|---|---|
| `state` | yes | detector state |
| `source` | yes | source |
| `n_events` | yes | number of primaries (decays or gammas) |
| `seed` | yes | random seed |
| `stop_after` | | last product of the chain: `geant4_interactions`, `clustered_interactions`, `quanta`, `drifted_electrons`, `extracted_electrons`, `s2_photons`, `photoelectrons`, `events`, `raw_records` (default; digitizer output for amstrax) |
| `physics` | | options: `clustering`, `source_rate_hz`, lineage / DBSCAN cluster settings, `production_cut_mm` (list and defaults: [Simulation chain](chain.md#physics-options-run-file)) |

Unknown keys are rejected.

## Hashes and provenance

- **Provenance file:** every `xamssim chain` run writes `<data>/provenance/<run id>/<date-time>_<run key>_<x>.json`
  (not when the newest one has the same content): the run file, state, source and detector as resolved then (full
  geometry, materials, HV case), the chain settings incl. the lifetime, the maps used, the Geant4 config and output
  hash, every product with its lineage, and the code (commit, uncommitted changes). `xamssim show <run>` reads it;
  `--hash H` picks the entry that made a product (hash as in `xamssim list`), `--diff` lists what changed since in the
  configuration, `--full` prints all. Not removed by `xamssim list --delete`.

- **Map keys:** per kind of map (field, mesh cells, drift, extraction / EL, S1 light, S2 pattern) a 12-character hash of exactly
  the inputs that map depends on. Light maps do not depend on voltages, so all HV states share them; field maps differ
  per HV case. `xamssim maps --state <name>` lists them.
- **Run key:** a hash of the run, state, source and map keys, printed by `status` / `validate` and stored in the
  output (`config.json` → `xamssim.run_key`).

## The map registry — `<data>/maps/`

Generated maps (not in git) are listed in `<data>/maps/manifest.json` with their key, files, producer and version. The
registry never starts a slow producer (COMSOL, optical scans); for a missing map it prints the command.

| kind | made by | file | needs |
|---|---|---|---|
| `field` | `efield/comsol/run.sh --states <s>` + `xamssim maps --state <s> --export field` | `field/<key>/efield_xyz.npz` | COMSOL licence |
| `mesh_cells` | `efield/comsol/run_cell.sh gate` and `cathode --states <s>` + `--export cells` | `mesh_cells/<key>/cells.npz` | COMSOL licence |
| `drift` | `xamssim maps --state <s> --export drift` (composite field, ~30 s) | `drift/<key>/drift_xyz.npz` | field + mesh_cells |
| `extraction_el` | `efield/comsol/run_cell.sh stack --states <s>` + `xamssim maps --state <s> --export el` | `extraction_el/<key>/el.npz` | COMSOL licence |
| `s1_light`, `s2_pattern` | `xamssim maps --state <s> --export light` (Geant4 optical, ~5 min) | `s1_light/<key>/s1.npz`, `s2_pattern/<key>/s2.npz` | Geant4 build |

`xamssim maps --state <s>` shows which exist for a state and the command for each missing one.
