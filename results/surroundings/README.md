# Surroundings: PTFE bucket and cryostat vessel (geometry v4, 2026-10-06)

Geometry v4 puts the TPC in the PTFE bucket (drawing `PTFE_bucket.pdf`: Ø112/132, 129 mm, weir 1.78 mm below the rim
sets the liquid level) inside the closed stainless-steel vessel (`Inner_cryostat_vessel.pdf`: Ø146.86/152.4, 305 mm),
gas xenon around the bucket. v3 had an absorbing world around the TPC.

One parameter point (level 4 mm, PTFE R 0.95, specular 0.1, steel R 0.35, Rayleigh 45 cm); v3 = that point of the
step-8 fit scans, v4 = `scans/check_v4_s2.yaml` / `check_v4_s1.yaml`; `python tools/surroundings_compare.py`.

| | S2 top fraction | S2 LCE top / bottom | S1 top fraction | S1 LCE top / bottom |
|---|---|---|---|---|
| v3 | 0.5629 ± 0.0006 | 0.0426 / 0.0331 | 0.1767 ± 0.0003 | 0.0135 / 0.0628 |
| v4 | 0.5617 ± 0.0006 | 0.0427 / 0.0334 | 0.1770 ± 0.0003 | 0.0135 / 0.0630 |

The S2 light that left the TPC region in v3 (22 %) ends in v4 on the vessel (13 %), the outside of the mesh rings
(+2.5 %), the PMT bodies (+1.7 %), the copper rings (1.8 %) and the bucket (1.9 %). Almost none comes back to the PMTs:
the surroundings do not explain the missing light, and all v3 results stay valid. Not known (defaults): bucket bottom
thickness (10 mm), vessel end thickness (2.77 mm), vessel bottom 10 mm below the bucket — irrelevant at this level.

![v4 vs v3](compare.png)
