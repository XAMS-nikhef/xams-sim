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

`--target` is the last product: `geant4_interactions`, `clustered_interactions` or `quanta`. Without it the chain
stops at the run's `stop_after`, or at the last product implemented so far. `--g4 DIR` reads Geant4 output from
somewhere other than `<data>/g4/<run name>/`.

## Plugins

| product (strax data type) | plugin | does |
|---|---|---|
| `geant4_interactions` | `XamsG4Input` (`xamssim/plugins/input.py`) | reads `deposits.*` and builds fuse's input table; events on a timeline at `source_rate_hz` |
| `clustered_interactions` | fuse `LineageClustering` + `MergeLineage` (or `FindCluster` + `MergeCluster`) | groups deposits into clusters, each with one NEST interaction type |
| `volume_properties`, `interactions_in_roi` | `XamsVolumeProperties`, `XamsVolumeSelection` (`xamssim/plugins/volumes.py`), fuse `DefaultSimulation` | volume of each cluster, its xenon density and whether its electrons are kept; clusters outside the volumes are dropped |
| `electric_field_values` | `XamsElectricField` (`xamssim/plugins/field.py`) | \|E\| at the cluster position (x, y, z) from the state's 3D field map |
| `quanta` | fuse `NestYields` | NEST photons / electrons / excitons with the local field and density |
| `microphysics_summary` | fuse `MicroPhysicsSummary` | all of the above in one table per cluster |

The input plugin changes only the reading: positions mm → cm, the particle and process codes back to names, and the
Geant4 11 process name `RadioactiveDecay` → `RadioactiveDecayBase` (the name fuse's lineage clustering looks for).

## Settings from the configuration

| option | value | from |
|---|---|---|
| `z_gate_cm`, `z_cathode_cm` | gate and cathode mesh z | `geometry.yaml` (`meshes`) |
| `z_liquid_cm` | gate z + liquid level | state (`liquid_level_mm`) |
| `z_bottom_pmt_cm`, `z_top_pmt_cm` | PMT window z | `geometry.yaml` (`pmts`) |
| `r_field_cage_cm` | inner radius of the PTFE cylinder (3.1 cm) | `geometry.yaml` (`ptfe_cylinder`) |
| `density_liquid_g_cm3`, `density_gas_g_cm3` | liquid / gas xenon density | `materials.yaml` |
| `xams_efield_map` | `<data>/maps/field/<key>/efield_xyz.npz` | map registry, state's field key |
| `nest_er_yields_parameters`, `nest_nr_yields_parameters`, `nest_width_parameters` | `-1`, `-1`, `{}` (NEST defaults) | fixed |
| clustering, `source_rate` | run file `physics` block | below |

Four volumes, all with r < 3.1 cm (`XamsVolumeProperties`; fuse's own volume plugins are not used: they know three
volumes, named after XENONnT, and keep two). Ids 1–3 are the ids fuse uses, so fuse plugins downstream read them as
usual.

| volume (`vol_id`) | z range | density | electrons kept |
|---|---|---|---|
| 1 drift region | cathode → gate | liquid | yes |
| 2 below cathode | bottom PMT window → cathode | liquid | no (light only) |
| 3 gas | liquid surface → top PMT window | gas | yes |
| 4 above gate | gate → liquid surface | liquid | yes |

"Electrons kept" means NEST electrons are passed on; for clusters above the gate and in the gas the later steps (drift,
extraction, EL) decide what they give. Xenon outside the field cage (r ≥ 3.1 cm) is in no volume: those clusters are
dropped.

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

The full model has the meshes as solid discs: within a few mm of a mesh the real field (holes) comes from the
mesh-cell models (later step). The map is registered under the state's field key (geometry, HV, level,
permittivities), so states with the same inputs share it and any change of an input asks for a new one.

## Output and reading it

strax data in `<data>/strax/`, run id = the run key (`xamssim status <run>`). The stored data depend on the plugin
settings (strax lineage), so changing an option and rerunning gives new data next to the old.

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
