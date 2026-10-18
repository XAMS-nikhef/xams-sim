# S1 area fraction top versus drift time (2026-10-09)

`python optical/s1aft_depth.py` (data: `analysis_SR2026.2/studies/s2_channels.py`, now with the S1 AFT, LED gains).
Calibration = median S1 AFT versus drift time of normal events (S2 > 20 kPE, r < 18 mm, outside the y < 0 region,
S1 > 100 PE); each event's S1 AFT → drift time t_S1; t_S1 − t_drift ≈ 0 when the S1 comes from where the drift time
says. Groups: y < 0 region (y < −3, r 10–18 mm, S2 > 50 kPE) vs mirror (y > 3); central small-S2 population (no
source, S2 3–20 kPE, r < 2.5 mm) vs ring (7.5–12.5 mm). `summary.json`, `s1aft_depth.png`.

## Central small-S2 population: S1 does not belong to the drift time

| no source, S2 3–20 kPE | t_S1 − t_drift (median) | off by > 10 µs | S1 | S2/S1 | S1 AFT |
|---|---|---|---|---|---|
| centre r < 2.5 mm | **+15 µs** (drift < 20 µs: +18) | **70 %** (81 %) | 583 PE | **13** | 0.099 |
| ring 7.5–12.5 mm | +3.5 µs | 32 % | 298 PE | 34 | 0.099 |

The central events have a large, deep-looking (bottom-heavy) S1 and a small S2 with a short drift time: the S1 and
S2 do not fit together. Likely accidental pairs — an S1-only event (e.g. a gamma below the cathode, no charge
collected) with an unrelated small, diffuse S2 (delayed / single-electron trains spread over the TPC give u ≈ v ≈ 0,
hence the reconstructed centre). **Correction (same day, `results/s1cut_spectrum/`):** a 3σ S1-AFT consistency cut
removes 63 % of the central events but not the dip — the survivors have consistent S1s and unusually narrow S2s, so
mismatched pairs are only part of the central population.

## y < 0 region: a mixture of two populations

S2/S1 has two peaks in every region: bulk events (S2/S1 ≈ 100–200) and **near-gate events** (S2/S1 ≈ 600–1000, drift
≈ 2 µs, S1 AFT 0.24–0.27 = consistent with ~2 mm below the gate, so real events, narrower S2s). Split at S2/S1 = 400
(S2 > 50 kPE):

| | near-gate fraction | S2 AFT near-gate / bulk | drift near-gate / bulk |
|---|---|---|---|
| no source, y < 0 region | **0.52** | 0.413 / 0.465 | 2.2 / 23.8 µs |
| no source, mirror y > 0 | 0.22 | 0.495 / 0.544 | 2.0 / 16.3 µs |
| Cs-137, y < 0 region | **0.41** | 0.207 / 0.293 | 2.1 / 35.2 µs |
| Cs-137, mirror y > 0 | 0.17 | 0.259 / 0.300 | 2.0 / 17.2 µs |

- Near-gate events have a lower S2 AFT everywhere (−0.04 to −0.05 vs bulk).
- They are a larger fraction at y < 0 mainly because the bulk events (external gammas) are concentrated at y > 0:
  near-gate events y < 0 / y > 0 = 0.6, all events 0.35 (no source).
- Cs-137 bulk events: region 0.293 vs mirror 0.300 — **normal events at y < 0 agree with the model**.
- Left over: near-gate events in the region have a still lower AFT (0.41 vs 0.50; Cs 0.21 vs 0.26), and no-source
  bulk events in the region 0.465 vs 0.544.

So most of the y < 0 "deficit" is a population mixture (near-gate events with lower S2 AFT, weighted up where bulk
events are rare), not a geometry or field effect for normal events. Open: why near-gate S2s have a lower AFT (S1
light ~2 µs before the S2 on the top PMT? extraction near the gate wires?), and the residual for near-gate events at
y < 0.
