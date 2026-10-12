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

## Photopeak events and expected shadow depth (2026-10-12)

- Cs-137 photopeak at the standard position (`photopeak_shadows.png`, 17.6 k events, r < 20 mm): no dip beyond the
  ±5–8 % noise at or near the ring times either. The photopeak density rises ~3× towards the cathode (0.011 → 0.03 per
  0.4 µs), more than all single scatters.
- Ray-trace of the shadows (point source on the side at distance d from the axis and height h; copper rings r 36–46.3
  mm, 1.8 mm high, μ_Cu = 0.066 /mm; interactions uniform in r < 20 mm; no scattering), deepest expected dip in 0.4 µs
  bins:

| d | h = −26 mm | −45 mm | −65 mm | −90 mm |
|---|---|---|---|---|
| 85 mm | 0.85 | 0.86 | 1.00 | 0.99 |
| 110 mm | 0.71 | 0.72 | 0.99 | 1.00 |
| 175 mm | 0.59 | 0.68 | 0.98 | 0.99 |
| 300 mm | 0.52 | 0.56 | 0.87 | 0.99 |

- A source aimed at the drift region from ≥ 11 cm would give 30–50 % dips — not seen. Consistent: a source below the
  drift region (h ≲ −60 mm) or right at the vessel. With the photopeak rising towards the cathode: the standard
  position was most likely low (near / below cathode level). Next fill: source level with the drift region at ≥ 10 cm,
  height noted — gives even depth coverage and ring shadows as a free depth / field check.
