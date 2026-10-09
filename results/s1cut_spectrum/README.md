# S1-AFT / drift-time consistency cut: energy spectrum and the data–simulation comparison (2026-10-09)

Cut (`analysis_SR2026.2/studies/optsim_targets.py` S1CUT=1, copy in `tools/s1cut_spectrum.py`): S1 AFT (LED gains)
within 3σ of the median S1 AFT versus drift time of normal events (S2 > 20 kPE, r < 18 mm); σ from the MAD per S1-size
bin; S1 < 20 PE removed. Not applied to S1 vs z (circular).

**Energy spectrum** (`python tools/s1cut_spectrum.py`, single scatters, r < 20 mm, drift 2–38 µs): the cut removes
1.8 % of the Cs-137 events (2.4 % of the photopeak) and 8.7 % without source — mostly tiny S1s (< 20 PE) and
near-gate / high-S2/S1 events. Spectra unchanged in shape; Cs-137 photopeak cS2 spread 43.0 % → 42.8 %. The cut does
not touch the S2 resolution.

**Comparison** (targets `targets/data_2026-10-09_single_s1cut.json`; step 8 refit `results/step8_s1cut/`): same best
optics; ε_S2 1.20 (was 1.17), ε_S1 0.74; χ² S2 vs r 1.7/7 (2.0), u,v 20.8/24 (27.4). No-source AFT vs size 0.71 → 0.53
(was 0.68 → 0.53). Central dip unchanged: centre/ring 0.71 / 0.74 / 0.82 / 0.83 / 1.02 for 3–5 / 5–10 / 10–20 / 20–50 /
> 50 kPE (was 0.69 / 0.75 / 0.79 / 0.87 / 1.02).

**Central events** (no source, S2 3–20 kPE): the cut removes 63 % at r < 2.5 mm (44 % have S1 < 20 PE) vs 20 % in the
ring; the central density excess drops from ×10.9 to ×5.1 — but the survivors still have AFT 0.53 vs 0.66 in the ring.
Their S1 is consistent, and their **S2s are narrow**: width50 400 ns (ring 586 ns; normal S2s are ≥ 520 ns even at the
gate), rise time 400 vs 517 ns, drift 8.9 vs 20.5 µs. So the central dip is only partly mismatched S1–S2 pairs: the rest
are S2s made over a shorter gas path or differently (anode / mesh geometry at the centre? gas events?) — open.

**Not a reconstruction artefact (checked 2026-10-09).** u, v = cgr fractions of ch1–4; `grid_lookup` keeps NaN as NaN
and clips out-of-range (u, v) onto the map edge, where `pos_rec_map_v0` gives r ≈ 29–31 mm; only |u|, |v| ≲ 0.12 maps to
r < 2.5 mm. Empty channels (e.g. ch3 + ch4 = 0 → v = +1) therefore end at the edge, and diagonal-only light
(ch1 = ch4, ch2 = ch3 = 0) would give u = v = 0 — but no central event has a channel below 3 % of the top light:
sorted channel shares 0.23 / 0.24 / 0.26 / 0.28 (S2 3–20 kPE, same as for large central S2s). Their top light is
genuinely balanced over the four anodes (a real central S2, or light from a spread-out source).
