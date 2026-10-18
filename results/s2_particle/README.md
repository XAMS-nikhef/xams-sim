# S2 check — Geant4 particle mode, Cs-137 (2026-10-18)

`validation/s2_particle_check.py` on three runs of 2·10⁶ Cs-137 decays each (`xamssim g4 config/runs/s2_*.yaml`,
~35 s per run on the Mac): source 100 mm from the axis at z = −26 mm (raised, short-fill plan), −52 mm (cathode
level) and −82 mm (30 mm below the cathode). Drift region = liquid xenon, r < 31 mm, −51.8 < z < 0 mm; photopeak =
E ≥ 655 keV in the drift region.

| | raised (−26) | cathode level (−52) | 30 mm below (−82) |
|---|---|---|---|
| events with a drift-region deposit | 24 514 | 22 040 | 16 286 |
| photopeak fraction | 0.205 | 0.208 | 0.191 |
| photopeak events per 10⁶ decays | 2508 | 2291 | 1553 |
| median depth of photopeak events (r < 22 mm) | −26.2 mm | −27.3 mm | −29.1 mm |

- **Spectrum:** photopeak at 662 keV, Compton edge at 477 keV (all three; the automatic edge finder gave 512 keV for
  the lowest source — noise of the finder, the plot shows 477), backscatter bump near 200 keV, Ba K X-rays near 32 keV.
- **Depth profile:** at 100 mm distance the photopeak events are spread over the whole drift region and depend only
  weakly on the source height; the photopeak *rate* does depend on it (−38 % from raised to 30 mm below the cathode).
- **Comparison with September data:** the data profile (z from a linear drift-time scale, clean cuts) is U-shaped —
  high near the cathode and near the gate — and is not reproduced by any height (χ² ≈ 280–340 / 20). The linear
  z(t) is distorted by the slow drift near the cathode and the gate (`results/drift_profile`), which piles events up at
  both ends: the comparison needs the drift model of S4 (compare in drift time, not in z). Not a Geant4 problem.

Model notes: source = ion at rest in a 1 mm steel capsule (stops the decay recoil and the betas); outside the vessel the
world is vacuum (no outer cryostat, no lab materials); PMT bodies and frames are Kovar, dead crosses steel; EM physics
option 4, production cut 0.1 mm.
