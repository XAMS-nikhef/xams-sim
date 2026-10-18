# Drift-velocity profile from the S1 area fraction top (2026-10-12)

`python optical/drift_profile.py`: Cs-137 Δ750 V (28/29-09), r < 15 mm, S1 ≥ 20 PE in top and bottom, gate-corrected S2
width > 450 ns (no drift-time or S1-AFT consistency cut). Model: z(t) piecewise linear with nodes every 6.2 µs from
t_gate = 1.15 µs (z = 0) to t_cathode = 38.2 µs (z = −51.8 mm); the 5 inner node depths and ε_S1 fitted to 1 µs medians
of the S1 AFT with the simulated S1 AFT(z) (best optics). Two samples: photopeak (30 k events) and all Cs events with
S1 100–3000 PE (211 k).

| segment (µs) | 1.2–7.3 | 7.3–13.5 | 13.5–19.7 | 19.7–25.9 | 25.9–32.0 | 32.0–38.2 |
|---|---|---|---|---|---|---|
| photopeak, all | 0.84 | 1.59 | 1.48 | 1.32 | 2.23 | 0.92 |
| all Cs, all | 0.90 | 1.74 | 1.66 | 1.65 | 1.79 | 0.65 |
| all Cs, y > 0 | 1.02 | 1.78 | 1.42 | 1.75 | 1.72 | 0.70 |
| all Cs, y < 0 | 1.12 | 1.48 | 1.98 | 1.53 | 0.99 | 1.29 |

(mm/µs; statistical errors 0.01–0.1, mean for a uniform field 1.40.)

- **Limited by the simulated S1 shape, not by statistics:** χ² 168 / 30 (photopeak), 1412 / 30 (all Cs) with statistical
  errors only — the model shape is not good to the 10⁻³ level of the data, and the node depths absorb shape mismatches.
  A first attempt by inverting the absolute S1 AFT, and a local-slope version, were dominated by the ε scale and by
  noise respectively.
- Robust across samples: **slower drift in the last ~6 µs before the cathode** (0.65–0.93 mm/µs; y < 0: 1.29) and in the
  first ~6 µs below the gate (0.84–1.12). The cathode part agrees with the drift-time spectrum (pile-up of 2–3× before
  the cathode, smeared cathode edge): a weak field near the cathode.
- The middle segments scatter between 1.3 and 2.2 mm/µs between samples: no ring-level kink can be resolved with
  this method. The y-difference near the cathode (0.70 vs 1.29) is suggestive but within the method's systematics.
