# Step 6 — first physics results (2026-10-05)

Model v1 (`geometry.yaml` 2026-10-05), made by `tools/step6_results.py` from the scans `s2_optics`, `s2_rayleigh`,
`s1_optics`, `s2_ring` (`scans/*.yaml`; 10⁷ photons per S2 point, 10⁸ per S1 point). QE 0.33 on both PMTs (no
relative QE / gain difference), SiPM PDE 1. Everything outside the TPC region (|x|, |y| > 60 mm) is black.

## S2 top fraction (S2 uniform in the gas gap, r < 30 mm)

| knob (others in the middle of their range) | range | top fraction |
|---|---|---|
| all ranges together (level 2–4 mm, PTFE R 0.90–0.99, steel R 0.2–0.5) | | 0.532 – 0.585 |
| steel reflectivity | 0.2 → 0.5 | −0.022 |
| PTFE reflectivity (liquid) | 0.90 → 0.99 | −0.018 |
| PTFE specular fraction | 0 → 0.2 | −0.034 |
| Rayleigh length | 30 → 60 cm | −0.013 |
| liquid level | 2 → 4 mm | +0.009 |
| mesh-ring inner Ø (open value) | 62.5 → 72 mm | +0.004 |

Data (S2 > 20 kPE): no source 0.52, Na-22 0.38, Cs-137 0.29.

- The geometry and optics alone give 0.53–0.59: the low-load value of the data (0.52) is close to this, at the
  reflective end of the ranges. The Cs and Na values are not geometric — they follow the load (top-PMT gain drop).
- The liquid level hardly matters (+0.009 from 2 to 4 mm): Oct 2024 and now should have the same geometric top
  fraction.
- The top fraction falls from 0.61 at the centre to 0.52 at r = 29 mm (`s2_vs_r.png`).
- Caveat: the data top fraction in PE also contains the relative QE / gain calibration of top and bottom PMT;
  10 % relative QE difference moves it by ~0.025. Equal QE assumed here.
- Sector pattern (`s2_sectors.png`): each sector collects most light from S2s below it (I −x+y, II +x+y, III −x−y,
  IV +x−y); at the centre the four shares are 0.24–0.26.

## Light collection and where the light is lost (`losses.png`, level 4, PTFE R 0.95, steel R 0.35)

| | S2 | S1 |
|---|---|---|
| detected top PMT (QE incl.) | 4.4 % | 1.4 % |
| detected bottom PMT | 3.4 % | 6.3 % |
| reaches a photocathode, not converted (1 − QE) | 15.7 % | 15.6 % |
| mesh rings | 23 % | 21 % |
| leaves the TPC region (sideways) | 18 % | 9 % |
| mesh bars (anode / gate / top screen / cathode / bottom screen) | 9.7 / 7.0 / 3.5 / 3.2 / 2.0 % | 1.6 / 12.5 / 0.9 / 8.7 / 4.7 % |
| PTFE | 2.6 % | 8.9 % |
| PMT frame / body | 6.2 % | 6.9 % |
| bulk absorption LXe | 0.8 % | 2.2 % |

Only ~23 % of the S2 photons reach a photocathode. About 40 % go sideways into the rings or out of the TPC region;
how much of that comes back in reality depends on the parts outside the model (ring inner Ø is an open value; it
moves light between "rings" and "leaves" but not the top fraction).

## S1 (`s1_vs_z.png`)

Top fraction 0.11 at the cathode → 0.26 at the gate (average 0.177); light collection 6–9 % (mostly bottom), rising
with PTFE reflectivity. Total internal reflection at the liquid surface keeps S1 light in the liquid.

## Checks

- Seed / photon number: each point split into two halves with independent seeds agree (worst pull 2.2 over 39
  points).
- Limits: black walls and reflectivity 1 (step 4) behave as expected.
