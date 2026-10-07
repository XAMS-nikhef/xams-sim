# Threshold / charge-sharing toy: can the readout make the central S2 dip? (2026-10-07)

**No.** The readout (DAQ self-trigger + amstrax hit finding) loses < 0.5 % of the top light and < 3 % of the bottom
light for S2 ≥ 3 kPE, at the centre and in the ring alike. Centre / ring of the S2 area fraction top stays 1.01 for
every S2 size (data 0.69 → 0.87 → 1.02). It also gives no S2-size dependence of the area fraction top (toy 0.585–0.588
for 3 kPE … 300 kPE, data 0.68 → 0.52).

`tools/threshold_toy.py` (60 000 events, 26 s) → `threshold_toy.png`, `summary.json`.

## What the toy does

- Light per channel from the simulated light response at the (true) event position: geometry v4, fit_s2 points
  PTFE R 0.95 / specular 0.1 / steel R 0.2 (Rayleigh 30/45/60 pooled), 3 mm smoothing.
- S2 time profile: electrons spread by diffusion (σ from the measured width50² slope, 3600 ns²/µs, drift 0.5–39 µs),
  each emitting uniformly over 480 ns (width50 ≈ 520 ns at the gate); 25 PE per electron.
- Per 4 ns sample and channel: Poisson photons, single-PE charge with the LED gains and resolutions (top 45–56,
  bottom 12.6 ADC·samples; resolution ~0.4), measured single-photon pulse shapes (top anodes 1–3: LED run 7682 —
  one-sample spike; anode 4: slow pulse; bottom: run 7717), 3 ADC noise.
- Readout as in the data: V1725 self-trigger per channel (top 30 ADC on 28-09 / 20 ADC on 29-09, half each; bottom
  60 ADC; 32 samples pre-trigger, 24 samples under threshold); amstrax hits = samples ≥ 15 ADC (`strax.find_hits`
  default); **the peak area per channel is the sum of the hit samples only** (`strax.sum_waveform`, no integration
  extension); peaks = hits of all channels with a 300 ns gap, S2 = the largest; PE with the LED gains.
- Check: a lone top photon keeps 52–54 % of its charge (anodes 1–3), as measured (55–60 %, delayed-signal note §5).

## Why it fails

At 3 kPE a top anode at the centre still gets ~3 PE per 4 ns sample (~130 ADC), far above 15 ADC: only the outermost
flank samples are lost. And charge sharing differs little between centre and ring — at r = 10 mm the top light is
also spread (channel shares 0.22 / 0.09 / 0.21 / 0.09 vs 0.16 each at the centre). Even for a 300 PE S2 the top keeps
0.72 (centre) vs 0.74 (ring).

| S2 (PE) | top kept, centre / ring | bottom kept |
|---|---|---|
| 100 | 0.52 / 0.59 | 0 |
| 300 | 0.72 / 0.74 | 0 |
| 1000 | 0.94 / 0.94 | 0.22–0.24 |
| 3000 | 0.99 / 0.99 | 0.96–0.97 |

Side result: the **bottom PMT** (−800 V: ~3 ADC peak per PE, 60 ADC trigger threshold) records nothing below ~1 kPE
and only part up to ~2–3 kPE. It matters for small S2s / single electrons, not for the 3–20 kPE S2s of the dip.

## What remains for the central dip

Not optics (step 7/8), not a PMT dead cross (step 8), not the readout threshold / charge sharing (this toy). The dip
is ~5 mm wide while the top PMT sees the S2 light over a much wider spot, so any light-collection effect is too
smooth. Candidates: position reconstruction near u = v = 0 (a population with low area fraction top mapped to the
centre), or something in the S2 production at the centre (the five meshes have their pattern centre on the axis);
the Cs-137 photopeak shows ~7 % less S2 light at r < 2.5 mm but no area-fraction dip for large S2s.
Not modelled here: the load / gain drop of the top PMT, afterpulses, delayed light, peak splitting.
