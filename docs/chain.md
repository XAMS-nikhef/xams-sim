# Simulation chain

The event chain after Geant4: energy deposits → clusters → quanta (photons, electrons) per cluster. It runs as a strax
context with the micro-physics plugins of [fuse](https://github.com/XENONnT/fuse) and our own input plugin; every
setting comes from the run file and what it points to. Later steps of the [roadmap](xams_sim_plan.md) (drift,
extraction, light, waveforms) add plugins to the same context.

```bash
xamssim particle config/runs/cs137_cmb50_001.yaml             # Geant4 first -> <data>/g4/cs137_cmb50_001/
xamssim maps --state cmb50 --export field                      # once per state: the field map (below)
xamssim chain config/runs/cs137_cmb50_001.yaml --target quanta # -> <data>/strax/
```

`--target` is the last product: `geant4_interactions`, `clustered_interactions`, `quanta`, `drifted_electrons` or
`extracted_electrons` (= `s2_photons`). Without it the chain
stops at the run's `stop_after`, or at the last product implemented so far. `--g4 DIR` reads Geant4 output from
somewhere other than `<data>/g4/<run name>/` (e.g. the output of another run file with the same Geant4 settings).
`--lifetime-us T` sets the electron lifetime for a state without a measured one (it overrides the state and is part
of the lineage).

## Plugins

| product (strax data type) | plugin | does |
|---|---|---|
| `geant4_interactions` | `XamsG4Input` (`xamssim/plugins/input.py`) | reads `deposits.*` and builds fuse's input table; events on a timeline at `source_rate_hz` |
| `clustered_interactions` | fuse `LineageClustering` + `MergeLineage` (or `FindCluster` + `MergeCluster`) | groups deposits into clusters, each with one NEST interaction type |
| `volume_properties`, `interactions_in_roi` | `XamsVolumeProperties`, `XamsVolumeSelection` (`xamssim/plugins/volumes.py`), fuse `DefaultSimulation` | volume of each cluster (from the drift map) and its xenon density; clusters outside the volumes are dropped |
| `electric_field_values` | `XamsElectricField` (`xamssim/plugins/field.py`) | \|E\| at the cluster position (x, y, z) from the state's 3D field map |
| `drifted_electrons` | `XamsElectronDrift` (`xamssim/plugins/drift.py`) | electrons at the liquid surface (end point and lifetime from the drift map), drift time and its spread, position at the gate |
| `extracted_electrons` | `XamsExtractionEL` (`xamssim/plugins/extraction.py`) | extracted electrons, S2 (EL) photons, S2 time and width per cluster, from the extraction / EL map at the gate-hole position |
| `quanta` | fuse `NestYields` | NEST photons / electrons / excitons with the local field and density |
| `microphysics_summary` | fuse `MicroPhysicsSummary` | all of the above in one table per cluster |

The input plugin changes only the reading: positions mm → cm, the particle and process codes back to names, and the
Geant4 11 process name `RadioactiveDecay` → `RadioactiveDecayBase` (the name fuse's lineage clustering looks for).

## Settings from the configuration

| option | value | from |
|---|---|---|
| `z_liquid_cm` | gate z + liquid level (liquid / gas boundary) | `geometry.yaml` + state (`liquid_level_mm`) |
| `r_field_cage_cm` | inner radius of the PTFE cylinder (3.1 cm) | `geometry.yaml` (`ptfe_cylinder`) |
| `density_liquid_g_cm3`, `density_gas_g_cm3` | liquid / gas xenon density | `materials.yaml` |
| `xams_efield_map` | `<data>/maps/field/<key>/efield_xyz.npz` | map registry, state's field key |
| `xams_drift_map` | `<data>/maps/drift/<key>/drift_xyz.npz` | map registry, state's drift key |
| `electron_lifetime_us` | electron lifetime in the liquid | state (`electron_lifetime_us`; needed for `drifted_electrons`) |
| `diffusion_longitudinal_cm2_s`, `diffusion_transverse_cm2_s` | diffusion of electrons in the liquid | `materials.yaml` (`liquid_xenon.transport`) |
| `xams_el_map` | `<data>/maps/extraction_el/<key>/el.npz` | map registry, state's extraction / EL key (needed for `extracted_electrons`) |
| `gate_angle_deg`, `mesh_pitch_mm`, `z_anode_cm` | gate-hole lattice (anode aligned), anode position | `geometry.yaml` |
| `nest_er_yields_parameters`, `nest_nr_yields_parameters`, `nest_width_parameters` | `-1`, `-1`, `{}` (NEST defaults) | fixed |
| clustering, `source_rate` | run file `physics` block | below |

Four volumes inside the field cage (r < 3.1 cm), taken from the **drift map** of the state: where the electrons of a
cluster go decides its region (`XamsVolumeProperties`; fuse's own volume plugins, named after XENONnT, are not used).
Ids 1–3 are the ids fuse uses.

| volume (`vol_id`) | cluster in ... whose electrons ... | density |
|---|---|---|
| 1 drift region | the liquid; cross the gate to the surface, or end on the PTFE wall / a SiPM | liquid |
| 2 below cathode | the liquid; drift down to the bottom screen | liquid |
| 3 gas | the gas (above the surface) | gas |
| 4 above gate | the liquid; reach the surface without crossing the gate | liquid |

NEST makes electrons for every cluster; `XamsElectronDrift` decides how many reach the surface. Xenon outside the field
cage is in no volume: those clusters are dropped.

## Drift map and drift

```bash
xamssim maps --state sept --export cells                          # once per state: gate and cathode cell fields (licence)
xamssim maps --state sept --export drift                          # once per state, ~30 s, composite field
xamssim chain <run> --target drifted_electrons
```

The drift map is a look-up table made once per state (`xamssim/driftmap.py`, ~30 s): from every point of a
1 × 1 × 0.5 mm grid inside the field cage one test electron is moved against the **composite field** (0.1 mm steps,
0.02 mm within 1 mm of a mesh; drift velocity v(\|E\|) of the liquid from NEST) until it reaches the liquid surface
(`surface`), the bottom screen (`bottom`), the PTFE wall (`wall`), a SiPM opening (`sipm`) or a mesh bar (`mesh`);
points in the gas are `gas`. The composite field is the full-TPC 3D map (meshes as solid discs) with, near the gate
and the cathode, the field of the real etched mesh from the mesh-cell models (`xamssim maps --export cells`), tiled
over the mesh with its rotation and hole pattern: E = E_cell + (E_full − cell average), the bracket taken just outside
the foil. So the hole structure sits on top of the large-scale field, and focusing through the gate holes, the layer
above the cathode pulled down through its holes and losses on the bars follow from the field. Stored per point: end code, drift time to
the surface, where it crosses the gate, path length. In the chain each cluster takes the values of its grid point
(drift time and gate position shifted to the exact position): all electrons of a cluster follow the same field line;
lifetime (binomial with exp(−t/τ)) and diffusion (σ_t from D_L, σ_xy from D_T) act statistically. `drifted_electrons`:
`n_electron_interface`, `drift_time_mean`, `drift_time_spread` [ns], `x_obs`, `y_obs` (at the gate) [cm],
`xy_spread`, `drift_end`, `survival`. Not in the map: partial losses at the edges of a catchment area (a cluster's
electrons all end at the same place), time-dependent fields.

## Extraction and electroluminescence

```bash
xamssim maps --state sept --export el                             # once per state (gate + anode cell model, licence)
xamssim chain <run> --target extracted_electrons
```

The extraction / EL map (`xamssim/elmap.py`) comes from the stack cell model of the state (gate, liquid surface,
anode, top screen; real etched meshes, anode aligned with the gate). Electrons start on a 0.025 mm grid over one
quarter of a gate-hole cell just above the liquid surface and are tracked through the gas to the anode bars. Per
start point: the **extraction efficiency** from the field just below the surface (NEST `CalculateG2`, as a function
of the field just above it), the **EL photons per electron** along the path (140 E[kV/cm] − 116 p_eq[bar] per cm,
Monteiro et al. 2007; p_eq = the pressure at 293 K with the density of the gas), the **transit time** with the gas
drift velocity and the **emission-time quantiles** (5 … 95 % of the electron's light). `XamsExtractionEL` takes the
values at the cluster's gate crossing (`x_obs`, `y_obs` of `drifted_electrons` in the gate-hole lattice):
extracted = binomial(electrons at the surface, efficiency), S2 photons = Poisson(extracted × photons per electron),
S2 time = drift time + emission, `s2_width50` = 25–75 % of the cluster's light (EL profile and diffusion). Clusters
in the gas keep their electrons and emit the part of the path above them. Gas transport in `materials.yaml`
(`gas_xenon.transport`); the gas drift velocity is tuned on the measured S2 width (no measurement at ~9 Td found).

## Physics options (run file)

```yaml
physics:
  clustering: lineage            # lineage (default) | dbscan
  source_rate_hz: 100            # timeline of the events
  time_threshold_ns: 10          # lineage: new cluster after this time gap
  gamma_distance_threshold_cm: 0 # lineage: keep a gamma's deposits in one cluster within this distance
  brem_distance_threshold_cm: 0  # lineage: the same for bremsstrahlung
  micro_separation_cm: 0.005     # dbscan: cluster size
  micro_separation_time_ns: 10   # dbscan: time window
  production_cut_mm: 0.1         # Geant4 particle mode
```

Unknown keys are rejected. The values above are the defaults (`xamssim.chain.PHYSICS_DEFAULTS`).

## Field map

```bash
efield/comsol/run.sh --states sept                # solve the COMSOL model for the state's HV case (~2 min)
xamssim maps --state sept --export field          # 3D field from the solved model -> <data>/maps/field/<key>/ (~30 s)
```

The export opens the solved model (`efield/comsol/build/XAMS_efield.mph`) through COMSOL's own API (Python package
`mph`; needs the COMSOL licence), picks the solution of the state's HV case by its electrode voltages and evaluates V
and E on a 0.5 mm (x, y, z) grid: x, y ±36 mm, z from the bottom to the top PMT window, in the frame of
`geometry.yaml`. The file `efield_xyz.npz` holds the axes (mm), V (V) and Ex, Ey, Ez (V/cm). `XamsElectricField`
interpolates \|E\| trilinearly; positions outside the grid get the value at its edge.

The full model has the meshes as solid discs: within a few mm of the gate and the cathode the real field (holes)
comes from the mesh-cell models (composite field of the drift map, below). The map is registered under the state's field key (geometry, HV, level,
permittivities), so states with the same inputs share it and any change of an input asks for a new one.

## Output and reading it

strax data in `<data>/strax/`, run id = the name of the run file. Each product is stored under its lineage hash:
plugin versions and tracked settings, including `g4_output_hash` (a content hash of the Geant4 output: the config it
ran with incl. the xams-sim version, seed, counts; not file paths), the map files (their paths hold the map keys), the
lifetime and the transport constants. Changing an option or a map, or rerunning Geant4, makes new data for exactly the
steps it affects; the clustering is redone only when the Geant4 output or the clustering settings change. Keep run
file names unique (they also name the Geant4 output folder). When the run file now asks for another Geant4
configuration than the output was made with (`g4_key`: geometry, materials, level, source, events, seed), the chain
warns.

Pre-selection: only decays with a deposit inside the field-cage radius go to the clustering (`preselect_r_max_cm`);
nothing outside it can reach a volume.

```python
from xamssim import chain
st, run_id = chain.context("config/runs/cs137_cmb50_001.yaml")
s = st.get_array(run_id, "microphysics_summary")     # x, y, z [cm], ed [keV], nestid, vol_id, e_field, photons, electrons
c = st.get_array(run_id, ("clustered_interactions", "volume_properties"))   # all clusters, also outside the volumes
st2, _ = chain.context("config/runs/cs137_cmb50_001.yaml", time_threshold=100, entry_stop=100000)  # option overrides
```

## Notes

- fuse 1.6.3 calls `np.in1d`, removed in numpy 2.4. `xamssim.plugins` puts it back as `np.isin` when it is missing.
- fuse reads a whole Geant4 file into memory before it makes chunks (2 × 10⁶ Cs-137 decays, 6 × 10⁶ deposits: fine on
  a laptop). For much larger productions split the Geant4 run (`--events`, `--seed`, `--out`).
- The first chunk starts 10 ns before the first event (`first_chunk_left`). fuse's default (1 ms) gives a negative
  chunk start when the first event is earlier; 0 fails when MergeLineage's energy-weighted cluster time rounds 1 ns
  below the first deposit. Changing it changes the lineage: a notebook kernel started before such a change
  recomputes instead of loading (restart the kernel).
