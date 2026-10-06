# Setup

Everything that runs Geant4 needs the conda environment **`g4`** (Geant4 11.3.2 with its data files, Qt viewer,
cmake, a C++ compiler, nlohmann/json). The data-file paths are only set when the environment is activated, so always
build and run inside it:

```bash
conda activate g4
cd /Users/acolijn/Documents/XAMS/optical_sim
mkdir -p build && cd build && cmake .. && make -j8 && cd ..
```

- After editing C++ code (`src/`, `include/`): `cd build && make -j8`.
- After editing a macro in `macros/`: `cp macros/*.mac build/` (or rerun `cmake ..`, which copies them).
- Python analysis of existing output does **not** need `g4`: any Python with numpy and matplotlib works (e.g.
  `~/miniconda3/bin/python`). `tools/run_scan.py` and `tools/make_config.py` need PyYAML (present in `g4`).
