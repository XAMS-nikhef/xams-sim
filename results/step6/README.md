# Step 6 — first physics results (geometry v3, 2026-10-05; figures and summary.json geometry v4, 2026-10-07)

**Geometry v4 (2026-10-07):** all step-6 scans rerun with the PTFE bucket, cryostat vessel and PMT holders; figures and
`summary.json` are v4. Top fractions change by < 0.006; light collection +6–7 % (PMT holders); the "leaves the TPC
region" share of v3 (S2 22 %, S1 11 %) now ends on the vessel (S2 10 %), bucket (1.7 %), copper rings (1.7 %) and more
on the meshes / rings. The text below gives the v3 numbers.

Made by `tools/step6_results.py` from the scans `s2_optics` (27 points: level 2/3/4 mm × PTFE R 0.90/0.95/0.99 ×
steel R 0.2/0.35/0.5, 10⁷ photons each), `s2_rayleigh` (9), `s1_optics` (3 × 10⁸). Geometry v3: everything from the
drawings — grid assemblies, PTFE cylinder, copper field-shaping rings, and the mesh foils as built (solid foil with
456 etched holes). QE 0.33 on both PMTs, SiPM PDE 1. Everything outside |x|, |y| < 60 mm is black.

## S2 top fraction (S2 uniform in the gas gap, r < 30 mm)

| knob (others in the middle of their range) | range | top fraction |
|---|---|---|
| all ranges together (level 2–4 mm, PTFE R 0.90–0.99, steel R 0.2–0.5) | | 0.531 – 0.584 |
| PTFE specular fraction | 0 → 0.2 | −0.034 |
| steel reflectivity | 0.2 → 0.5 | −0.021 |
| PTFE reflectivity (liquid) | 0.90 → 0.99 | −0.020 |
| Rayleigh length | 30 → 60 cm | −0.014 |
| liquid level | 2 → 4 mm | +0.010 (0.553 → 0.563) |

- Vs r (level 4): 0.62 at the centre → 0.52 at r = 29 mm (`s2_vs_r.png`).
- Sector pattern (`s2_sectors.png`): each sector collects most light from S2s below it; at the centre the four
  shares are 0.24–0.26.

## Light collection and where the light ends (`losses.png`; level 4, PTFE R 0.95, steel R 0.35, copper R 0.3)

| | S2 | S1 |
|---|---|---|
| detected top PMT (QE incl.) | 4.3 % | 1.4 % |
| detected bottom PMT | 3.3 % | 6.3 % |
| reaches a photocathode, not converted (1 − QE) | 15.4 % | 15.5 % |
| leaves the TPC region sideways | 21.9 % | 11.3 % |
| mesh foils anode / gate / top screen / cathode / bottom screen | 12.3 / 9.7 / 6.0 / 3.7 / 3.5 % | 2.6 / 15.7 / 1.6 / 10.5 / 7.8 % |
| mesh rings + foil rims | 10.3 % | 8.9 % |
| PTFE | 2.6 % | 9.1 % |
| PMT frame / body | 6.1 % | 6.8 % |
| copper field-shaping rings | < 0.1 % | < 0.1 % |
| absorption in the liquid | 0.8 % | 2.2 % |

- Only ~23 % of the S2 photons reach a photocathode (7.6 % detected). The mesh foils take 35 % (the solid band
  outside the etched area included), and ~32 % go sideways into the rings or out of the model.
- The copper rings sit behind the PTFE and see almost no light.

## S1 (`s1_vs_z.png`)

Top fraction 0.11 at the cathode → 0.25–0.27 at the gate (average 0.18); light collection 7.0–8.2 % (mostly bottom),
rising with PTFE reflectivity.

## Checks

Each point split into two halves with independent seeds: worst pull 1.8 (s2_optics), 1.2 (s2_rayleigh), 1.0 (S1).
