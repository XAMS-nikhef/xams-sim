# Installation

## Two conda environments

| env | contents | used for |
|---|---|---|
| **`xamssim`** | Python 3.12, strax 2.2.3, straxen 4.1.1, xenon-fuse 1.6.3, nestpy 2.0.6, amstrax + amstrax_files, matplotlib, MkDocs, the `xamssim` package | **everything you run**: all `xamssim` commands, the optical and efield tools, analysis, these docs |
| **`g4`** | Geant4 11.3.2 with its data files, Qt viewer, cmake, C++ compiler, nlohmann/json | **compiling** `xamsg4`; `xamsg4` also needs its libraries and data paths at run time |

You never activate `g4` to run anything: `xamssim/g4bin.py` starts `xamsg4` inside `g4` by itself
(`conda run -n g4`). Another env name for Geant4: set `XAMSSIM_G4_ENV`.

Why two: Geant4 brings its own compiler toolchain, Qt and C++ libraries; strax / fuse / amstrax pin their own numpy,
numba and Python versions. Kept apart, an update of one cannot break the other.

## Building `xamsg4`

```bash
conda activate g4 && cd ~/Documents/XAMS/xams-sim
cmake -S g4 -B g4/build && cmake --build g4/build -j8
```

- After editing C++ (`g4/src/`, `g4/include/`): `cmake --build g4/build -j8` (in `g4`).
- After adding a new `.cc` file or editing a macro in `g4/macros/`: rerun `cmake -S g4 -B g4/build` (the source list
  and the macro copies into `g4/build/` are made at configure time).
- After moving the repository: remove `g4/build/` and configure again (CMake keeps absolute paths).

## The `xamssim` environment

Created once (versions as tested; see `pyproject.toml`):

```bash
conda create -n xamssim python=3.12
conda activate xamssim
pip install "strax==2.2.3" "nestpy==2.0.6" "xenon-fuse==1.6.3" matplotlib plotly
pip install ~/Documents/XAMS/amstrax_files ~/Documents/XAMS/amstrax
cd ~/Documents/XAMS/xams-sim && pip install -e ".[test]" && pip install -r requirements-docs.txt
```

`nestpy` must stay below 2.1 (fuse 1.6.3 uses `nestpy.VDetector`, removed in 2.1). The editable install means
changes to `xamssim/` take effect without reinstalling.

## Checking the installation

```bash
conda activate xamssim && cd ~/Documents/XAMS/xams-sim
python -m pytest tests                  # Python package
python optical/check_step1.py           # Geant4 optical mode (prints PASSED)
xamssim particle config/runs/s2_cs137_raised.yaml --events 20000 --out /tmp/xamssim_test   # particle mode
```
