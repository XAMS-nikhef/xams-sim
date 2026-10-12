# Where does the Cs-137 photopeak cS2 spread come from? Unbiased map (2026-10-12)

`python tools/spread_map.py`: Cs-137 photopeak (Δ750 V, all source positions), clean cuts, r < 22 mm; spread =
1.4826 · MAD / median per cell (relative to the cell's own median, so slow yield gradients do not count); total and
bottom-PMT cS2 (lifetime-corrected, LED gains). Global: total 0.427, bottom 0.400.

**No compact spots — a strong depth dependence**, the same for every source position (bottom cS2):

| z (mm) | −3…−10 | −10…−18 | −18…−26 | −26…−34 | −34…−42 | −42…−52 |
|---|---|---|---|---|---|---|
| standard | 0.27 | 0.31 | 0.44 | 0.54 | 0.48 | 0.47 |
| 2 cm lower | 0.22 | 0.37 | 0.39 | 0.40 | 0.36 | 0.44 |
| rotated 170° | 0.26 | 0.35 | 0.39 | 0.44 | 0.43 | 0.48 |
| rotated 90° | 0.26 | 0.31 | 0.38 | 0.42 | 0.39 | 0.49 |
| r < 8 mm (all) | 0.20 | 0.21 | 0.27 | 0.33 | 0.29 | 0.46 |

- Near the gate the spread is 20–27 %, approaching Oct 2024 (17 %); it rises to 40–50 % below z ≈ −20 mm, with the
  largest step between −10…−18 and −18…−26 mm, and once more in the last bin before the cathode.
- **Azimuth:** worst at φ 0–150° (deep: 0.50–0.54), better at φ 150–270° (deep: 0.31–0.42; near the gate 0.16–0.19).
  Event coverage differs per sector (the source side has most events; sectors 210–360° are populated mainly near the
  cathode), so the azimuth pattern is less certain than the depth pattern.
- Interpretation: the fluctuation grows with the drift path / depth of the interaction → charge transport in the
  lower drift region (consistent with the drift-field dependence and the weak field near the cathode), not the S2
  production at the surface and not a sensor. The SiPMs sit at z ≈ −25 mm (sim azimuths 0° / 90° → data frame 180° /
  90°), at the height where the spread rises, but the azimuth pattern does not single them out.
- Check of the selection: lifetime correction errors (τ ± 20 %) give only ±5 % at the deepest events.
