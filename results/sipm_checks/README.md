# Two checks of the drift-field / SiPM hypothesis (2026-10-12)

`python optical/sipm_checks.py runtimes.json sc_hv.jsonl` (run start times from the run database and HV lines from the
slow-control archive, both read-only).

## 1. Apparent electron lifetime versus radius — strongly radius-dependent

ln(bottom S2) versus drift time, Cs-137 photopeak, clean cuts, no lifetime correction (τ in µs):

| | r 0–8 mm | 8–14 | 14–19 | 19–24 |
|---|---|---|---|---|
| 29-09, all φ | 302 ± 86 | 343 ± 84 | 137 ± 14 | 70 ± 6 |
| 29-09, φ 0–150° | 307 ± 119 | 264 ± 60 | 118 ± 12 | 74 ± 7 |
| 29-09, φ 150–360° | 289 ± 116 | 229 ± 69 | 149 ± 35 | 37 ± 4 |
| 28-09, all φ | 497 ± 414 | (poor) | 144 ± 29 | 46 ± 5 |

- Attachment to impurities gives the same τ everywhere. Here the centre has ~300 µs (more than Oct 2024, 238 µs) and the
  outer ring 40–75 µs: a **geometric charge loss towards the wall that grows with the drift length**. The
  analysis lifetime (elife_v2, 157–161 µs) is an average over radius: it over-corrects central events and
  under-corrects outer ones.
- Both azimuth halves show it (somewhat stronger at φ 150–360° in the outermost ring): the loss runs all around the
  wall, not only at two points.
- This also inflates the depth-dependent spread: mixing radii with different loss in one depth bin.

## 2. Spread of deep events versus time since HV-on — inconclusive

Per run, bottom cS2 spread (fixed τ = 160 µs, which inflates the deep values) for z < −26 mm and z > −15 mm. First runs
after a fresh cathode ramp: 28-09 deep 0.75–0.78 at 1.2–1.5 h → 0.61–0.68 at 1.6–2.0 h; 29-09 0.62–0.73 at 0.3–0.7 h →
0.55–0.62 at 2.2–2.5 h. But on 28-09 the top spread falls together (0.44 → 0.33; deep / top flat at ~1.8), the source
position changed between the run groups, and after the anode-only restart on 29-09 (cathode stayed on) there is no
fresh-start excess. A slow charge-up cannot be excluded, but the data do not show a clear one.
