# Step 8 with Cs-137 photopeak events only (geometry v4, 2026-10-09)

Data: `optical/targets/data_2026-10-09_photopeak.json` (`analysis_SR2026.2/studies/optsim_targets.py` with `PHOTOPEAK=1`,
read-only, central v4): Cs-137 Δ750 V (C28 + C29), single scatters, cS1 photopeak ±0.5 σ, 34 592 events. S2 ≈ 120 kPE,
S1 ≈ 1400 PE — no small signals. `python optical/step8_fit.py --targets=data_2026-10-09_photopeak.json --key=cs137
--out=step8_photopeak` (same 81-point grid, same method as `results/step8/`).

| | no source (step 8) | **Cs-137 photopeak** |
|---|---|---|
| best point | PTFE R 0.95, spec. 0.1, steel R 0.2, Rayleigh 45 | **same** |
| ε_S2 | 1.17 (1.11–1.23) | **0.31** (0.27–0.34) |
| ε_S1 | 0.74 (0.71–0.77) | **0.33** (0.30–0.35) |
| χ² S2 vs r / S1 vs z / u,v (7 / 11 / 24 dof) | 2.0 / 8.0 / 27.4 | 3.3 / 6.4 / 43.9 |
| data AFT centre / ring | 0.82 | **1.00** (sim 1.01–1.04) |
| steel R profile Δχ² (0.35 / 0.5) | +16.7 / +35.7 | +29 / +62 |

Reading:
- **No central dip** in the photopeak data: the dip belongs to the small no-source S2s (the extra population piled up at
  the reconstructed centre, `results/aft_maps/`).
- **ε_S2 = ε_S1** for large signals: one factor ≈ 0.32 = the load-induced top-PMT efficiency at Cs rates (the v2
  `f_top` corrects only part of it). The no-source difference ε_S2 1.17 vs ε_S1 0.74 is the small-signal loss of the
  top PMT on S1 (amstrax hit-only integration, `results/threshold_toy/`), not a QE ratio.
- The optical model reproduces S2 vs r and S1 vs z for photopeak events with the same optics as for the no-source data;
  low steel reflectivity is now strongly preferred.
