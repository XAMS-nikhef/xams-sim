# Setup

Two conda environments ([README](../README.md) "Environments and commands"):

- **`g4`** — Geant4 11.3.2 with its data files, Qt viewer, cmake, a C++ compiler, nlohmann/json: needed to **compile**
  the program `g4/build/xamsg4`, and by `xamsg4` at run time (libraries, data paths).
- **`xamssim`** — Python 3.12 with strax, fuse, nestpy, amstrax and the `xamssim` package: **everything you run**.
  `xamssim/g4bin.py` starts `xamsg4` inside `g4` by itself (`conda run -n g4`), so `g4` never has to be activated
  for running.

```bash
conda activate g4 && cd ~/Documents/XAMS/xams-sim
cmake -S g4 -B g4/build && cmake --build g4/build -j8
conda activate xamssim
```

- After editing C++ code (`g4/src/`, `g4/include/`): `cmake --build g4/build -j8`.
- After editing a macro in `g4/macros/`: `cp g4/macros/*.mac g4/build/` (or rerun `cmake -S g4 -B g4/build`, which copies them).
- Python analysis of existing output and the optical tools (`optical/run_scan.py`, `check_step*.py`, `make_config.py`)
  run in `xamssim` (they start `xamsg4` through `g4bin`); they also still work inside `g4`.
