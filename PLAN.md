# Implementation plan — XAMS optical simulation (model v1)

Goal: predict, from geometry and optics alone, how S2 and S1 light divides over the top PMT (4 sectors), the bottom
PMT and the SiPMs, and compare with the data — in particular whether the top PMT's share (S2 top fraction ≈ 0.5 at low
load) follows from the geometry. Geometry and parameters come from `geometry.yaml` (single source of truth).

Each step ends with a check; a step is only done when its check passes. Rough effort in brackets.

## Progress

| Step | Status | Date | Notes |
|---|---|---|---|
| 0 Environment | **done** | 2026-10-05 | see "Done" under step 0 |
| 1 Skeleton | **done** | 2026-10-05 | see "Done" under step 1 |
| 2 Materials | open | | |
| 3 Geometry v1 | open | | |
| 4 Optical surfaces | open | | |
| 5 Sources and runs | open | | |
| 6 First physics results | open | | |
| 7 Targets from the data | open | | |
| 8 Comparison and fit | open | | |
| 9 Write-up | open | | |

## 0. Environment (½ day)

- Geant4 ≥ 11 with optical physics, CMake, a C++17 compiler. Where: the Mac (`g4` conda environment) or stbc-i2
  (cvmfs). Decide after checking what is installed.
- Config: a small Python script turns `geometry.yaml` into `config.json`; the C++ code reads JSON (header-only
  nlohmann/json). No YAML library needed in C++.
- Output without ROOT: one binary/CSV record per photon (origin x, y, z; end: which sensor or where absorbed; number of
  reflections), analysed in Python (numpy).
- **Check:** Geant4's optical example (OpNovice2) builds and runs.

**Done (2026-10-05).**
- Environment: the Mac, conda environment `g4` (`conda activate g4`): Geant4 11.3.2 (conda-forge, GDML and Qt
  enabled), cmake 4.0.2, clang++ 18, nlohmann/json headers. The Geant4 data sets are installed with the environment
  (`share/Geant4/data/*`); their paths (`G4ENSDFSTATEDATA` etc.) are set only when the environment is activated, so
  always build and run inside it.
- Check passed: OpNovice2 builds and its `fresnel.mac` runs (batch, 5 s, no exceptions); Fresnel reflection, total
  internal reflection (mean 68°, beyond the 46° critical angle for n = 1.40 / 1.01) and refraction behave as expected.
  (Its reference output comes from an older Geant4 with other units, so only the physics was compared.)
- Config: `tools/make_config.py --level <mm> [--set path=value] --out run/<name>.json` turns `geometry.yaml` into the
  JSON the C++ code will read: one liquid-level scenario, free parameters at the middle of their range unless set,
  derived liquid-surface z, meshes sorted by z; refuses missing required values and impossible levels; defaults for the
  two open second-order values (mesh ring inner Ø 64 mm, foil in the middle of the ring).
- Output format decided: one record per photon (origin, end point / sensor, number of reflections), read in Python;
  no ROOT.
- Generated files (`run/`, `build/`) are not tracked in git.

## 1. Skeleton application (½ day)

- `main`, DetectorConstruction, PhysicsList (G4OpticalPhysics only: absorption, Rayleigh, boundary — no
  scintillation, the photons are generated directly), PrimaryGenerator (178 nm optical photons, isotropic, random
  polarisation, position sampler), sensitive photocathodes, per-photon output, macro commands for source type and
  position, number of photons, random seed.
- **Check:** a box of liquid xenon with one photocathode; detected fraction equals the solid angle.

**Done (2026-10-05).**
- Code (C++17, Geant4 11.3, CMake): `xamsopt.cc` (`xamsopt -c config.json -o out.bin [-s seed] [macro]`; without a
  macro an interactive session with visualisation), `src/` + `include/`: `Config` (reads the JSON from
  `make_config.py`), `DetectorConstruction` (geometry_mode `test_box` now; `xams` = step 3), `PhysicsList`
  (G4OpticalPhysics only; scintillation, Cherenkov, WLS, Mie off; e−/e+/γ/p defined because G4OpticalPhysics looks
  them up), `PrimaryGeneratorAction` (one 178 nm photon per event, isotropic, random polarisation; shapes `point` and
  `cylinder` via `/xamsopt/source/...`), `PhotonActions` (per-photon record: origin, end point, end code detected /
  bulk-absorbed / surface-absorbed / escaped, sensor id, end volume, number of reflections), `Output` (binary records
  + `<file>.volumes.json`). Sequential run manager (fast enough; per-thread output would be needed for MT).
- Photocathodes: optical surface dielectric_metal, REFLECTIVITY 0, EFFICIENCY = QE; sensor id = copy number
  (0 bottom, 1–4 top sectors I–IV, 6/7 SiPMs, 10 test cathode).
- Python: `tools/read_output.py` (numpy reader, summary), `tools/check_step1.py` (the check below).
- Build: `conda activate g4; mkdir build; cd build; cmake ..; make` (macros are copied into `build/`).
- **Check passed:** point source, 48.5 mm square cathode (QE 1) at 10 / 30 / 60 mm, 2·10⁵ photons each: detected
  fraction 0.32626 / 0.12946 / 0.04435 against the solid angle 0.32624 / 0.12932 / 0.04484 (pulls 0.02, 0.19, −1.06);
  every photon ends detected or escaped. Speed: ~6·10⁵ photons per second in this geometry.

## 2. Materials and optical properties (½ day)

- Liquid xenon (n = 1.69, Rayleigh and absorption length from the config), gas xenon (n = 1.00), fused silica
  (PMT window, n ≈ 1.6), stainless steel (meshes, rings), PTFE (only as a surface), photocathode (efficiency = QE).
- **Check:** a beam onto a liquid–gas boundary reproduces the Fresnel reflection versus angle and total internal
  reflection beyond 36° (from the liquid side), against the formulas.

## 3. Geometry v1 (1–1½ days)

- World = absorber. Inside: liquid xenon below the liquid level, gas xenon above (the level from the config, scenarios
  2 / 3 / 4 mm above the gate).
- PTFE cylinder (inner Ø 61.94 mm, z range from the config), split at the liquid level so that each part has its own
  optical surface (PTFE–liquid, PTFE–gas).
- Five meshes: 0.15 mm stainless foil, square holes 2.45 mm, bars 0.15 mm (pitch 2.6 mm), foil Ø 80 mm, rotated per
  mesh; built without overlaps (bars in one direction full length, the crossing bars in segments between them), clipped
  to the circle; the ring (Ø 92.6 × 1.8 mm) as a stainless annulus. The gate uses the exact hole pattern
  (`posrec2_template.json`) as a check of the generated one.
- Two R12699 PMTs: fused-silica window + photocathode (48.5 mm square), the top one split into 4 sectors (24.25 mm),
  the rest of the PMT body absorbing.
- **Checks:** Geant4 overlap check clean; geometry drawn (VRML / image) and compared with section A–A; a collimated beam
  through one mesh gives the open fraction 0.888 at normal incidence and the expected drop with angle (analytic
  formula for a foil of thickness 0.15 mm).

## 4. Optical surfaces (½ day)

- Liquid–gas: plain boundary (Fresnel + total internal reflection from the refractive indices).
- PTFE: UNIFIED model, diffuse (Lambertian) + specular part, reflectivity separately in liquid and gas (config).
- Stainless steel (meshes, rings): reflectivity from the config, mostly diffuse.
- Photocathodes: absorb with probability QE (detected), else absorbed (no reflection in v1).
- **Check:** with PTFE reflectivity 0 the result equals the step-3 geometry with black walls; with reflectivity → 1 and
  no other losses every photon ends on a sensor or a mesh (bookkeeping closes).

## 5. Sources and production runs (½ day)

- S2: uniform between the liquid surface and the anode, on an x–y grid (r < 25 mm) or uniform in the disc.
- S1: in the liquid, z from the cathode to the surface in 2 mm steps, same x–y grid.
- Run sets as config + macro (parameter scans as separate runs), 10⁶–10⁷ photons per point.
- **Check:** statistical precision of the top fraction per point < 0.5 %; run time per scan point measured.

## 6. First physics results (1 day)

- S2 top fraction versus liquid level (2, 3, 4 mm) and versus PTFE reflectivity (gas / liquid), mesh reflectivity,
  Rayleigh length; light collection efficiency (detected / emitted) top and bottom.
- S1 top fraction versus z (and r).
- Light pattern of the 4 top sectors versus S2 position.
- Where the light is lost (meshes, PTFE, liquid surface, escape) — this answers *why*.
- **Check:** results stable against the photon number and the seed; sensible limits (black walls, perfect walls).

## 7. Targets from the data (1 day, analysis_SR2026.2)

- S2 top fraction at low load: no-source runs (B28, B29) and load-corrected values (top-PMT gain drop: history model,
  or SiPM-referenced); per position (r) and per S2 size.
- S1 top fraction versus drift time (z) for the Cs photopeak.
- Top-sector light pattern versus position: the light-response model of position reconstruction v2 (`posrec2_lrf.json`).
- Oct 2024 (run 6786, 2 + 6 mm) versus SR-2026.2 (4 + 4 mm): the same quantities.
- Gains / QE: LED gains per sector; QE top versus bottom is a free parameter (only their ratio matters for the top
  fraction).

## 8. Comparison and fit (1 day)

- Grid scan (or a simple likelihood) of the free parameters — PTFE reflectivity liquid / gas, mesh reflectivity,
  Rayleigh length, QE ratio top / bottom — against the targets of step 7.
- **Outcome:** does a realistic parameter set reproduce the S2 top fraction (and S1 versus z, the sector pattern, the
  2024 → 2026 change)? If yes: the top light is geometry; if no: which observable fails, and by how much (QE / gain
  calibration of the top PMT, mesh transparency, a missing part).

## 9. Write-up (½ day)

- Note in `optical_sim/notes/` with the geometry, the checks, the comparison and the conclusion; results into
  `notebooks/run_overview.md`; input for the refill plan (expected S2 sizes at the Oct-2024 settings with 4 + 4 mm).

## Later (v2, only if step 8 asks for it)

- SiPMs with their VUV filters; field-shaping rings, PMT holders and other parts (from the CAD if needed); S2 light
  produced along the electron path with the real field map; photocathode reflection; the light-response model for the
  position reconstruction.

## Decisions / input needed from AP

1. The open values in `geometry.yaml` (24, mainly: PTFE z range, PMT window heights, top-screen height, mesh
   orientations, window material / thickness).
2. Where to run (Mac or stbc-i2) and whether you want to maintain the code yourself (then C++ in a standard Geant4
   layout, which this plan assumes).
3. Liquid level in Oct 2024: 2 mm (your correction) or 3 mm (thesis) — or simulate both.

Total: roughly 7–8 working days for steps 0–9, of which steps 0–5 (a working, checked simulation) about 4.
