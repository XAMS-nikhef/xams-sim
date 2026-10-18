# Implementation plan — electric field and electron drift (efield)

Goal: calculate the electric field in the XAMS TPC for every HV setting we run, drift electrons through it, and
predict (1) where charge is lost (PTFE wall, SiPMs, cathode), (2) the drift time versus depth and (3) the shift of the
S2 position — in particular the effect of the two SiPMs in their square holes in the PTFE cylinder (≈ 25 mm below the
gate, between copper rings 2 and 3). The predictions are compared with the measured apparent lifetime versus radius,
the cS2 spread map, the drift-time profile and the position reconstruction.

Principles, as for the optical model:

- `geometry.yaml` stays the single source of truth; the field model reads it (no second geometry).
- One HV setting = one small case file; every result is tied to a case.
- Each step ends with a check; a step is only done when its check passes. Rough effort in brackets.
- First the simple, fast route (scipy, no new software); full 3D FEM only if the simple route shows that the SiPMs
  matter or if a number for a paper is needed.

## Progress

| Step | Status | Date | Notes |
|---|---|---|---|
| E0 Inputs and decisions | in progress | 2026-10-12 | SiPM = grounded 3 × 3 mm plane, 1 mm recessed (user) |
| E1 Model builder | open | | |
| E2 2D axisymmetric field | open | | |
| E3 Mesh unit cell (optional) | open | | |
| E4 Drift tracker | open | | |
| E5 Validation with data (no SiPMs) | open | | |
| E6 3D SiPM model | open | | |
| E7 PTFE surface charge | open | | |
| E8 Run-plan cases (predictions) | open | | |
| E9 Link to the optical simulation | open | | |
| E10 Write-up | open | | |

## Layout

```
xams-sim/
  geometry.yaml            ← extended in E0: SiPM holes / packages / foil, chain resistors, electrode HV defaults
  efield/
    cases/*.yaml           one HV setting each: electrode voltages, SiPM state (grounded / floating / V), surface charge
    build.py               geometry.yaml + case → material (ε) and electrode description (2D and 3D)
    solve2d.py             axisymmetric (r, z) solver → potential map
    solve3d.py             local 3D box around one SiPM, boundary from the 2D map
    unitcell.py            (optional) one cell of a mesh → field leakage through gate / cathode
    drift.py               electron drift lines through a field map
    run_case.py            case → solve → drift → results/efield/<case>/
  results/efield/<case>/   maps (.npz), plots, summary.json, README
```

Python in the `g4` conda environment (numpy, scipy, matplotlib). FEM software (E6, route A) only in a separate
environment, so the Geant4 environment stays untouched.

## E0. Inputs and decisions (½ day, mostly the user)

Add to `geometry.yaml` (each value with its source, as now):

- **SiPMs** (user, 2026-10-12): model each SiPM as a **grounded 3 × 3 mm conducting plane, recessed 1 mm into the
  PTFE cylinder** (a 3 × 3 mm square hole, 1 mm deep, in the inner wall; the plane forms its bottom). No package, PCB,
  cables or foil in the model. Height: midway between rings 2 and 3 (z ≈ −25.3 mm; sheet −25 mm). Azimuths: the sheet
  says 0° / 90°, the data (`results/sipm_checks`, spread map) point to 90° / 180° — check and correct.
- **Field cage**: resistor values per step (gate → ring 1 → … → ring 4 → cathode; design 5 × 1 GΩ, ~5 GΩ measured in
  operation), gap gate ring → ring 1 (assumed 8 mm on the drawing).
- **Surroundings for the field**: grounded vessel (Ø146.86 mm) and the PTFE bucket are in the sheet; anything metallic
  closer to the SiPMs (cables, holders)?
- **Cases**: the Sept SR-2026.2 setting (anode +2.5, gate −2.5, cathode −3.25 kV, screens as logged), the Oct-2024
  setting, and the short-fill plan settings (REF-a, REF-c, BS2, BS3, CM-A, CM-B, S1D).

Decisions: route B first (below); route A only after E6-B. COMSOL licence at Nikhef? (would replace route A).

**Check:** sheet complete for all items above, or open items listed with a default and marked as assumed.

## E1. Model builder (½ day)

`build.py`: from `geometry.yaml` and a case, describe every region by its dielectric constant (LXe 1.96, GXe 1.00,
PTFE 2.1, liquid level 4 mm above the gate) and every conductor by its potential:

- meshes (top screen, anode, gate, cathode, bottom screen) as fixed-potential planes with their support rings;
- copper rings at the chain potentials (from the resistors; no current into the liquid);
- vessel at ground; PMT windows / bodies as grounded (or at their HV for the photocathode side — decide in E0);
- the 0.8 mm gap between the PTFE cylinder and the cathode foil, and the cathode – bottom-screen region;
- SiPM (E6 only): 3 × 3 mm plane at the bottom of a 1 mm deep square hole in the PTFE wall; grounded by default
  (option: a set voltage, e.g. for checks).

**Check:** plotted (r, z) section on top of the optical-model section (`optical/plot_section.py`): same positions of
meshes, rings, PTFE, level, bucket and vessel.

## E2. 2D axisymmetric field (1 day)

Finite differences on a non-uniform (r, z) grid (0.05–0.1 mm near meshes, rings, gaps and the liquid surface, coarser
towards the vessel), Laplace with varying ε (face values from the harmonic mean), solved with scipy sparse (direct
solver; ~10⁵–10⁶ points). Output: potential and field map on the grid, interpolator for E(r, z).

**Check:**

- parallel-plate test: the field in the centre of the drift region equals ΔV / d (gate – cathode) within 1 %;
- liquid / gas interface: E_gas / E_liq = 1.96 at the centre of the gate – anode gap;
- grid convergence: field at 10 test points changes < 0.5 % when the grid is halved;
- ring potentials and chain current: total current = (V_gate − V_cathode) / R_chain.

## E3. Mesh unit cell (optional, ½ day)

The 2D model treats the meshes as solid planes. One periodic 3D cell of the etched gate (and cathode) mesh — bars
from the sheet — at the real fields above and below gives the field leaking through the mesh: how far the extraction
field reaches into the drift region and the cathode – bottom-screen field into the drift region (hypotheses H1, H5).

**Check:** leakage of a parallel-wire grid against the analytic formula for the same pitch and wire size.

## E4. Drift tracker (½ day)

Electrons follow −E with the LXe drift velocity v(|E|) (literature parametrisation, scaled to the measured velocity
at the Sept field), optional longitudinal / transverse diffusion. Runge–Kutta steps with a step size set by the field
gradient. A drift line ends on: the liquid surface above the gate (good: S2), the PTFE wall, a SiPM / its foil, the
cathode or a ring. Output per start point (x, y, z): end type, end position, drift time, (x, y) at the gate.

**Check:** uniform field → straight lines and t = L / v; reversed field → all lines end on the cathode.

## E5. Validation with data, no SiPMs (1 day)

For the Sept setting and the Oct-2024 setting, start electrons on a grid (r 0–25 mm, z −51 … −1 mm):

- drift time versus z against the measured profile (`results/drift_profile`: slow near the cathode and the gate);
- maximum drift time against the measured cathode edge;
- fraction of drift lines from each (r, z) that reach the gate → predicted charge loss versus r and depth, compared
  with the measured apparent lifetime (≈ 300 µs centre, 40–75 µs at the wall, `results/sipm_checks`) and the spread map;
- radial shift of drift lines (field-cage inward / outward bending) against the position reconstruction.

**Check:** the drift-time profile is reproduced within the measurement errors. If the wall loss is NOT reproduced by
the bare geometry, that already says the cause is not the electrode layout alone (SiPMs, surface charge — E6, E7).

## E6. 3D SiPM model (1–2 days)

**Route B (first):** a 3D box around one SiPM (≈ 20 × 20 mm wide, 30 mm high: PTFE wall with the 3 × 3 × 1 mm hole,
the grounded 3 × 3 mm plane at its bottom, rings 2 and 3, part of the liquid inside), grid 0.1 mm (≥ 10 cells across
the hole and its depth), finite differences with ε and conductors as in E1, boundary potentials from the E2 map.
Solve with scipy (iterative, preconditioned; ~10⁶–10⁷ points).

**Check:** box-size convergence (field at the box edge undisturbed by the hole: < 1 % difference to 2D; result
unchanged when the box grows by 50 %); grid convergence in the hole (result unchanged at 0.05 mm).

Then drift lines from start points around the SiPM (all azimuths of the box, z −45 … −5 mm):

- where they end (SiPM / foil / wall / gate) per (azimuth, z) → local loss map;
- (x, y) shift at the gate → position and S2-AFT distortion near the SiPM;
- the Sept setting, CM-A and CM-B (SiPM at ≈ −1.45 kV and ≈ 0 V relative to the local potential).

**Route A (only if B shows a relevant effect, or for a paper):** the full TPC in 3D with both SiPMs, gmsh (geometry
from `geometry.yaml` via the OpenCASCADE kernel) + Elmer or FEniCSx, or COMSOL. Cross-check with route B in the SiPM
region (< 2 %).

## E7. PTFE surface charge (½ day)

Charge on the PTFE (inner wall, inside the SiPM hole, on an insulating foil) cannot be predicted. Add a surface charge
density σ per region as a case parameter; scan σ and find what σ is needed to reproduce the measured wall loss (E5)
and the local effects near the SiPMs (E6). Compare with the charge that reaches the wall in a day of running (from the
rate × S2 electrons × lost fraction).

**Check:** σ = 0 reproduces E5 / E6; the field from a uniform σ on a cylinder matches the analytic value.

## E8. Run-plan cases: predictions before the fill (½ day)

All cases of the short-fill plan (`measurements/next_fill/plan/`): REF-a, REF-c, BS2, BS3, CM-A, CM-B, S1D, plus the
Sept setting. Per case one table row: drift-field non-uniformity, predicted wall-loss fraction (top / deep, centre /
wall), loss and shift near the SiPMs, drift-time range. CM-A and CM-B must give the same field inside the TPC except
near the SiPMs (and outside the cage) — that is the point of the test.

**Check:** CM-A vs CM-B difference confined to the SiPM region and the outside; BS2 / BS3 change only the cathode
region.

## E9. Link to the optical simulation (½ day)

- S2 origin: generate S2 light at the (x, y) where the drift line reaches the liquid surface instead of straight
  above the start point → expected AFT and position distortion near the SiPMs (re-use the existing S2 photon tables:
  the light map is in (x, y) of the S2, so this is a re-mapping, no new Geant4 runs needed).
- Extraction field map from E2 / E3 → S2 yield versus (x, y) (mesh sag, edge effects).

**Check:** with a uniform field the mapped AFT equals the present model.

## E10. Write-up (½ day)

Docs page (geometry for the field, cases, how to run), `results/efield/<case>/README.md`, a section in the results
note, logbook entry; the predictions table (E8) in `measurements/run_overview.md` next to the short-fill plan.

## Effort

| Part | Effort |
|---|---|
| E0–E2 (inputs, builder, 2D field) | ~2 days |
| E3–E5 (mesh cell, drift, validation) | ~2 days |
| E6 route B + E7 + E8 (SiPMs, surface charge, predictions) | ~2–3 days |
| E9–E10 | ~1 day |
| E6 route A (full 3D FEM), if needed | +2 days |

Minimum for the SiPM question before the short fill: E0, E1, E2, E4, E6-B, E8 (≈ 3–4 days). With the SiPM as a
grounded plane in a hole (no package or foil), E6-B is about 1 day.

## Open questions

1. SiPM azimuths: sheet 0° / 90°, data 90° / 180°.
2. ~~SiPM hole and grounding~~ settled (user, 2026-10-12): grounded 3 × 3 mm plane, 1 mm recessed. Foil and package
   not modelled; revisit only if the result is borderline.
3. Chain resistor values per step; gate ring → ring 1 gap.
4. PMT side of the field: grounded body / photocathode potential at the window (affects only the regions beyond the
   screens).
5. COMSOL licence available at Nikhef?
