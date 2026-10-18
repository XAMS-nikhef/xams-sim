# Best optics against the data per S2 size class (2026-10-09)

`python optical/size_classes.py`: step-8 best optics (PTFE R 0.95, specular 0.1, steel R 0.2, Rayleigh 45 cm), only the
scale ε fitted per sample; χ² for r ≥ 5 mm (7 dof), floor 0.01. See `summary.json` and `size_classes.png`.

| sample | ε | χ² / 7 | centre ÷ model |
|---|---|---|---|
| no source 3–5 kPE | 1.78 | 13.1 | 0.73 |
| no source 5–10 kPE | 1.26 | 5.3 | 0.76 |
| no source 10–20 kPE | 1.07 | 2.1 | 0.80 |
| no source 20–50 kPE | 0.80 | 19.0 | 0.86 |
| no source > 50 kPE | 0.78 | 26.7 | 1.03 |
| no source > 50 kPE, y > 0 | 0.80 | 10.4 | 1.02 |
| no source > 50 kPE, y < 0 | 0.65 | 146 | 1.07 |
| Cs-137 photopeak | 0.31 | 3.3 | 0.97 |

Large S2s agree with the model in shape (and at the centre) where the y < 0 region does not interfere; ε is stable
at ~0.8 above 20 kPE without source and 0.31 with Cs-137 (top-PMT load). Below 20 kPE ε rises (AFT falls with size)
and the central population adds the dip. The y < 0 deficit: `results/channel_test/`.
