# Ring shadows in the drift-time spectrum? (2026-10-12, quick look)

Δ750 V single scatters (r < 20 mm, S1 ≥ 20 PE in top and bottom; `analysis_SR2026.2/outputs/s2_channels.npz`), Cs-137
(392 k events) and no source (29 k), 0.25 µs bins. Expected ring times for a uniform field (1.40 mm/µs, gate 1.15 µs):
8.7 / 15.8 / 22.8 / 29.8 µs. In M. Flierman's thesis (p. 118, 194) the source data show dips there — shadows of the
copper rings for an external source; background data have none.

| ring time | 8.7 µs | 15.8 µs | 22.8 µs | 29.8 µs |
|---|---|---|---|---|
| Cs-137 ÷ neighbourhood (±0.75 µs vs 1.5–3.5 µs away) | 0.997 ± 0.008 | 0.949 ± 0.009 | 0.987 ± 0.010 | 0.966 ± 0.009 |

- No clear shadows: at most 3–5 % at two of the four rings, similar to fluctuations elsewhere (12.6, 24.1 µs). A level,
  distant source would give much deeper dips (~50 % absorption in 10 mm Cu at 662 keV) → the shadows are washed out,
  most likely by the source geometry (not level / close / off-axis; the Cs events concentrate at x < 0, y > 0).
- Both spectra (with and without source) rise ×2–3 towards the gate and the cathode: for events spread evenly in z the
  rate per µs is ∝ 1/v, so the drift is slower at both ends — a field effect (present without source), consistent with
  the S1-AFT profile (`results/drift_profile/`).
- Next: a collimated z-scan (lead slit or Na-22 + NaI coincidence) gives t(z) at known heights directly.
