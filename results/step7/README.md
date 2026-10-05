# Step 7 — data vs simulation (geometry v3, 2026-10-05)

Data: `analysis_SR2026.2/studies/optsim_targets.py` (stbc-i2, read-only, central v4 = gains v2 + pos_rec_map v0) →
`targets/data_2026-10-05.json`. Δ750 V runs of 28/29-09: no source (B28, B29), Na-22 (N28, N29), Cs-137 (C28, C29);
S1 and S2, no saturated S2 channel, r < 25 mm, −51.3 < z < −0.5 mm; area fractions with LED gains only (the v2 load
correction undone). `tools/step7_compare.py` → `compare.png` (simulation band = all optics points at the 4 mm level,
equal QE top / bottom).

## Top-sector pattern — matches

u = (ch1+ch3−ch2−ch4)/top along x, v = (ch1+ch2−ch3−ch4)/top along y (S2 3–20 kPE): the data lie inside the
simulation band over ±24 mm, the same for every source. **The geometry is right.** (x_data = −x_sim.)

## S2 area fraction top

| | 3–5 kPE | 5–10 | 10–20 | 20–50 | 50–100 | > 100 kPE |
|---|---|---|---|---|---|---|
| no source | 0.68 | 0.60 | 0.55 | 0.50 | 0.50 | 0.49 |
| Na-22 | 0.53 | 0.48 | 0.43 | 0.38 | 0.37 | 0.36 |
| Cs-137 | 0.40 | 0.37 | 0.33 | 0.29 | 0.28 | 0.27 |
| simulation (r < 25 mm) | 0.554 – 0.597 | | | | | |

- Falls with source rate (load on the top PMT) and with S2 size up to ~20 kPE: not geometric.
- Vs r (no source, 3–20 kPE): **dip at the centre** (0.50 at r < 2.5 mm, 0.63–0.65 at 5–15 mm, 0.54 at 24 mm), same
  shape for every source; the simulation falls smoothly 0.62 → 0.52. Top/bottom ratio data/simulation 0.61, 0.68
  (r < 5 mm), 1.07–1.21 (5–20 mm), 1.02 at the edge. An insensitive cross between the four anodes of the top PMT is
  excluded as the cause (step 8); position-reconstruction bias near the centre remains the candidate.

## S1 area fraction top vs z

Same shape as the simulation; top/bottom ratio data/simulation **0.72 at every z** (0.71–0.77): one efficiency factor
(small-signal integration loss for isolated photons on the top anodes and/or a top/bottom QE ratio), not geometry.
Na-22 and Cs-137 are 1.6× and 2.6× lower again (load).

## Not done

Oct 2024 (run 6786); QE ratio top / bottom left free.
