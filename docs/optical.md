# Optical simulation

178 nm photons through the TPC: refraction and reflection at the liquid surface and the windows, transmission through
and reflection on the etched meshes, reflection on PTFE, steel and copper, Rayleigh scattering and absorption in the
liquid, detection on the photocathodes with the QE. One event = one photon; nothing else is simulated.

## Scans (production)

A scan runs the optical model for a grid of parameter values; each point is split into parallel parts with
independent seeds. Positions are random in the source volume and stored per photon, so maps (vs r, x–y, z) are made
afterwards by binning.

```bash
xamssim optical <scan>.yaml [--jobs 8] [--dry]
```

A scan file:

```yaml
name: my_scan                 # output goes to <data>/scans/my_scan/
source: s2                    # s2 = gas gap (liquid surface to below the anode), s1 = drift region
rmax_mm: 30                   # photons start at r < 30 mm
photons: 10000000             # per point
chunks: 8                     # parallel parts per point
seed: 70000                   # change it for an independent repetition
base:
  level: 4.0                  # liquid level above the gate (mm) for every point
  set: {optics.lxe.rayleigh_length_cm: 45}     # fixed overrides (any path in config.json)
grid:                         # every combination is one point
  optics.ptfe_in_liquid.reflectivity: [0.90, 0.95, 0.99]
  optics.copper_reflectivity: [0.2, 0.4]
```

- Finished parts are skipped, so an interrupted scan just runs again. After a geometry or code change move the old
  `<data>/scans/<name>/` away first, or old results are reused.
- `--dry` lists the points and how many parts are still to run.
- Scan files: `config/scans/example_s2.yaml` (example), `checks/scans/` (reference scans of check 5); the scans of the
  optical fit (2026-10-05) are in `../simulations/2026-10-05_optical_model_and_fit/scans/`; the light-map scans of the
  chain come with step S6.
- Speed: ~1.5·10⁵ photons per second per process.

`xamssim optical` runs `xamssim/run_scan.py`, which can also be called directly
(`python -m xamssim.run_scan <scan> --jobs 8`).

## One configuration, one run

```bash
python -m xamssim.g4config --level 3.0 --set optics.stainless_steel_reflectivity=0.5 --out /tmp/my.json
```

`xamssim.g4config` combines `geometry.yaml` and `materials.yaml` into one `config.json`: one liquid level and one value
for every free optical parameter (the middle of its range unless set). A single run of `xamsg4` with your own macro:
see the [xamsg4 reference](xamsg4.md).

## Changing the model

- Values: `config/geometry.yaml` (dimensions), `config/materials.yaml` (materials, optics). Each value has its source
  next to it.
- Design options without new code: `extra_ptfe` (extra PTFE cylinders; example scans in the 2026-10-05 study).
- New kinds of parts: C++ in `g4/src/XamsGeometry.cc`, then rebuild and run the [checks](validation.md).

## Tools

| tool | does |
|---|---|
| `xamssim/run_scan.py` | runs a scan (`xamssim optical`) |
| `xamssim/g4config.py` | geometry + materials → `config.json` |
| `xamssim/read_output.py`, `xamssim/scan_data.py` | readers for one file / a whole scan |
| `xamssim/section.py` | draws an exact cross section (see [viewers](viewers.md)) |
| `checks/check_step1.py` … `check_step5.py` | [validation checks](validation.md) |
