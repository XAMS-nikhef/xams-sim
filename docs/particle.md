# Particle mode

Radioactive sources or gammas through the full XAMS geometry; every energy deposit in the xenon is written out. This
is the start of the event chain (the clustering, NEST and drift steps read these deposits).

```bash
xamssim particle config/runs/<run>.yaml [--events N] [--seed S] [--out DIR] [--dry-run]
```

| option | meaning |
|---|---|
| `--events N` | number of primaries (default: `n_events` of the run) |
| `--seed S` | random seed (default: `seed` of the run) |
| `--out DIR` | output folder (default `run/g4/<run name>/`) |
| `--dry-run` | write `config.json` and `run.mac`, print the command, do not run Geant4 |
| `--vis` | interactive viewer instead of a production run ([viewers](viewers.md)) |

What happens: the run is resolved (state, source, geometry, materials); `optical/make_config.py` writes the
geometry / materials part of `config.json` for the liquid level of the state; the source, `mode: particle`, the world
size and run metadata are added; `run.mac` initialises and starts N events; `xamsg4 -m particle` runs in the `g4`
env; its log goes to `g4.log`. Speed on the Mac: 2·10⁶ Cs-137 decays in ~35 s.

## Files

| file | content |
|---|---|
| `deposits.bin` | one record per Geant4 step with energy deposit in liquid or gas xenon |
| `deposits.events.bin` | one record per event (also events without deposits) |
| `deposits.json` | header: record layouts, units, code → name tables, full config, seed, counts |
| `config.json`, `run.mac`, `g4.log` | what was run |

Record layouts and reading: [Output formats](output.md), [Reading the output](analysis.md).

## Sources

From `config/sources/<name>.yaml` ([configuration](configuration.md#sources-configsourcesnameyaml)):

- **`type: isotope`** — an ion (Z, A from the isotope name) at rest at `position_mm`, decayed by Geant4's radioactive
  decay with the full chain (Cs-137 → e⁻ + Ba-137m → 662 keV γ or conversion electrons + X-rays). All decay products
  get time 0 (the 30-year Cs-137 and 2.55-min Ba-137m decay times would otherwise ruin the ns precision). The ion sits
  in a **source capsule**: a steel sphere of 1 mm radius (config `source/capsule/{material,radius_mm}`), which stops
  the decay recoil and most betas, as the real holder does. The capsule is only placed outside the vessel.
- **`type: gamma`** — one gamma of `energy_keV`, isotropic or in a cone towards a point on the axis (useful for the
  viewer and for fast checks: isotropic decays at 10 cm mostly miss the TPC).

## Physics and materials

- Geant4 EM physics option 4 (accurate low-energy photon and electron physics), decay and radioactive decay; the
  long-lifetime threshold of Geant4 ≥ 11.2 is lifted so that Cs-137 decays. Production cut 0.1 mm (run option
  `physics: {production_cut_mm: ...}`).
- Neutrinos and optical photons are not tracked.
- Materials from `materials.yaml`; in particle mode the PMT bodies and frames are Kovar and the mesh dead crosses are
  steel (in optical mode both are perfect absorbers).
- The world is ±300 mm (or larger to contain the source) and **vacuum** outside the vessel: no outer cryostat, no lab.

## Positions and frames

Records are in the geometry frame (mm, z = 0 at the gate). The data frame of the position reconstruction is mirrored
in x (x_data = −x_sim).
