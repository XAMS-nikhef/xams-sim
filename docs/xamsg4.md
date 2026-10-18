# `xamsg4` reference

The Geant4 program (`g4/`, built to `g4/build/xamsg4`). Normally started through `xamssim` (which runs it in the
`g4` env); called directly it must run inside `conda activate g4`, from `g4/build/` when macros are given by name.

```
xamsg4 [-m optical|particle] -c config.json [-o out.bin] [-s seed] [-d] [-v] [macro.mac]
```

| option | meaning |
|---|---|
| `-m` | mode: `optical` (default) or `particle` |
| `-c` | config (`config.json` from `xamssim/g4config.py`; for particle mode written by `xamssim particle`) |
| `-o` | output file (optical: `.bin` + `.bin.summary.json` + `.bin.volumes.json`; particle: `.bin`, `.events.bin`, `.json`) |
| `-s` | random seed |
| `-d` | optical mode: records only for detected photons |
| `-v` | allow visualisation in batch mode |
| macro | batch macro; without it an interactive Qt session opens (`vis_interactive.mac` / `vis_particle.mac`) |

## Modes

| | optical | particle |
|---|---|---|
| physics | Geant4 optical physics (boundary processes, absorption, Rayleigh); scintillation and Cherenkov off | EM option 4, decay, radioactive decay; neutrinos and optical photons killed |
| primaries | one 178 nm photon per event from the source shape (macro commands below) | config `source`: ion at rest in a capsule (radioactive decay) or a gamma |
| output | one record per photon | one record per energy deposit in xenon + one per event |
| PMT bodies, frames, dead crosses | perfect absorbers | Kovar / steel (from `materials.yaml`) |
| world | ±160 × ±160 × ±260 mm (both vessels), absorbing | ±300 mm or larger (config `world_half_mm`), vacuum |

## Macro commands

Optical mode, source (`/xamsg4/source/...`):

| command | meaning |
|---|---|
| `shape s2` | uniform in the gas gap (liquid surface to just below the anode foil), r < rmax |
| `shape s1` | uniform in the drift region (just above the cathode to just below the gate), r < rmax |
| `shape cylinder` | uniform in a cylinder (rmax, zmin, zmax) on the axis |
| `shape point` | at `position` |
| `shape beam`, `beam_disc` | from `position` in `direction` (disc of radius rmax for `beam_disc`); tests |
| `rmax`, `zmin`, `zmax`, `position`, `direction` | parameters (lengths with unit, e.g. `30 mm`) |

Both modes: `/xamsg4/section <file> <xz|yz|xy> <offset> <u_min> <u_max> <v_min> <v_max> <step>` (mm) writes the
volume at every grid point (exact cross sections; `xamssim/section.py` draws them). Standard Geant4 commands
(`/run/beamOn`, `/tracking/verbose`, `/vis/...`) work as usual.

## Config keys read by the program

| key | meaning |
|---|---|
| `geometry_mode` | `xams` (default) or a test geometry: `test_box`, `test_interface`, `test_mesh`, `test_surface` (used by the checks) |
| geometry sections | as in `geometry.yaml` (copied by `xamssim/g4config.py`), plus `liquid.surface_z_mm` |
| `materials` | densities, temperatures, pressures, NIST names, compositions (from `materials.yaml`) |
| `optics` | one value per optical parameter (from `materials.yaml`, free ones at mid-range unless set) |
| `surfaces` | `0`: PTFE, steel and copper black (a check) |
| `source` | particle mode: `type`, `Z`, `A`, `energy_keV`, `position_mm`, `direction`, `half_angle_deg`, `z_target_mm`, `capsule` |
| `world_half_mm` | `[x, y, z]` half sizes of the world |
| `particle.production_cut_mm` | particle mode production cut |
| `test_*` | parameters of the test geometries |

## Source code (`g4/`)

| file | content |
|---|---|
| `xamsg4.cc` | main program: options, mode selection, run manager |
| `src/XamsGeometry.cc` | the XAMS geometry from the config (meshes with holes, rings, PTFE, PMTs, SiPMs, bucket, both cryostat vessels with flanges, source capsule) |
| `src/DetectorConstruction.cc` | materials (from the config), optical surfaces, test geometries |
| `src/PrimaryGeneratorAction.cc`, `src/PhotonActions.cc`, `src/Output.cc`, `src/PhysicsList.cc` | optical mode: photon sources, per-photon bookkeeping and output, optical physics |
| `src/ParticleMode.cc` | particle mode: physics list, source, stacking / tracking / stepping / event actions, deposit output |
| `src/Config.cc` | JSON config reader (`Num`, `Str` with `/`-separated paths, array indices) |
| `src/SectionScan.cc` | `/xamsg4/section` |
| `macros/` | viewers, checks, scan template (`production.mac`), cross sections |
