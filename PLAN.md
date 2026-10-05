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
| 2 Materials | **done** | 2026-10-05 | see "Done" under step 2 |
| 3 Geometry v1 | **done** | 2026-10-05 | see "Done" under step 3 |
| 4 Optical surfaces | **done** | 2026-10-05 | see "Done" under step 4 |
| 5 Sources and runs | **done** | 2026-10-05 | see "Done" under step 5 |
| 6 First physics results | **done** | 2026-10-05 | see "Done" under step 6 and `results/step6/README.md` |
| 7 Targets from the data | **done** | 2026-10-05 | see "Done" under step 7 and `results/step7/README.md` |
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

**Done (2026-10-05).**
- Materials in `DetectorConstruction`: liquid xenon (n, absorption and Rayleigh length from the config), gas xenon
  (n = 1.00), silica for the PMT windows (n from the config; window transmission folded into the QE), stainless steel
  (G4_STAINLESS-STEEL; optics via its surface, step 4), photocathode (G4_Al; detection via its surface). All optical
  properties flat over 6–8 eV (178 nm).
- Test geometry `test_interface` (liquid below z = 0, gas above, plain boundary) and a `beam` source
  (`/xamsopt/source/direction`); `tools/check_step2.py`, macro `step2_interface.mac`.
- **Check passed:** beam from the liquid onto the surface at 0–80°, 10⁵ photons per angle, random linear polarisation:
  reflected fraction equals (Rs + Rp)/2 from 6.6 % at normal incidence to 37.7 % at 35.5°, and 100 % (total internal
  reflection) from 37° on (critical angle 36.3°). All pulls within ±1.4 except 30° (+2.5), which a rerun with 4·10⁵
  photons and another seed gives −0.66 (fluctuation).

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

**Done (2026-10-05).**
- `src/XamsGeometry.cc`, geometry_mode `xams`: absorbing world; liquid xenon box (z −90 mm to the liquid surface) and
  gas xenon box (surface to +45 mm), ±60 mm in x, y. The PTFE cylinder lies entirely in the liquid (gate is below the
  surface in every scenario), so no split at the liquid level is needed.
- Meshes (top screen 18, anode 8 in gas; gate 0, cathode −51.8, bottom screen −59.6 in liquid), all at 29.4° to the
  anodes: a thin disc of the surrounding medium (r 32 mm, 0.15 mm) holding 531 steel bar pieces (x bars as full chords,
  y bars in pieces between them, so nothing overlaps); bar centre lines at k·p, so two bars cross on the axis — as in
  the gate drawing (`posrec2_template.json`: pitch 2.5997 mm, hole 2.45 mm, lattice phase ±0.5 = wire crossing at the
  centre). Rings: steel annulus r 32–46.3 mm, 1.8 mm thick.
- PTFE cylinder r 30.97–35.97 mm, z −50.9 to −0.9 mm (between the gate and cathode rings). PMTs: silica window
  54.6 mm square, 2.5 mm; photocathode 48.5 mm square (top: 4 sectors, copies 1–4; bottom: copy 0); absorbing frame and
  body. SiPMs (copies 6, 7) on the PTFE inner wall at azimuth 0° / 90°, z −25 mm.
- Viewing: `xamsopt -c config.json` without a macro opens the Qt viewer (`vis_interactive.mac`: media hidden, colours,
  axes; `/run/beamOn N` draws photon tracks). `/xamsopt/section file plane offset umin umax vmin vmax step` asks
  Geant4's navigator for the volume at every point of a grid (`section.mac`), `tools/plot_section.py` draws it
  (`build/section_xz.png`, `section_xz_zoom.png`, `section_gate_xy.png`).
- **Checks passed:** overlap check at every placement clean; the cross sections match section A–A (z positions, ring
  and PTFE radii, liquid surface at +4 mm) and the gate drawing (pitch, hole, crossing at the centre). Mesh
  transparency (`tools/check_step3.py`, geometry_mode `test_mesh`, black bars, beam over a 25 mm disc, 2·10⁵ photons
  per point, θ = 0–75°, φ = 0 / 29.4 / 45°): Geant4 agrees photon by photon with an analytic ray trace through the bar
  lattice (agreement 1.000000 in all 15 settings), and the transmitted fraction follows
  T = (h − t|tanθ cosφ|)(h − t|tanθ sinφ|)/p² from 0.888 at normal incidence to 0.62 at 75° (pulls within ±2.4).
- Not done: the exact hole pattern of the drawing as geometry (the generated lattice reproduces it; not needed).

## 4. Optical surfaces (½ day)

- Liquid–gas: plain boundary (Fresnel + total internal reflection from the refractive indices).
- PTFE: UNIFIED model, diffuse (Lambertian) + specular part, reflectivity separately in liquid and gas (config).
- Stainless steel (meshes, rings): reflectivity from the config, mostly diffuse.
- Photocathodes: absorb with probability QE (detected), else absorbed (no reflection in v1).
- **Check:** with PTFE reflectivity 0 the result equals the step-3 geometry with black walls; with reflectivity → 1 and
  no other losses every photon ends on a sensor or a mesh (bookkeeping closes).

**Done (2026-10-05).**
- `DetectorConstruction::MakeReflector` / `ApplySurfaces` (geometry_mode `xams`): skin surfaces, UNIFIED model,
  ground, dielectric_metal. PTFE: reflectivity and specular fraction from `optics.ptfe_in_liquid` (specular part as a
  mirror spike, the rest Lambertian). Steel (all mesh bars and rings): `optics.stainless_steel_reflectivity`, fully
  Lambertian. Not reflected = absorbed. `ptfe_in_gas` is not used: the PTFE cylinder lies entirely in the liquid.
  Config `"surfaces": 0` makes PTFE and steel black. `test_mesh` keeps black bars (step-3 check).
- Liquid–gas surface and PMT windows: plain boundaries from the refractive indices (step 2). Photocathodes as before
  (QE, no reflection).
- New test geometry `test_surface` (beam in liquid xenon onto a PTFE or steel slab); macros `step4_surface.mac`,
  `step4_xams.mac`; S2-like test source: cylinder r < 25 mm, z 4.0–7.9 mm (a first version up to 8.0 mm started
  photons inside the anode foil — they were absorbed at birth; the source must stay below the foil, 7.925 mm).
- **Checks passed** (`tools/check_step4.py`):
  (a) single surface, 2·10⁵ photons, θ = 0 / 30 / 60°: reflected fraction = R (PTFE 0.95 and 0.90, steel 0.35; pulls
  ≤ 1.1); specular fraction 0.199 for f = 0.2 (pull −0.9), none for f = 0; diffuse part Lambertian (⟨cos⟩ = 0.667,
  KS p ≥ 0.1).
  (b) XAMS, S2-like source: black surfaces and reflectivity 0 give the same light per sensor (pulls within ±1.0).
  (c) XAMS with PTFE and steel reflectivity 1, no bulk losses: every photon ends detected (15.5 %) or on an absorber
  (world 41 %, photocathodes beyond QE, PMT frames/bodies); none on PTFE or steel, none undefined, none in the bulk.
- First look (not a result; no absorption / Rayleigh, QE 0.33 everywhere): S2 top fraction 0.69 with black PTFE and
  steel, 0.47 with reflectivity 1. The data (low load) give ≈ 0.52 — reflections matter; step 6 does this properly.

## 5. Sources and production runs (½ day)

- S2: uniform between the liquid surface and the anode, on an x–y grid (r < 25 mm) or uniform in the disc.
- S1: in the liquid, z from the cathode to the surface in 2 mm steps, same x–y grid.
- Run sets as config + macro (parameter scans as separate runs), 10⁶–10⁷ photons per point.
- **Check:** statistical precision of the top fraction per point < 0.5 %; run time per scan point measured.

**Done (2026-10-05).**
- Sources (`/xamsopt/source/shape s2 | s1`, z range from the config, so every liquid level is right automatically):
  S2 uniform from the liquid surface to 0.01 mm below the anode foil (z 4.0–7.915 mm at the 4 mm level); S1 uniform
  from just above the cathode foil to just below the gate foil (z −51.715 to −0.085 mm); both r < rmax (30 mm).
  Instead of a grid of source points, photons start uniformly and every record keeps its origin: maps (r, sector
  pattern, z slices) are made by binning afterwards, one run per parameter point.
- Output for production (`xamsopt -d`): records only for detected photons; every photon is counted in
  `<file>.summary.json` (end code × end volume, detected per sensor, seed, config).
- `tools/run_scan.py scans/<name>.yaml`: parameter grid (liquid level and any config path) → one config per point,
  each point split into parallel parts with their own seeds; resumable; output in `run/scans/<name>/`.
  `tools/scan_data.py`: reads a scan (records, tallies, timing), `top_fraction()`.
- Scan sets ready for step 6: `s2_optics` (level × PTFE reflectivity × steel reflectivity, 27 points × 10⁷),
  `s2_rayleigh` (Rayleigh length × PTFE specular fraction, 9 × 10⁷), `s1_optics` (PTFE reflectivity, 3 × 10⁸).
- **Check passed** (`tools/check_step5.py`): source z ranges as expected for levels 2 and 4 and for S1; z, r², φ
  uniform (KS p ≥ 0.01); every photon counted once, one record per detected photon. Reference runs (4·10⁶ photons,
  middle-of-range optics, level 4): S2 top fraction 0.5663 ± 0.0009 (0.16 %), S1 0.1775 ± 0.0007 (0.39 %) — below
  0.5 % per point. Speed 1.5–1.6·10⁵ photons/s per process; 8 in parallel on the Mac → 4·10⁶ photons in 3 s.
  For 0.5 % in every bin: S2 in 5 mm rings of r needs 10⁷ photons per point, S1 in 2 mm slices of z 10⁸ (~2 min).

## 6. First physics results (1 day)

- S2 top fraction versus liquid level (2, 3, 4 mm) and versus PTFE reflectivity (gas / liquid), mesh reflectivity,
  Rayleigh length; light collection efficiency (detected / emitted) top and bottom.
- S1 top fraction versus z (and r).
- Light pattern of the 4 top sectors versus S2 position.
- Where the light is lost (meshes, PTFE, liquid surface, escape) — this answers *why*.
- **Check:** results stable against the photon number and the seed; sensible limits (black walls, perfect walls).

**Done (2026-10-05).** Results and figures in `results/step6/` (`README.md`), made by `tools/step6_results.py` from
the scans `s2_optics` (27 points), `s2_rayleigh` (9), `s1_optics` (3 × 10⁸), `s2_ring` (4; ring inner Ø robustness).
- S2 top fraction 0.53–0.59 over all parameter ranges (data at low load 0.52); liquid level hardly matters (+0.009
  from 2 to 4 mm); strongest knobs PTFE specular fraction, steel and PTFE reflectivity. Ring inner Ø (open value)
  changes it by < 0.004.
- S2 light collection 4.4 % top / 3.4 % bottom (QE 0.33 included); ~40 % of the S2 light goes sideways into the rings
  or out of the TPC region; mesh bars take ~25 %.
- S1 top fraction 0.11 (cathode) → 0.26 (gate).
- **Check passed:** halves of every point with independent seeds agree (worst pull 2.2); limits as in step 4.

## 7. Targets from the data (1 day, analysis_SR2026.2)

- S2 top fraction at low load: no-source runs (B28, B29) and load-corrected values (top-PMT gain drop: history model,
  or SiPM-referenced); per position (r) and per S2 size.
- S1 top fraction versus drift time (z) for the Cs photopeak.
- Top-sector light pattern versus position: the light-response model of position reconstruction v2 (`posrec2_lrf.json`).
- Oct 2024 (run 6786, 2 + 6 mm) versus SR-2026.2 (4 + 4 mm): the same quantities.
- Gains / QE: LED gains per sector; QE top versus bottom is a free parameter (only their ratio matters for the top
  fraction).

**Done (2026-10-05).** `analysis_SR2026.2/studies/optsim_targets.py` (stbc-i2, read-only, central v4) →
`targets/data_2026-10-05.json`; `tools/step7_compare.py` → `results/step7/compare.png`; details in
`results/step7/README.md`.
- Top-sector pattern (u, v vs position, posrec v2): data inside the simulation band over ±24 mm, same for every
  source — the geometry is right.
- S2 area fraction top (LED gains): falls with source rate and with S2 size up to ~20 kPE (no source 0.68 → 0.50);
  vs r a dip at the centre (r < 5 mm) not in the simulation; outside it data/simulation top/bottom ratio 1.0–1.2.
- S1 area fraction top vs z: same shape as the simulation, top/bottom ratio data/simulation 0.72 at every z.
- Not done: Oct 2024 (run 6786); QE ratio left free for step 8.

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
