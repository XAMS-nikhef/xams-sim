# Step 7 — targets from the data (2026-10-05)

Data: `analysis_SR2026.2/studies/optsim_targets.py` (stbc-i2, read-only, central v4 = gains v2 + pos_rec_map v0),
copied to `targets/data_2026-10-05.json`. Δ750 V runs of 28/29-09: no source (B28, B29), Na-22 (N28, N29), Cs-137
(C28, C29); S1 and S2 present, no saturated S2 channel, r < 25 mm, −51.3 < z < −0.5 mm. Area fractions with LED gains
only (the v2 load correction `f_top`, `b_hv` undone). Comparison: `tools/step7_compare.py` → `compare.png`
(simulation band = all optics points at the 4 mm level, equal QE top / bottom).

## Top-sector pattern (u, v vs position) — matches

u = (ch1+ch3−ch2−ch4)/top along x, v = (ch1+ch2−ch3−ch4)/top along y (S2 3–20 kPE): the data lie inside the narrow
simulation band over the full ±24 mm (slope ~0.044 /mm at the centre, ±0.66 at 24 mm), and are the same for every
source. This tests the geometry directly (top-PMT height above the S2, sector layout, light spread through the anode
and top screen): **the geometry is right**. (Frames: x_data = −x_sim, y_data = y_sim.)

## S2 area fraction top

| | S2 3–5 kPE | 5–10 | 10–20 | 20–50 | 50–100 | > 100 kPE |
|---|---|---|---|---|---|---|
| no source | 0.68 | 0.60 | 0.55 | 0.50 | 0.50 | 0.49 |
| Na-22 | 0.53 | 0.48 | 0.43 | 0.38 | 0.37 | 0.36 |
| Cs-137 | 0.40 | 0.37 | 0.33 | 0.29 | 0.28 | 0.27 |
| simulation | 0.555 – 0.60 (r < 25 mm, all optics) | | | | | |

- Falls with source rate (load on the top PMT) and with S2 size up to ~20 kPE, then flat.
- Versus r (3–20 kPE, no source): **dip at the centre** — 0.50 (r < 2.5 mm), 0.52 (2.5–5), 0.63–0.65 (5–15),
  0.54 at 24 mm; the same relative shape for every source. The simulation falls smoothly from 0.62 to 0.54.
  Top/bottom ratio data/simulation: 0.61, 0.69 (r < 5 mm), 1.08–1.20 (5–20 mm), 1.00 at the edge. Candidates: an
  insensitive cross between the four anodes of the top PMT (the posrec light-response fit has a 1.5 mm gap); a
  position-reconstruction bias near u = v = 0. Not in the model yet.

## S1 area fraction top vs z (S1 > 20 PE, mean)

No source: 0.085 (z −50) → 0.188 (z −6) mm; the simulation has the same shape but higher: the top/bottom ratio
data/simulation is **0.72 ± 0.02 at every z** (0.70–0.76) — one constant efficiency factor, not geometry. Likely the
small-signal integration loss for the top anodes (isolated photons keep ~55–60 % of their charge; TODO), and/or a
top/bottom QE ratio. Na-22 and Cs-137 are 1.6× and 2.6× lower again (load).

## Not done

- Oct 2024 (run 6786, 2 + 6 mm): needs its own gains / processing; left for later (the simulation predicts only +0.01
  difference in S2 top fraction between the levels).
- QE top / bottom: free in step 8 (only the ratio matters).

## For step 8

Fit with an efficiency ratio for S2 (QE ratio) and one for S1 (QE ratio × small-signal factor): S2 AFT vs r outside
the centre (no source, 3–20 kPE), S1 AFT vs z shape, u/v profiles. Then test the centre dip with an insensitive cross
on the top PMT.
