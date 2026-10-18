# `xamssim` reference

The Python package (`xamssim/`, installed editable in the `xamssim` env) and its command.

## Command line

| command | does |
|---|---|
| `xamssim particle <run> [--events N] [--seed S] [--out DIR] [--dry-run] [--vis]` | [particle mode](particle.md) |
| `xamssim optical <scan.yaml> [--jobs N] [--dry]` | [optical scan](optical.md) |
| `xamssim optical --vis [--state S \| --level L]` | optical [viewer](viewers.md) |
| `xamssim status <run>` | resolved run: state, voltages, level, pressure, lifetime, source, geometry version, map keys and status |
| `xamssim maps --state <state>` | map keys and status of a state |
| `xamssim validate <run> [...]` | check run files and everything they refer to |
| `xamssim --version` | version |

Exit code 2 and a one-line message for configuration errors.

## Modules

| module | content |
|---|---|
| `config.py` | `resolve(run)` → `Resolved` (run, state, source, geometry, materials, HV case); schema checks; `load_materials_and_geometry()` (material references); `short_hash`; `Resolved.map_inputs()` / `map_keys()` / `run_key()`; `resolve_state(name)`; `PRODUCTS` (chain products in order) |
| `maps.py` | map registry: `KINDS` (producer, command, plan step, first product that needs it), `status(res)`, `needed(stop_after)`, `register(res, kind, files)`, `find(kind, key)`; `maps/manifest.json` |
| `g4bin.py` | `command(args)` / `run(args)`: start `xamsg4` from any env (directly in `g4`, else `conda run -n g4`); `XAMSG4`, `BUILD`, `G4_ENV` |
| `particle.py` | `run(run, ...)` production, `vis(run)` viewer, `build(...)` config.json + run.mac, `source_config(res)`, `isotope_za(name)` |
| `optical.py` | `scan(file, jobs, dry)`, `vis(state, level)` |
| `g4io.py` | `read(path, mmap=False)` → header, deposits, events; `names(h, table, codes)`; `code(h, table, name)` |
| `cli.py` | the command line |

## Tests

```bash
python -m pytest tests
```

`tests/test_config.py`: every run and state resolves; map keys depend only on their inputs; bad runs are rejected;
needed maps per product; registry; materials single source. `tests/test_g4.py`: isotope parsing, source checks,
reader round trip and record sizes (46 / 28 bytes), the launcher wraps `conda run` outside the `g4` env.
