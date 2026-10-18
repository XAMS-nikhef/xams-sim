# Low S2 area fraction top at y < 0: channels, top vs bottom, depth (2026-10-09)

Data: `analysis_SR2026.2/studies/s2_channels.py` (stbc-i2, read-only, central v4): single scatters at Δ750 V, S2 area
per channel from the stored peaks (matched to the main S2 by time; `event_area_per_channel` fails to compute in this
amstrax), LED gains. Simulation: per-sensor light map, 81 fit_s2 points pooled (geometry v4).
`python optical/channel_test.py` → `channel_test.png`, `low_region_vs_drift.png`, `summary.json`.

**A. Channel calibration is fine.** Relative top gains that make the measured channel shares match the simulation:
0.98 / 1.03 / 0.95 / 1.04 (ch1–4, Cs-137 photopeak) and 0.97 / 1.02 / 0.97 / 1.04 (no-source S2 > 20 kPE); share
rms 0.012–0.013 → 0.009–0.011. (Also implied by the position reconstruction working: a ch3/ch4 error large enough for the deficit,
35–40 %, would shift v by 0.15–0.2.)

**B. Cs-137 photopeak versus x and y** (strips |x|, |y| < 6 mm, data ÷ simulated light collection, ÷ centre): top and
bottom move together (S2 yield varies ±15–20 %), the top/bottom ratio is flat within ~5 % except at the edges.
(Photopeak band cS1 1247–1511 PE from the edge fit on stbc-i2; a first version used a local peak search that
landed in the Compton region — corrected 2026-10-09.)

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

**Not a slow channel** (anode 4 has a ~30 ns tail): the deficit is the same on the ch4 side (lower left, top/bottom ÷
sim 0.51) and the ch3 side (lower right, 0.52), and the top-channel shares stay normal (±10 %, the same for shallow and
deep events) — the top light keeps its pattern, only top vs bottom changes.

**Photopeak events show it only mildly.** Cs-137 photopeak (fixed energy) in the region vs mirror at the same drift
time: AFT 0.24 / 0.26 / 0.28 vs 0.27 / 0.28 / 0.30 for drift 0–5 / 5–10 / 10–20 µs (×0.88–0.95; 70–105 events per bin),
equal deeper. The strong deficit of the S2 > 50 kPE samples belongs to events with an S1 too small for their S2
(median S1 399 vs 787 PE in the mirror region). Alternative to the field-distortion picture: interactions outside the
active volume (liquid between the PTFE wall and the outer structures at y < 0) whose S1 is shielded by the PTFE and whose
electrons reach the extraction region at its edge. Test: cS2/cS1 and S1-AFT versus drift-time z of these events.
