# Anode mesh rotated by 120° relative to the gate (2026-10-05; geometry v4 2026-10-07)

Question: what changes if the anode mesh is rotated by 120° relative to the gate? A square mesh (and the 456-hole
pattern) repeats every 90°, so 120° = **30° relative rotation**. Scans `anode_rotation_s2` / `_s1` (anode at 29.4° =
as now, aligned with the gate, vs 149.4°; level 4 mm, middle optics; 4·10⁷ photons each). `optical/anode_rotation.py`.

| | anode as now | anode +120° |
|---|---|---|
| S2 top fraction | 0.5595 ± 0.0003 | 0.5599 ± 0.0003 |
| S2 light collection top / bottom | 4.53 / 3.57 % | 4.54 / 3.57 % |
| S2 light absorbed on the anode foil | 13.03 % | 13.03 % |
| S1 top fraction | 0.1791 ± 0.0002 | 0.1792 ± 0.0002 |
| S1 light collection top / bottom | 1.45 / 6.65 % | 1.45 / 6.65 % |
| fine structure of the top light vs S2 position (1 mm cells, RMS beyond statistics) | 3.0 % | 3.0 % |

(Geometry v4. v3 gave the same picture: S2 top fraction 0.5631 / 0.5632, fine structure 3.3 / 2.8 %.)

**Optically nothing changes:** top fraction, light collection, the radial profile, the sector pattern and the S1
profile are identical within the statistical errors. The light hitting the anode (S2 is produced just below it) sees
the same open fraction whatever the orientation, and the gate–anode overlap pattern (moiré) only shows as a ~3 %
fine structure on the mm scale in both cases.

Not in this simulation: the electric field. A rotation changes the gate–anode field map locally (where the bars cross),
which could matter for the electron extraction and the electroluminescence — that needs a field calculation, not an
optical one.
