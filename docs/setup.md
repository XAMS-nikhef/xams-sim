# Installation

A complete installation from scratch, in order. Tested on macOS (Apple Silicon, arm64); on Linux the same conda
commands work. Paths below assume the workspace `~/Documents/XAMS/`.

## Overview: two conda environments

| env | contents | used for |
|---|---|---|
| **`g4`** | Geant4 11.3 with its data files, Qt viewer, cmake, C++ compiler, nlohmann/json | **compiling** `xamsg4`; `xamsg4` also needs its libraries and data paths at run time |
| **`xamssim`** | Python 3.12, strax 2.2.3, straxen 4.1.1, xenon-fuse 1.6.3, nestpy 2.0.6, amstrax + amstrax_files, matplotlib, plotly, MkDocs, the `xamssim` package | **everything you run**: all `xamssim` commands, the optical and efield tools, analysis, these docs |

You never activate `g4` to run anything: `xamssim/g4bin.py` starts `xamsg4` inside `g4` by itself
(`conda run -n g4`). Another env name for Geant4: set `XAMSSIM_G4_ENV`. Why two: Geant4 brings its own compiler
toolchain, Qt and C++ libraries; strax / fuse / amstrax pin their own numpy, numba and Python versions. Kept apart, an
update of one cannot break the other.

## Step 1 — prerequisites

- **conda**: Miniconda or Miniforge (`conda --version`). Miniconda's default channel is fine: every command below asks
  for `conda-forge` explicitly where it matters.
- **git** and access to the private repository `XAMS-nikhef/xams-sim` (GitHub organisation XAMS-nikhef).
- Disk: ~2 GB for the `g4` env (Geant4 data sets), ~1 GB for `xamssim`, plus simulation output in `xams-sim/run/`.
- Optional: COMSOL 6.2 with a licence, only for the electric-field models (step 7).

## Step 2 — the repositories

```bash
cd ~/Documents/XAMS
git clone https://github.com/XAMS-nikhef/xams-sim.git
git clone https://github.com/XAMS-nikhef/amstrax.git          # processing (used by the chain after raw_records)
git clone https://github.com/XAMS-nikhef/amstrax_files.git    # its auxiliary files
```

## Step 3 — the `g4` environment (Geant4)

Geant4 comes from conda-forge, with its physics data sets, the Qt viewer and a C++ toolchain as dependencies:

```bash
conda create -n g4 -c conda-forge geant4=11.3 cmake cxx-compiler nlohmann_json
conda activate g4
geant4-config --version                 # 11.3.x
geant4-config --has-feature qt          # yes  (Qt viewer)
geant4-config --has-feature gdml        # yes
echo $G4LEDATA                          # .../envs/g4/share/Geant4/data/EMLOW...  (set on activation)
```

- The physics data sets (`G4EMLOW`, `PhotonEvaporation`, `RadioactiveDecay`, `G4ENSDFSTATE`, …) are separate conda
  packages (`geant4-data-*`) pulled in by `geant4`. Their paths (`G4LEDATA`, `G4LEVELGAMMADATA`,
  `G4RADIOACTIVEDATA`, …) are set by the scripts in `envs/g4/etc/conda/activate.d/` when the env is activated —
  which is why `xamsg4` must run inside this env (`g4bin` takes care of it).
- `cmake` and `cxx-compiler` build `xamsg4`; `nlohmann_json` is the header-only JSON library of its config reader.
- For reference, how the existing env on the lab Mac was made (its `conda-meta/history`): `conda create -n g4 geant4
  -c conda-forge`, then `conda install -c conda-forge root` (not needed by xams-sim; it brought `nlohmann_json`
  along), `cmake`, and `ipywidgets` (not needed). Versions there: Geant4 11.3.2, cmake 4.0.2, clang 18,
  nlohmann_json 3.11.3, Python 3.13.

## Step 4 — building `xamsg4`

```bash
conda activate g4 && cd ~/Documents/XAMS/xams-sim
cmake -S g4 -B g4/build && cmake --build g4/build -j8
ls g4/build/xamsg4 g4/build/*.mac       # the program and its macros
```

- After editing C++ (`g4/src/`, `g4/include/`): `cmake --build g4/build -j8` (in `g4`).
- After adding a new `.cc` file or editing a macro in `g4/macros/`: rerun `cmake -S g4 -B g4/build` (the source list
  and the macro copies into `g4/build/` are made at configure time).
- After moving the repository: remove `g4/build/` and configure again (CMake keeps absolute paths).
- Quick test inside `g4`: `cd g4/build && ./xamsg4 -c <config.json> -o /tmp/t.bin init_only.mac`.

## Step 5 — the `xamssim` environment

```bash
conda create -n xamssim python=3.12
conda activate xamssim
pip install "strax==2.2.3" "nestpy==2.0.6" "xenon-fuse==1.6.3" matplotlib plotly
pip install ~/Documents/XAMS/amstrax_files ~/Documents/XAMS/amstrax
cd ~/Documents/XAMS/xams-sim && pip install -e ".[test]" && pip install -r requirements-docs.txt
xamssim --version
```

- `nestpy` must stay below 2.1 (fuse 1.6.3 uses `nestpy.VDetector`, removed in 2.1).
- xenon-fuse pulls in straxen 4.1.1 and utilix; utilix warns that `~/.xenon_config` is missing — harmless (no XENON
  database is used).
- The editable install (`-e`) means changes to `xamssim/` take effect without reinstalling.

## Step 6 — checking the installation

```bash
conda activate xamssim && cd ~/Documents/XAMS/xams-sim
python -m pytest tests                                   # Python package (all pass)
python optical/check_step1.py                            # optical mode via g4bin: STEP 1 CHECK PASSED
xamssim particle config/runs/s2_cs137_raised.yaml --events 20000 --out /tmp/xamssim_test   # particle mode
xamssim optical optical/scans/fit_s2.yaml --vis         # the viewer opens (Qt window)
mkdocs serve                                             # this manual at http://127.0.0.1:8000
```

## Step 7 — COMSOL (optional, electric field)

- COMSOL 6.2 at `/Applications/COMSOL62` (elsewhere: `export COMSOL=/path/to/Multiphysics/bin/comsol`), licensed
  (on the lab Mac via the UvA network licence server, which must be reachable).
- No COMSOL configuration is needed: the scripts generate the models, `comsol batch` solves them. Only the 3D SiPM
  box exports need *Preferences → Security → File system access: All files* (see [Electric field](efield.md)).
- Check without solving: `python efield/comsol/make_model.py --cases cmb50` (writes the Java model to
  `efield/comsol/build/`). A real solve (`efield/comsol/run.sh --cases …`, ~1.5 min) rewrites the files in
  `results/efield/comsol/`, so pass all the cases you want to keep.

## Updating

- Code: `git pull` in `xams-sim` (and `amstrax`, `amstrax_files`); after C++ changes rebuild (step 4).
- Python packages: keep the pinned versions (step 5) unless the roadmap says otherwise; amstrax after a pull:
  `pip install ~/Documents/XAMS/amstrax` in `xamssim`.
