# xams-sim — XAMS simulation

The program that simulates the XAMS TPC (repository `XAMS-nikhef/xams-sim`; until 2026-10-18 `acolijn/xams-optical-sim`,
last state of that layout: tag `optical-sim-final`). This repository holds the **program and the definition of the
detector**; studies made with it live in **`../simulations/`** (own repository), all outputs in **`../simulations/data/`**.

| Folder | What |
|---|---|
| `config/` | the definition: `geometry.yaml` (data frame; + `mesh_holes.json`), `materials.yaml`, detector `states/`, `sources/`; example `runs/` and `scans/` |
| `g4/` | Geant4 program `xamsg4` (particle and optical mode); build in `g4/build/` |
| `efield/` | electric field: COMSOL model generators (full TPC, mesh cells), `cases.yaml` (voltages only) |
| `checks/` | slow checks of Geant4's optical physics (need the g4 build) |
| `xamssim/` | Python package and command: configuration, Geant4 config writer and launcher, readers, optical scans, map registry, field maps, the simulation chain (strax / fuse plugins) |
| `tests/` | pytest |
| `docs/` | the manual (MkDocs: `mkdocs serve`) |
| `notes/` | explainer of the program, generated from the code (`python notes/make_overview_note.py`) |

## Environments and commands

Two conda envs: **`xamssim`** for everything you run, **`g4`** only to compile `xamsg4` (it is started in `g4`
automatically). Installation: `docs/setup.md`.

```bash
conda activate xamssim
xamssim particle config/runs/cs137_cmb50_001.yaml [--events N]   # Geant4 energy deposits -> <data>/g4/<run>/
xamssim chain    config/runs/cs137_cmb50_001.yaml --target quanta # clusters, field, NEST quanta -> <data>/strax/
xamssim optical  config/scans/example_s2.yaml [--jobs 8]          # optical scan -> <data>/scans/<scan>/
xamssim maps     --state sept --export field                      # 3D field map from the solved COMSOL model
xamssim status   config/runs/<run>.yaml                           # resolved run, input hashes, map status
python -m pytest tests
```

`<studies>` (run files `<study>/runs/*.yaml`, for `xamssim list`) = `$XAMSSIM_STUDIES`, else the folder that holds `<data>`.
`<data>` = `xamssim.config.DATA`: `$XAMSSIM_DATA`, else `../simulations/data` next to the code (development checkout). A shared installation without a simulations folder next to it (STBC: `software/xams-sim`) refuses to run without `$XAMSSIM_DATA`. Set it once in `~/.config/xamssim/env` (a line `XAMSSIM_DATA=/path`; read by xamssim itself, so every terminal, Jupyter kernel and condor job finds it; the environment wins).

Roadmap of the full chain: `docs/xams_sim_plan.md`.
