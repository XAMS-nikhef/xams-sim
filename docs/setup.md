# Setup

Everything that runs Geant4 needs the conda environment **`g4`** (Geant4 11.3.2 with its data files, Qt viewer,
cmake, a C++ compiler, nlohmann/json). The data-file paths are only set when the environment is activated, so always
build and run inside it:

```bash
conda activate g4
cd /Users/acolijn/Documents/XAMS/optical_sim
cmake -S g4 -B g4/build && cmake --build g4/build -j8
```

- After editing C++ code (`g4/src/`, `g4/include/`): `cmake --build g4/build -j8`.
- After editing a macro in `g4/macros/`: `cp g4/macros/*.mac g4/build/` (or rerun `cmake -S g4 -B g4/build`, which copies them).
- Python analysis of existing output does **not** need `g4`: any Python with numpy and matplotlib works (e.g.
  `~/miniconda3/bin/python`). `optical/run_scan.py` and `optical/make_config.py` need PyYAML (present in `g4`).
