# XAMS optical simulation — user guide

How it works, what every file is, how to run it, and how to read the output for your own analysis.
(`PLAN.md` = how it was built and checked; `README.md` = short status; this file = how to use it.)

## 1. The idea in one picture

```
geometry.yaml ──make_config.py──► config.json ──┐
 (all numbers,                   (one concrete    │
  from the drawings)              setting)        ▼
                                  macro.mac ──► xamsopt (Geant4) ──► photons.bin  (+ .summary.json, .volumes.json)
                                  (what to do:                         one record per photon
                                   source, how many)                        │
                                                                            ▼
                                                    Python: tools/read_output.py, tools/scan_data.py → your analysis
```

- One **event** = one 178 nm photon. It is started at a random place in the source volume (S2: gas gap, S1: drift
  region), in a random direction, and followed until it is detected or lost.
- Every photon gives one **record**: where it started, where it ended, how (detected / absorbed / escaped), which
  sensor, how many reflections.
- A **scan** = the same run for a grid of parameter values (liquid level, reflectivities, ...), each point split in
  8 parallel parts. `tools/run_scan.py` does all of that from one small YAML file.
- There is **no position grid**: positions are random and stored per photon, so maps (vs r, x–y, z) are made
  afterwards by binning.

## 2. One-time setup

Everything that runs Geant4 needs the conda environment `g4` (Geant4 11.3 with its data files). Python analysis
of existing output does not need it (any Python with numpy + matplotlib, e.g. `~/miniconda3/bin/python`).

```bash
conda activate g4
cd /Users/acolijn/Documents/XAMS_DAQ/optical_sim
mkdir -p build && cd build && cmake .. && make -j8 && cd ..
```

After editing C++ code (`src/`, `include/`): `cd build && make -j8`. After editing a macro in `macros/`: rerun
`cmake ..` in `build/` (it copies the macros), or `cp macros/*.mac build/`.

## 3. What every file is

| Path | What it is | You edit it? |
|---|---|---|
| `geometry.yaml` | **all numbers**: meshes (z, angle, which face the foil is on), rings, PTFE, copper rings, PMTs, SiPMs, optics ranges, data targets. Single source of truth, values with their source (drawing, thesis, user). | yes — geometry / optics changes go here |
| `tools/make_config.py` | turns `geometry.yaml` into one `config.json`: picks a liquid level, puts free parameters at the middle of their range unless you `--set` them | no |
| `xamsopt.cc`, `src/`, `include/` | the Geant4 program (C++) | only for new features |
| `src/XamsGeometry.cc` | builds the XAMS geometry from the config (meshes as real bars, rings, PTFE, copper rings, PMTs, SiPMs) | rarely |
| `src/DetectorConstruction.cc` | materials, optical surfaces (reflectivities), test geometries | rarely |
| `src/PrimaryGeneratorAction.cc` | the photon source (shapes `s2`, `s1`, `point`, `cylinder`, `beam`, ...) | rarely |
| `src/PhotonActions.cc`, `src/Output.cc` | follow each photon, write the records and the summary | no |
| `macros/*.mac` | Geant4 command files (what to run). `production.mac` = template for scans, `vis_interactive.mac` = viewer setup, `section.mac` = cross sections, `step*.mac` = the checks | sometimes |
| `scans/*.yaml` | scan definitions (source, photons, parameter grid) | yes — make your own |
| `tools/run_scan.py` | runs a scan (configs, macros, parallel parts, skips finished parts) | no |
| `tools/read_output.py` | reads one `.bin` file → numpy array | no — use it |
| `tools/scan_data.py` | reads a whole scan → points with parameters, records, tallies; `top_fraction()` | no — use it |
| `tools/plot_section.py` | draws a cross section made with `/xamsopt/section` | no |
| `tools/check_step1..5.py` | the validation checks of `PLAN.md` (each prints PASSED / FAILED) | no |
| `tools/step6_results.py`, `step7_compare.py`, `design_ptfe.py` | made the result figures / tables in `results/` | copy to start your own |
| `targets/data_2026-10-05.json` | measured AFT and top-sector numbers from the data (from `analysis_SR2026.2/studies/optsim_targets.py`) | no |
| `results/` | result notes + figures (step 6, step 7, design study) | — |
| `examples/my_first_analysis.py` | **start here** for your own analysis | copy it |
| `run/` | all generated files (configs, output). **Not in git**, can be regenerated | — |
| `build/` | compiled program + copied macros. Not in git | — |

## 4. Running

All commands from `optical_sim/` with `conda activate g4`.

**Look at the geometry** (Qt window; drag = rotate, scroll = zoom):
```bash
python tools/make_config.py --level 4.0 --out run/config_level4.json
cd build && ./xamsopt -c ../run/config_level4.json -o /tmp/vis.bin
```
In the window's command box: `/xamsopt/source/shape s2`, `/xamsopt/source/rmax 30 mm`, `/run/beamOn 50` draws
photons; `/vis/viewer/set/cutawayMode intersection` + `/vis/viewer/addCutawayPlane 0 0 0 m 1 0 0` cuts it open.

**Exact cross sections** (what the simulation really uses):
```bash
cd build && ./xamsopt -c ../run/config_level4.json -o /tmp/s.bin section.mac && cd ..
python tools/plot_section.py build/section_xz.bin --zoom 25 50 -14 22      # → build/section_xz.png
```

**One run** (e.g. 10⁶ S2 photons):
```bash
cat > build/my_run.mac <<'EOF'
/run/initialize
/xamsopt/source/shape s2
/xamsopt/source/rmax 30 mm
/run/beamOn 1000000
EOF
cd build && ./xamsopt -c ../run/config_level4.json -o ../run/my_run.bin -s 1 -d my_run.mac && cd ..
```
Options: `-c` config, `-o` output file, `-s` random seed, `-d` write records only for detected photons (all photons
are still counted in the summary; without `-d` every photon gets a record — 36 bytes each), `-v` allow pictures in
batch.

**A scan** (recommended for anything systematic): write a YAML file, e.g. `scans/my_scan.yaml`:
```yaml
name: my_scan                 # output goes to run/scans/my_scan/
source: s2                    # s2 = gas gap (liquid surface to anode), s1 = drift region (cathode to gate)
rmax_mm: 30                   # photons start at r < 30 mm
photons: 10000000             # per point (~10 s on the Mac for S2; S1 slices in z need ~10^8)
chunks: 8                     # parallel parts per point
seed: 70000                   # change it for an independent repetition
base:
  level: 4.0                  # liquid level above the gate (mm) for every point
  set: {optics.lxe.rayleigh_length_cm: 45}     # fixed overrides (any path in config.json)
grid:                         # every combination is one point
  optics.ptfe_in_liquid.reflectivity: [0.90, 0.95, 0.99]
  optics.copper_reflectivity: [0.2, 0.4]
```
```bash
python tools/run_scan.py scans/my_scan.yaml --jobs 8
```
Interrupted? Run the same command again: finished parts are skipped. To redo a scan from scratch, move or remove
`run/scans/my_scan/` first.

**Change a parameter for one run:** `python tools/make_config.py --level 3.0 --set optics.stainless_steel_reflectivity=0.5 --out run/my.json`.
Geometry design changes (e.g. extra PTFE) work the same way, see `scans/make_design_ptfe.py`.

## 5. The output files

Per run (or per scan part) `xxx.bin` plus two small JSON files:

**`xxx.bin`** — one fixed-size binary record (36 bytes) per photon (per detected photon with `-d`):

| field | type | meaning |
|---|---|---|
| `event` | int32 | photon number in the run |
| `x0, y0, z0` | float32, mm | start position |
| `x1, y1, z1` | float32, mm | end position |
| `end_code` | int16 | 1 detected, 2 absorbed in the xenon, 3 absorbed on a surface (also: entered an absorbing material), 4 left the world, 0 unknown (should not happen) |
| `sensor` | int16 | 0 bottom PMT; 1–4 top-PMT sectors I–IV (= ch1–ch4); 6, 7 SiPMs; −1 not detected |
| `volume` | int16 | where it ended: index into `xxx.bin.volumes.json` (e.g. `anodeBar`, `PTFE`, `World`) |
| `n_refl` | int16 | number of reflections (Fresnel, total internal, PTFE, steel, copper) |

**`xxx.bin.summary.json`** — every photon counted, also without records: `n_photons`, `tally` (list of
`{end_code, volume, n}`), `detected_by_sensor`, and the config / seed / macro used.
**`xxx.bin.volumes.json`** — volume index → name.

A scan directory `run/scans/<name>/` has per point `point_<i>.json` (its config), `point_<i>_<k>.bin` (+ JSON,
+ `.log`, `.mac`) for the parts k = 0..7, and `points.json` (index: parameters per point).

**Coordinates:** mm; z = 0 at the gate foil, z up; liquid surface at z = level (2–4 mm); anode +8, top screen +18,
cathode −51.8, bottom screen −59.6; top-PMT window at +22.5, bottom-PMT window at −64.1. Top sectors (seen from
above): I at (−x, +y), II (+x, +y), III (−x, −y), IV (+x, −y). **The data frame (posrec v2) has x mirrored:**
x_data = −x_sim, y_data = y_sim.

**QE:** the photocathodes convert with QE 0.33 (`pmt_common.qe_178nm`), so "detected" already includes the QE.
Photons that reached a photocathode but were not converted end with code 3 on `TopPMTSector` / `BottomPMTCathode`.

## 6. Reading the output in Python

```python
import sys; sys.path.insert(0, "tools")          # from optical_sim/
from read_output import read, summary
from scan_data import load, top_fraction
import numpy as np

# one file
rec, volumes = read("run/my_run.bin")            # rec: numpy structured array, volumes: {index: name}
det = rec[rec["end_code"] == 1]
print(len(det) / len(rec), summary(rec, volumes))   # (with -d, rec holds only detected photons: use the tally)

# a scan
scan = load("s2_optics")                         # run/scans/s2_optics
for p in scan["points"]:
    rec = p["rec"]                               # detected photons of all 8 parts together
    f, err = top_fraction(rec)                   # top / (top + bottom)
    lce_top = np.isin(rec["sensor"], (1, 2, 3, 4)).sum() / p["n_photons"]
    print(p["params"], f, lce_top, p["tally"])   # tally: {(end_code, volume): n} over ALL photons
```

Typical cuts: `r = np.hypot(rec["x0"], rec["y0"])` for maps vs radius, `rec["z0"]` for S1 vs depth,
`rec["sensor"] == s` for one sector. `load(name, records=False)` reads only tallies (fast).

**Worked example:** `python examples/my_first_analysis.py` — scan contents, one record, top fraction (overall and
vs r), sector shares for an S2 spot, where the undetected photons went, a figure. Copy it and change it.

## 7. Checks and existing results

- `python tools/check_step1.py` … `check_step5.py` re-validate the program (solid angle, Fresnel, mesh transparency,
  surfaces, sources). Run them after changing C++ code.
- `results/step6/README.md` — first physics (top fraction vs optics, light collection, where light is lost).
- `results/step7/README.md` — comparison with the data (sector pattern, S2 / S1 area fraction top).
- `results/design_ptfe/README.md` — extra PTFE cylinders.

## 8. Things that are easy to get wrong

- Run Geant4 only inside `conda activate g4` (otherwise it cannot find its data files and stops).
- A macro edited in `macros/` is only used after copying it to `build/`.
- `run_scan.py` skips parts that exist: after a geometry change, move the old `run/scans/<name>/` away.
- With `-d` the `.bin` holds only detected photons; fractions of all photons come from `n_photons` / the tally.
- The model treats everything outside |x|, |y| < 60 mm (and below −90 / above +45 mm) as black.
- Free optical parameters (reflectivities, Rayleigh length) sit at the middle of their range unless set.
