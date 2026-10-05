# Step 6 — first physics results (geometry v2, 2026-10-05)

Made by `tools/step6_results.py` from the scans `s2_optics` (27 points: level 2/3/4 mm × PTFE R 0.90/0.95/0.99 ×
steel R 0.2/0.35/0.5, 10⁷ photons each), `s2_rayleigh` (9), `s1_optics` (3 × 10⁸). Geometry v2 from the drawings
(grid assemblies, PTFE cylinder, copper field-shaping rings). QE 0.33 on both PMTs, SiPM PDE 1. Everything outside
|x|, |y| < 60 mm is black. (v1 results: git history.)

## S2 top fraction (S2 uniform in the gas gap, r < 30 mm)

| knob (others in the middle of their range) | range | top fraction |
|---|---|---|
| all ranges together (level 2–4 mm, PTFE R 0.90–0.99, steel R 0.2–0.5) | | 0.537 – 0.586 |
| PTFE specular fraction | 0 → 0.2 | −0.032 |
| steel reflectivity | 0.2 → 0.5 | ≈ −0.02 |
| PTFE reflectivity (liquid) | 0.90 → 0.99 | ≈ −0.02 |
| Rayleigh length | 30 → 60 cm | −0.013 |
| liquid level | 2 → 4 mm | +0.009 (0.557 → 0.566) |

- Vs r (level 4): 0.62 at the centre → 0.53 at r = 29 mm (`s2_vs_r.png`).
- Sector pattern (`s2_sectors.png`): each sector collects most light from S2s below it; at the centre the four
  shares are 0.24–0.26.

## Light collection and where the light ends (`losses.png`; level 4, PTFE R 0.95, steel R 0.35, copper R 0.3)

| | S2 | S1 |
|---|---|---|
| detected top PMT (QE incl.) | 4.3 % | 1.4 % |
| detected bottom PMT | 3.3 % | 6.3 % |
| reaches a photocathode, not converted (1 − QE) | 15.6 % | 15.7 % |
| leaves the TPC region sideways | 25.7 % | 15.0 % |
| mesh rings + foil rims | 13.2 % | 11.6 % |
| mesh bars anode / gate / top screen / cathode / bottom screen | 10.4 / 7.5 / 4.0 / 3.2 / 2.2 % | 1.9 / 13.4 / 1.1 / 8.9 / 5.2 % |
| PTFE | 2.8 % | 9.3 % |
| PMT frame / body | 6.8 % | 7.5 % |
| copper field-shaping rings | 0.02 % | 0.03 % |
| absorption in the liquid | 0.8 % | 2.3 % |

- Only ~23 % of the S2 photons reach a photocathode. The gate–anode gap is open sideways between the rings
  (r 36–46 mm), so ~39 % of the S2 light goes into the rings or out of the TPC region; how much of that returns in
  reality depends on the structure outside the model (TODO).
- The copper rings sit outside the PTFE and see almost no light.

## S1 (`s1_vs_z.png`)

Top fraction 0.11 at the cathode → 0.26–0.27 at the gate (average 0.18); light collection 7.1–8.3 % (mostly bottom),
rising with PTFE reflectivity.

## Checks

Each point split into two halves with independent seeds: worst pull 2.3 (s2_optics), 0.9 (s2_rayleigh), 0.5 (S1).
