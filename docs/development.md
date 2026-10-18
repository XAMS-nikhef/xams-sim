# Development

## Repository layout

| path | content | edit? |
|---|---|---|
| `config/geometry.yaml`, `config/mesh_holes.json` | dimensions; the 456 etched mesh holes | geometry changes |
| `config/materials.yaml` | all material properties incl. optics | material / optics changes |
| `config/states/`, `config/sources/`, `config/runs/` | detector states, sources, simulation runs | yes, add your own |
| `efield/cases.yaml` | HV cases | yes |
| `g4/` | `xamsg4` (C++): `xamsg4.cc`, `src/`, `include/`, `macros/`, `CMakeLists.txt`; build in `g4/build/` (not in git) | new physics / parts |
| `optical/` | optical tools: `make_config.py`, `run_scan.py`, readers, checks, study scripts, `scans/`, `targets/`, `examples/` | scans: yes |
| `efield/comsol/` | COMSOL generators, run scripts, parsers, plots; build in `efield/comsol/build/` | yes |
| `xamssim/` | Python package (config, registry, launcher, particle, optical, reader, CLI) | yes |
| `tests/` | pytest | with every change |
| `validation/` | checks of the simulation against expectations / data | yes |
| `maps/` | generated maps + manifest (only the README in git) | — |
| `run/` | simulation output (not in git) | — |
| `results/`, `notes/` | results and PDF notes of studies (not part of this manual) | — |
| `docs/`, `mkdocs.yml` | this manual | yes |
| `xamssim_s0/` | the fuse read-through (S0 of the roadmap) | — |

## Adding things

- **A detector state:** `config/states/<name>.yaml` (fields in [configuration](configuration.md)); its `hv_case` in
  `efield/cases.yaml`. Check: `xamssim maps --state <name>`.
- **A source:** `config/sources/<name>.yaml`; then a run file pointing to it; `xamssim validate`.
- **A material:** `config/materials.yaml` (density, `geant4`, `electrical`), and reference it from `geometry.yaml`.
  The C++ reads NIST names and xenon properties from the config; a new kind of material also needs a function in
  `g4/src/DetectorConstruction.cc`.
- **A part of the geometry:** numbers in `geometry.yaml`, construction in `g4/src/XamsGeometry.cc`; then the
  [checks](validation.md), the field model if it matters electrically, and this manual.
- **A map kind:** `KINDS` and `Resolved.map_inputs()` (exactly the inputs it depends on) in `xamssim/`; a test.
- **A chain step (strax plugin):** per the [roadmap](xams_sim_plan.md); fuse plugins are used as a library
  (subclass to change, never fork), all settings from the configuration.

## Rules

- One source per kind of information (geometry, materials, HV cases); no numbers copied between files.
- No ROOT; binary records + JSON headers; maps `.npz` / HDF5 with a manifest.
- Every run and map carries its provenance (config, seed, code version, run key).
- When a roadmap step is done, update this manual in the same commit; results go into notes / `results/`, not here.

## Pitfalls

- `xamsg4` needs the `g4` env: run it through `xamssim` / `g4bin`, or directly only inside `conda activate g4`.
- After adding a `.cc` file or editing a macro: rerun `cmake -S g4 -B g4/build` (configure-time copies).
- After moving the repository: rebuild `g4/build/` from scratch (absolute paths in the CMake cache).
- Scans skip finished parts: after a geometry or code change move the old `run/scans/<name>/` away first.
- Optical `-d` output holds only detected photons; use `n_photons` / the tally for fractions of all photons.
- Particle-mode code tables are built per run: decode with the header of the same run.
- One frame: `geometry.yaml` (v5) is in the data frame; Geant4, COMSOL and the chain use it as is. Optical scans made
  with geometry v4 or older are mirrored in x (`config.json` → `meta.version`).
- Free optical parameters sit at the middle of their range unless set (`--set`, scan grid).
- `notes/make_note.py` needs reportlab (base conda Python).
- `nestpy` must stay below 2.1 for fuse 1.6.3.
