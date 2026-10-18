# Configuration

Everything that describes the detector and a simulation lives in `config/` (plus the HV cases in `efield/cases.yaml`).
Every kind of information has exactly one place:

```
config/runs/<run>.yaml ─┬─ state ──► config/states/<state>.yaml ── hv_case ──► efield/cases.yaml (voltages, field cage, SiPMs)
                        ├─ source ─► config/sources/<source>.yaml
                        ├─ config/geometry.yaml   (dimensions; which part is which material)
                        └─ config/materials.yaml  (all material properties incl. optics)
```

`xamssim validate <run>` loads and checks all of it; `xamssim status <run>` shows the result.

## `geometry.yaml` — dimensions

Shapes and positions of every part, each value with its source (drawings in `reference/XAMS design/`, thesis,
position reconstruction, the user). Units mm and degrees; z = 0 at the gate foil, z up; x along the edge of the
top-PMT anode sectors. Sections:

| section | content |
|---|---|
| `liquid` | liquid-level scenarios above the gate |
| `mesh_common`, `meshes` | the five etched meshes (foil, holes `mesh_holes.json`, pitch, rings; z, angle, foil side per mesh), `material` |
| `ptfe_cylinder`, `field_shaping_rings` | inner PTFE cylinder, copper rings (z of each ring), `material` |
| `pmt_ptfe`, `ptfe_bucket`, `cryostat_vessel` | PMT holders, bucket (its weir sets the liquid level), steel vessel, `material` |
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
  ...                     # gas_xenon, ptfe, stainless_steel, copper, silica, aluminium, kovar
optics:                   # refractive indices, Rayleigh / absorption lengths, reflectivities; a range = free parameter
  ...
```

Used by: Geant4 (through `optical/make_config.py`), the COMSOL generators (permittivities), xamssim (validation,
map hashes), fuse settings (densities). Every `material:` in `geometry.yaml` must exist here. Optics: [Optics](optics.md).

## Detector states — `config/states/<name>.yaml`

One operating condition of the detector.

| field | required | meaning |
|---|---|---|
| `hv_case` | yes | key in `efield/cases.yaml`: anode, gate, cathode, screens, PMT and SiPM potentials |
| `liquid_level_mm` | yes | liquid level above the gate (must equal `liquid_level_mm` in `efield/cases.yaml`) |
| `pressure_bar` | | gas pressure (EL yield) |
| `electron_lifetime_us` | | electron lifetime (drift), null if unknown |
| `sensors` | | e.g. `pmt_hv_v: {top: -1000, bottom: -1000}` |
| `description` | | free text |

Existing: `sept` (SR-2026.2), `cmb50` (short-fill CM-B with −50 V SiPM margin), `refa` (short-fill REF-a).

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

Existing: `cs137_raised`, `cs137_sept` (position unknown), `cs137_r100_cathode`, `cs137_r100_below`,
`cs137_vis_cone` (viewer).

## Simulation runs — `config/runs/<name>.yaml`

| field | required | meaning |
|---|---|---|
| `state` | yes | detector state |
| `source` | yes | source |
| `n_events` | yes | number of primaries (decays or gammas) |
| `seed` | yes | random seed |
| `stop_after` | | last product of the chain: `geant4_interactions`, `clustered_interactions`, `quanta`, `drifted_electrons`, `extracted_electrons`, `s2_photons`, `photoelectrons`, `raw_records` (default) |
| `physics` | | options, e.g. `clustering: lineage`, `production_cut_mm: 0.1` |

Unknown keys are rejected.

## Hashes and provenance

- **Map keys:** per kind of map (field, drift, extraction / EL, S1 light, S2 pattern) a 12-character hash of exactly
  the inputs that map depends on. Light maps do not depend on voltages, so all HV states share them; field maps differ
  per HV case. `xamssim maps --state <name>` lists them.
- **Run key:** a hash of the run, state, source and map keys, printed by `status` / `validate` and stored in the
  output (`config.json` → `xamssim.run_key`).

## The map registry — `maps/`

Generated maps (not in git) are listed in `maps/manifest.json` with their key, files, producer and version. The
registry never starts a slow producer (COMSOL, optical scans); for a missing map it prints the command. The export
of maps into the registry comes with the chain steps (field and drift S4, extraction S5, light S6).
