# Step 7 — data vs simulation (geometry v3, 2026-10-05)

**Default since 2026-10-06: single scatters** (no alternative S2; `targets/data_2026-10-05_single.json`,
`top_bottom_vs_r_cs137_single.json`; figures made with them). The tables below are for all events unless marked;
single-scatter numbers are in the section "Single scatters only".

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
  shape for every source (statistical errors 0.003–0.009); the simulation falls smoothly 0.62 → 0.52. Top/bottom ratio data/simulation 0.61, 0.68
  (r < 5 mm), 1.07–1.21 (5–20 mm), 1.02 at the edge. An insensitive cross between the four anodes of the top PMT is
  excluded as the cause (step 8); position-reconstruction bias near the centre remains the candidate.

### Central dip versus S2 size (threshold test, `central_dip_vs_size.png`)

Idea (user): at the centre the top charge is shared over four channels, so more of each channel's S2 tail falls below
the hit threshold, lowering the top area. Such a loss shrinks with S2 size. Data (no source, LED gains, ± statistical):

| S2 size | AFT r < 2.5 mm | AFT r 7.5–12.5 mm | centre / ring |
|---|---|---|---|
| 3–5 kPE | 0.53 | 0.74–0.82 | 0.68 ± 0.02 |
| 5–10 kPE | 0.50 | 0.67–0.68 | 0.73 ± 0.01 |
| 10–20 kPE | 0.49 | 0.62–0.63 | 0.79 ± 0.01 |
| 20–50 kPE | 0.48 | 0.51–0.55 | 0.91 ± 0.004 |
| 50–300 kPE | 0.51 | 0.55–0.56 | 0.93 ± 0.005 |
| simulation | | | 1.01–1.04 |

The dip shrinks with S2 size, but because the **ring** value falls with size (0.82 → 0.55); the **centre stays at
≈ 0.50 for every size**. A pure threshold loss from charge sharing would make the centre rise with S2 size, which is
not seen. Two size effects seem to overlap: the area fraction top falls with S2 size where the light is concentrated
on one top channel (per-channel non-linearity at large signals?), and the centre, where the light is shared, is low
and flat. To settle it: compare per channel the peak area with the fully integrated waveform (raw records) for central
and off-centre events.

### Top deficit or bottom excess? (`top_bottom_vs_r.png`)

The area fraction top cannot tell whether the top sees less or the bottom more. Cs-137 photopeak (fixed S2 per
event, ~120 kPE; LED gains; `analysis_SR2026.2/scratch/top_bottom_vs_r.py` → `targets/top_bottom_vs_r_cs137.json`),
each ÷ its value at r = 7.5–12.5 mm:

- **Centre (r < 2.5 mm):** top 0.95 and bottom 0.93 — both lower, the bottom does *not* see more; total S2 light 0.93
  on both days (S2 production lower at the very centre — not optics). The area fraction top is 1.02 (simulation
  1.01–1.04): **no central dip for large S2s** — the dip of the small S2s (3–20 kPE) is a small-signal effect.
- **Outwards:** the bottom rises to 1.08–1.15 at r ≈ 19 mm where the simulation falls to 0.96, and the total stays
  ≈ 1.0–1.08 where the simulation falls to 0.9; the area fraction top falls faster than simulated (0.87 vs 0.94 at
  19 mm, 0.77 vs 0.89 at 24 mm). Either the S2 yield rises outwards, or light that leaves the modelled region
  sideways (black in the model) comes back in reality and reaches the bottom PMT — the surrounding-structure TODO.

### Single scatters only (no alternative S2, `alt_s2_index < 0`)

Same selections with the strict cut (`targets/*_single.json`): it keeps only 20 % (no source), 22 % (Na-22), 25 %
(Cs-137) of the events — most events have some second S2.

- **Central dip of the small S2s survives** (no source, S2 3–50 kPE: centre / ring 0.69–0.87, centre ≈ 0.48–0.54) —
  not a multiple-scatter effect. For S2 > 50 kPE it disappears (1.02).
- **Cs-137 photopeak:** the outward bottom excess was a multiple-scatter effect. Single scatters: bottom / ring 0.93
  and 0.86 at r ≈ 19 mm (all events 1.15 / 1.08), total S2 light 0.89 / 0.81 at 19 mm and 0.51 / 0.44 at 24 mm
  (strong loss near the wall, more than the optical 0.78), area fraction top 0.90–0.92 at 24 mm (simulation 0.88–0.90;
  all events 0.77–0.78). Centre: area fraction top 1.00, no dip.
- No-source S2 vs r (3–20 kPE): 0.51 (centre) … 0.65 … 0.59 at 24 mm (all events 0.54 there).
- **Loose cut** (alternative S2 below 5 % of the main S2; `targets/*_alt0.05.json`): keeps 30 % (no source) / 33 %
  (Cs) and lies between all events and single scatters, close to single scatters (no source S2 vs r: 0.50 … 0.65 …
  0.56; Cs photopeak area fraction top at 24 mm 0.86–0.89).
- S1 area fraction top: single / all 0.91–0.94 near the cathode, ~1.05 in the middle — the depth profile is steeper
  for single scatters.

## S1 area fraction top vs z

Same shape as the simulation; top/bottom ratio data/simulation **0.72 at every z** (0.71–0.77): one efficiency factor
(small-signal integration loss for isolated photons on the top anodes and/or a top/bottom QE ratio), not geometry.
Na-22 and Cs-137 are 1.6× and 2.6× lower again (load).

## Not done

Oct 2024 (run 6786); QE ratio top / bottom left free.
