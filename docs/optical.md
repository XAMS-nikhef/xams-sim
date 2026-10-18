# Optical simulation

178 nm photons through the TPC: refraction and reflection at the liquid surface and the windows, transmission through
and reflection on the etched meshes, reflection on PTFE, steel and copper, Rayleigh scattering and absorption in the
liquid, detection on the photocathodes with the QE. One event = one photon; nothing else is simulated.

## Scans (production)

A scan runs the optical model for a grid of parameter values; each point is split into parallel parts with
independent seeds. Positions are random in the source volume and stored per photon, so maps (vs r, x–y, z) are made
afterwards by binning.

```bash
xamssim optical optical/scans/<scan>.yaml [--jobs 8] [--dry]
```

A scan file:

```yaml
name: my_scan                 # output goes to run/scans/my_scan/
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
  `run/scans/<name>/` away first, or old results are reused.
- `--dry` lists the points and how many parts are still to run.
- Existing scan files: `optical/scans/` (`fit_s1`, `fit_s2`, `s1_optics`, `s2_optics`, `s2_rayleigh`, `check_v4_*`,
  `deadcross_s2`, `anode_rotation_*`, `design_ptfe_*`).
- Speed: ~1.5·10⁵ photons per second per process.

`xamssim optical` runs `optical/run_scan.py`, which can also be called directly
(`python optical/run_scan.py <scan> --jobs 8`).

## One configuration, one run

```bash
python optical/make_config.py --level 3.0 --set optics.stainless_steel_reflectivity=0.5 --out run/my.json
```

`make_config.py` combines `geometry.yaml` and `materials.yaml` into one `config.json`: one liquid level and one value
for every free optical parameter (the middle of its range unless set). A single run of `xamsg4` with your own macro:
see the [xamsg4 reference](xamsg4.md).

## Changing the model

- Values: `config/geometry.yaml` (dimensions), `config/materials.yaml` (materials, optics). Each value has its source
  next to it.
- Design options without new code: `extra_ptfe` (extra PTFE cylinders, see `optical/scans/make_design_ptfe.py`).
- New kinds of parts: C++ in `g4/src/XamsGeometry.cc`, then rebuild and run the [checks](validation.md).

## Tools in `optical/`

| tool | does |
|---|---|
| `run_scan.py` | runs a scan |
| `make_config.py` | geometry + materials → `config.json` |
| `read_output.py`, `scan_data.py` | readers for one file / a whole scan |
| `plot_section.py` | draws an exact cross section (see [viewers](viewers.md)) |
| `check_step1.py` … `check_step5.py` | [validation checks](validation.md) |
| `step6_results.py`, `step7_compare.py`, `step8_fit.py`, … | analyses of the optical study (scripts behind the notes) |
| `targets/` | measured data targets for comparisons and fits |
| `examples/my_first_analysis.py` | a worked example to copy |
