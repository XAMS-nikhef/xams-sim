# Low S2 area fraction top at y < 0: channels, top vs bottom, depth (2026-10-09)

Data: `analysis_SR2026.2/studies/s2_channels.py` (stbc-i2, read-only, central v4): single scatters at Δ750 V, S2 area
per channel from the stored peaks (matched to the main S2 by time; `event_area_per_channel` fails to compute in this
amstrax), LED gains. Simulation: per-sensor light map, 81 fit_s2 points pooled (geometry v4).
`python tools/channel_test.py` → `channel_test.png`, `low_region_vs_drift.png`, `summary.json`.

**A. Channel calibration is fine.** Relative top gains that make the measured channel shares match the simulation:
0.97 / 1.02 / 0.96 / 1.04 (ch1–4), the same from the Cs-137 photopeak and from no-source S2 > 20 kPE; share rms
0.013 → 0.011. (Also implied by the position reconstruction working: a ch3/ch4 error large enough for the deficit,
35–40 %, would shift v by 0.15–0.2.)

**B. Cs-137 photopeak versus x and y** (strips |x|, |y| < 6 mm, data ÷ simulated light collection, ÷ centre): top and
bottom move together (S2 yield varies ±25 %), the top/bottom ratio is flat within ±5 % except at the lower edge.

**C. The deficit is a depth-dependent region, not geometry of the S2 alone.** On x-y (and in raw u-v, no
reconstruction) the top/bottom ratio drops abruptly to 0.55–0.7 × the model in an arc at y < 0, r ≈ 10–18 mm, next to
cells with almost no events. AFT in that region versus drift time (S2 > 50 kPE):

| | 0–3 µs | 3–6 | 6–10 | 10–15 | 25–30 | 30–35 | 35–41 µs |
|---|---|---|---|---|---|---|---|
| no source, y < 0 region | 0.41 | 0.42 | 0.42 | 0.42 | 0.47 | 0.56 | 0.57 |
| no source, mirror y > 0 | 0.50 | 0.54 | 0.54 | 0.54 | 0.55 | 0.55 | 0.55 |

Same on 28-09 and 29-09 and for Cs-137 (0.21–0.22 vs 0.28 at drift < 20 µs; 0.30–0.31 vs 0.30–0.31 deeper). Events in
the region: shallower (median drift 4.3 vs 10.8 µs), wider S2 (width50 739 vs 624 ns), smaller S1 (399 vs 787 PE).

Reading: the AFT of an S2 should depend only on where its light is made. At the same reconstructed (and raw u-v)
position, S2s from shallow interactions at y < 0 have ~20 % less top light per bottom light than S2s from deep ones,
and less than anywhere in the model (minimum 0.52). So their S2 light is not made where normal S2s are. Working
hypothesis: a drift-field distortion in the upper part at y < 0 (field cage / resistor chain, cf. the 1.2 µs longer
cathode drift time for y > 0) sends electrons from shallow interactions there to the edge of the extraction region,
where the S2 light is partly hidden from the top PMT (ring / foil rim), and the light pattern is reconstructed inward.
Wider S2s and the empty cells next to the region fit this. To check: event display of region events; S2 width / rise
time vs drift; electric-field calculation with a broken field-cage connection.
