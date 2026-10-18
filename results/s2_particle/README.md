# S2 check — Geant4 particle mode, Cs-137

`validation/s2_particle_check.py` on three runs of 2·10⁶ Cs-137 decays each (`xamssim particle config/runs/s2_*.yaml`,
~40 s per run). **Update 2026-10-18 (evening):** both cryostat vessels in the geometry (`XAMS_cryostat.pdf`) and the
source **outside the outer vessel**, 130 mm from the axis (outer tube r = 127 mm), at z = −26 mm (raised, short-fill
plan), −52 mm (cathode level) and −82 mm (30 mm below the cathode). Drift region = liquid xenon, r < 31 mm,
−51.8 < z < 0 mm; photopeak = E ≥ 655 keV in the drift region.

| | raised (−26) | cathode level (−52) | 30 mm below (−82) |
|---|---|---|---|
| events with a drift-region deposit | 13790 | 13237 | 10477 |
| photopeak fraction | 0.176 | 0.181 | 0.172 |
| photopeak events per 10⁶ decays | 1214 | 1196 | 898 |
| median depth of photopeak events (r < 22 mm) | -25.8 mm | -27.6 mm | -28.0 mm |

- **Spectrum:** photopeak at 662 keV, Compton edge at ~477 keV, backscatter bump near 200 keV, Ba K X-rays near 32 keV.
- **Cryostat:** compared with the earlier runs (source at 100 mm in what is now the vacuum, no outer vessel) the
  photopeak rate of the raised source falls from 2508 to 1214 per 10⁶ decays: distance (100 → 130 mm, ×0.59) and the
  2.77 mm steel of the outer tube (~15 % at 662 keV); the photopeak fraction drops from 0.205 to 0.176 (scattering in
  the wall).
- **Depth profile:** the photopeak events spread over the whole drift region, nearly independent of the source height;
  the photopeak rate does depend on it.
- **Comparison with September data:** the data profile (z from a linear drift-time scale, clean cuts) is U-shaped and
  not reproduced by any height (χ² ≈ 160–170 / 20); the linear z(t) is distorted by the slow drift near the cathode
  and the gate — the comparison needs the drift model of S4. Not a Geant4 problem.

Model notes: source = ion at rest in a 1 mm steel capsule; outside the outer vessel the world is vacuum (no lab);
PMT bodies and frames Kovar, dead crosses steel; EM physics option 4, production cut 0.1 mm.
