# Step 8 — fit to the data and the dead-cross test (geometry v3, 2026-10-05)

`tools/step8_fit.py` on the scans `fit_s2` / `fit_s1` (81 points each: PTFE reflectivity 0.90 / 0.95 / 0.99 ×
PTFE specular fraction 0 / 0.1 / 0.2 × steel reflectivity 0.2 / 0.35 / 0.5 × Rayleigh length 30 / 45 / 60 cm,
level 4 mm; 10⁷ S2 and 2·10⁷ S1 photons per point) and `deadcross_s2`. Data: `targets/data_2026-10-05.json`, no-source
runs, LED gains.

## Method

- Observables, binned exactly like the data: S2 area fraction top vs r (S2 3–20 kPE; r ≥ 5 mm, the central dip is
  treated separately), S1 area fraction top vs z (11 slices, the slice at the gate excluded), top-sector asymmetries
  u(x), v(y).
- Per grid point two efficiency factors are fitted: ε_S2 and ε_S1 multiply the top/bottom ratio AFT/(1 − AFT). They
  absorb the QE ratio of the two PMTs and the top-PMT efficiency for S2 / for small S1 signals. The optical
  parameters are then constrained by the **shapes** only.
- χ² = simulation statistics, data statistics (σ/√n, ×1.25 for medians) plus a systematic floor (S2 0.010, S1 0.004, u/v 0.010 absolute). The floors are a
  choice: absolute χ² values depend on them, differences between points are what matter. Degrees of freedom: 7 (S2),
  11 (S1), 45 (u, v).

## Results

| | value |
|---|---|
| best grid point | PTFE R 0.99, PTFE specular 0.1, steel R 0.2, Rayleigh 60 cm |
| χ² (S2 vs r / S1 vs z / u, v) | 11.2 / 1.6 / 40.6 for 7 / 11 / 45 dof |
| **ε_S2** (top/bottom data ÷ simulation, S2) | **1.13** (1.06–1.21 over the 10 best points) |
| **ε_S1** (same for S1) | **0.77** (0.71–0.80) |

Profiles (minimum χ² over the other parameters, Δχ² vs the best point):

| parameter | low | middle | high |
|---|---|---|---|
| PTFE reflectivity 0.90 / 0.95 / 0.99 | +4.2 | +10.0 | 0 |
| PTFE specular 0 / 0.1 / 0.2 | +35 | 0 | +4.2 |
| steel reflectivity 0.2 / 0.35 / 0.5 | 0 | +4.2 | +33 |
| Rayleigh 30 / 45 / 60 cm | +7.6 | +15.5 | 0 |

## Reading

- **The shapes are reproduced.** S1 vs z matches within the floor at every depth (χ² 1.6 for 11 slices) once the top
  is scaled by ε_S1; the sector pattern matches over ±24 mm; S2 vs r agrees within ~0.015 from 6 to 19 mm, the data
  fall faster at the edge (0.54 vs 0.56 at r = 24 mm).
- **Two efficiency factors, not one.** ε_S2 ≈ 1.13 and ε_S1 ≈ 0.77 cannot both be a QE ratio. If the QE ratio
  top/bottom is ~1.1, the top PMT keeps only ~0.68 of its S1 signal relative to the bottom — consistent with the
  small-signal integration loss found earlier (isolated photons keep 55–60 % of their charge on the top anodes,
  TODO item "Small-signal integration in amstrax"). Note that ε_S2 depends on the S2 size chosen (the data AFT falls
  with S2 size, step 7), so it is an upper limit for the QE ratio.
- **Optical parameters: only weakly constrained.** The data prefer a low steel reflectivity (0.2 rather than 0.5) and
  a small specular PTFE component (0.1–0.2 rather than 0), both through the sector pattern. PTFE reflectivity and
  Rayleigh length are not constrained: their profiles are not monotonic, i.e. within the scatter of the u/v term
  (10⁷ photons per point). A finer grid with more photons would be needed to go further; the S1 and S2 *shapes*
  hardly depend on any of the four parameters inside their ranges.
- **The dead cross is not the cause of the central dip.** An insensitive cross between the top sectors of 1.5 / 3 /
  6 mm lowers the centre by at most 3 % (centre / ring 1.03 → 1.00) — the data have 0.79 — and a 6 mm cross spoils
  u(x), v(y). The dip must come from elsewhere — see the S2-size test in `results/step7/README.md` (the centre stays at
  ≈ 0.50 for every S2 size while the ring value falls with size: a signal-processing / per-channel effect of the top
  PMT is more likely than geometry).

Figures: `best_fit.png` (best point vs data, profiles), `dead_cross.png`. Table of all points: `fit_table.csv`.
