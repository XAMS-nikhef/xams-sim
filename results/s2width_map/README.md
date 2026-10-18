# S2 width maps: the central dip is a population of narrow S2s (2026-10-09)

`python optical/s2width_map.py` (data `analysis_SR2026.2/outputs/s2_channels.npz`; quality cuts: S1 ≥ 20 PE in top and
bottom, S1 AFT consistent with the drift time; width50 corrected to the gate with k = 3600 ns²/µs).

| | width50 at gate, centre r < 2.5 | ring 7.5–12.5 | narrow (< 450 ns) centre / ring |
|---|---|---|---|
| no source 3–20 kPE | **360 ns** | 510 ns | **62 %** / 8 % |
| no source 20–50 kPE | 543 | 540 | 28 % / 2 % |
| no source > 50 kPE | 571 | 567 | 2 % / 0.5 % |
| Cs-137 photopeak | 577 | 593 | 14 % / 0.9 % |

(Raw, uncorrected width50 of the small central S2s: 400 vs 589 ns — not an artefact of the diffusion correction.)

**Small no-source S2s (3–20 kPE), split by width:**

| | narrow (< 450 ns) | normal width |
|---|---|---|
| centre r < 2.5 mm | AFT **0.499** (68 events), drift 6.5 µs | AFT **0.650** (41), drift 13.7 µs |
| ring 7.5–12.5 mm | AFT 0.665 (28) | AFT 0.665 (315) |

- Narrow S2s are concentrated in one or two 2.5 mm cells around (0, 0); their fraction falls with S2 size (62 → 28 →
  2 %), as the dip does.
- Normal-width S2s at the centre have the ring's AFT: **without the narrow S2s there is no central dip**.
- Wider S2s at r > 17 mm and in the lower region (y < 0) for large S2s (field fringe at the edge).

What the narrow S2s are is open. They have balanced top light (u ≈ v ≈ 0), lower AFT (0.50) and are narrower than any
normal S2 at the gate (EL path ~520 ns): light from a spread-out source arriving at once rather than one electron cloud
at one place — e.g. electrons released simultaneously over a large area (photo-emission from the gate / burst from
the surface after a large S2), which reconstructs at the centre. Test: time since the previous large S2 (event
times needed), S2 shape. A cut on the S2 width (gate-corrected width50 > 450 ns) removes them.
