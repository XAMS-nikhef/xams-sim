# `xamssim` reference

The Python package (`xamssim/`, installed editable in the `xamssim` env) and its command.

## Command line

| command | does |
|---|---|
| `xamssim particle <run> [--events N] [--seed S] [--out DIR] [--dry-run] [--vis]` | [particle mode](particle.md) |
| `xamssim optical <scan.yaml> [--jobs N] [--dry]` | [optical scan](optical.md) |
| `xamssim optical <scan.yaml> --vis [--point N]` | optical [viewer](viewers.md) for point N of the scan |
| `xamssim optical <scan.yaml> --list` | the scan points: number and parameter values |
| `xamssim chain <run> [--target T] [--g4 DIR]` | [simulation chain](chain.md) on the Geant4 output: clusters, field, NEST quanta, drift to the surface, extraction and EL → `<data>/strax/` |
| `xamssim status <run>` | resolved run: state, voltages, level, pressure, lifetime, source, geometry version, map keys and status |
| `xamssim maps --state <state>` | map keys and status of a state |
| `xamssim maps --state <state> --make [--dry-run]` | make all missing maps of the state in dependency order (field, mesh cells, drift, EL, light) with the commands the status shows; stops at the first failure (COMSOL steps need the licence server) |
| `xamssim maps --state <state> --export field` | COMSOL field of the state's HV case → `<data>/maps/field/<key>/` (registered) |
| `xamssim maps --state <state> --export cells` | gate and cathode mesh-cell fields from the solved cell models → `<data>/maps/mesh_cells/<key>/` |
| `xamssim maps --state <state> --export el` | extraction / EL map from the gate + anode cell model → `<data>/maps/extraction_el/<key>/` |
| `xamssim maps --state <state> --export drift` | drift map of the state in its composite field → `<data>/maps/drift/<key>/` |
| `xamssim validate <run> [...]` | check run files and everything they refer to |
| `xamssim --version` | version |

Exit code 2 and a one-line message for configuration errors.

## Modules

| module | content |
|---|---|
| `config.py` | `resolve(run)` → `Resolved` (run, state, source, geometry, materials, HV case); schema checks; `load_materials_and_geometry()` (material references); `short_hash`; `Resolved.map_inputs()` / `map_keys()` / `run_key()`; `resolve_state(name)`; `PRODUCTS` (chain products in order) |
| `maps.py` | map registry: `KINDS` (producer, command, plan step, first product that needs it), `status(res)`, `needed(stop_after)`, `register(res, kind, files)`, `find(kind, key)`; `<data>/maps/manifest.json` |
| `g4bin.py` | `command(args)` / `run(args)`: start `xamsg4` from any env (directly in `g4`, else `conda run -n g4`); `XAMSG4`, `BUILD`, `G4_ENV` |
| `particle.py` | `run(run, ...)` production, `vis(run)` viewer, `build(...)` config.json + run.mac, `source_config(res)`, `isotope_za(name)` |
| `optical.py` | `scan(file, jobs, dry)`, `vis(file, point)` (same points as `run_scan.make_points`) |
| `chain.py` | `context(run, **overrides)` → (strax context, run id); `settings(res, g4_dir)`, `volumes(res)`, `physics(res)` (`PHYSICS_DEFAULTS`), `plugins(clustering)`, `run(run, target)`; `TARGETS` |
| `fieldmap.py` | `read_comsol(case, geometry)`: 3D field from the solved COMSOL model via `mph`; `export(res)` → registry; `path(res)`; `FieldMap` (interpolation in x, y, z); `grid_axes` |
| `plugins/field.py` | `XamsElectricField`: \|E\| at the cluster position from the 3D map (replaces fuse's (r, z) `ElectricField`) |
| `cellmap.py` | mesh-cell fields (gate, cathode quarter cells; the gate + anode stack for S5) from the solved cell models via `mph`: `read_cell`, `export(res)`, `path(res)` |
| `elmap.py` | extraction / EL map: `compute(res)` / `export(res)` (gas tracking in the stack cell, NEST extraction, Monteiro EL), `extraction_table`, `gas_model`, `ELMap`, `path(res)` |
| `plugins/extraction.py` | `XamsExtractionEL`: extracted electrons, S2 photons, S2 time and width per cluster |
| `driftmap.py` | drift map: `compute(res)` / `export(res)` (tracking against the composite field: full TPC + mesh cells, NEST v(E)), `track`, `CODES`, `DriftMap` (look-up, `.at` with sub-grid shifts), `path(res)` |
| `plugins/drift.py` | `XamsElectronDrift`: electrons at the surface, drift time and spread, gate position |
| `plugins/volumes.py` | `XamsVolumeProperties` (regions from the drift map; surface and field-cage radius), `XamsVolumeSelection` (keeps volumes 1–4), `XAMS_VOLUME_IDS`, `VOLUME_NAMES` |
| `plugins/input.py` | `XamsG4Input` (fuse ChunkInput with our reader), `XamsG4Loader`, `deposits_frame(path)`; `plugins/__init__.py`: `np.in1d` shim for fuse |
| `g4config.py` | geometry.yaml + materials.yaml (+ level, overrides) → `config.json` for `xamsg4` (both modes); `python -m xamssim.g4config` |
| `run_scan.py`, `scan_data.py`, `read_output.py` | optical scans: runner (`make_points`), reader of a whole scan (`load`, `top_fraction`), reader of one photon file (`read`, `summary`) |
| `section.py` | draws the exact cross sections written by `/xamsg4/section`; `python -m xamssim.section` |
| `g4io.py` | `read(path, mmap=False)` → header, deposits, events; `names(h, table, codes)`; `code(h, table, name)`; `output_hash(path)` (content hash for the lineage) |
| `cli.py` | the command line |

## Tests

```bash
python -m pytest tests
```

`tests/test_config.py`: every run and state resolves; map keys depend only on their inputs; bad runs are rejected;
needed maps per product; registry; materials single source. `tests/test_g4.py`: isotope parsing, source checks,
reader round trip and record sizes (46 / 28 bytes), the launcher wraps `conda run` outside the `g4` env.
`tests/test_chain.py`: input translation (cm, names, process alias, event selection), 3D field-map interpolation
(x matters, not only r; edge), volumes and physics options from the configuration, a 6-event run through fuse up to the quanta
(one event per volume, one outside the field cage).
