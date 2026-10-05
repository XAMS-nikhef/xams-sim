# Design study: extra PTFE cylinders (2026-10-05)

Simulation (model v1, level 4 mm, middle optics: PTFE R 0.945 in liquid / 0.75 in gas, steel R 0.35, QE 0.33).
Extra cylinders: same radii as the drift-region PTFE (r 30.97–35.97 mm), between the mesh rings: gate–anode
z 0.9–7.1 mm (split at the liquid surface, gas part with the gas reflectivity), anode–top screen 8.9–17.1 mm,
cathode–bottom screen −58.7 to −52.7 mm. Scans `scans/design_ptfe_s2.yaml`, `_s1.yaml` (8·10⁶ photons each).
Light collection = detected / emitted, QE included.

## S2 (gas gap)

| extra PTFE | top | bottom | total | gain vs now | top fraction | rings | leaves | PTFE absorbed |
|---|---|---|---|---|---|---|---|---|
| none (as built) | 4.38 % | 3.35 % | 7.73 % | +0 % | 0.567 | 23.1 % | 18.3 % | 2.8 % |
| gate–anode | 4.93 % | 3.90 % | 8.83 % | +14 % | 0.558 | 16.2 % | 12.0 % | 3.5 % |
| anode–top screen | 5.13 % | 3.58 % | 8.71 % | +13 % | 0.589 | 16.8 % | 14.1 % | 3.0 % |
| cathode–bottom screen | 4.39 % | 3.64 % | 8.02 % | +4 % | 0.547 | 21.0 % | 18.0 % | 3.2 % |
| gate–anode + anode–top screen | 5.79 % | 4.15 % | 9.94 % | +29 % | 0.582 | 9.2 % | 7.2 % | 3.6 % |
| gate–anode + anode–top screen + cathode–bottom screen | 5.80 % | 4.49 % | 10.29 % | +33 % | 0.563 | 6.6 % | 6.7 % | 4.1 % |

## S1 (drift region)

| extra PTFE | top | bottom | total | gain vs now | top fraction | rings | leaves | PTFE absorbed |
|---|---|---|---|---|---|---|---|---|
| none (as built) | 1.35 % | 6.25 % | 7.60 % | +0 % | 0.178 | 20.9 % | 8.8 % | 9.7 % |
| gate–anode | 1.48 % | 6.63 % | 8.11 % | +7 % | 0.182 | 14.9 % | 7.5 % | 11.0 % |
| anode–top screen | 1.48 % | 6.29 % | 7.77 % | +2 % | 0.191 | 19.6 % | 8.4 % | 9.7 % |
| cathode–bottom screen | 1.39 % | 7.01 % | 8.40 % | +11 % | 0.165 | 15.2 % | 7.7 % | 10.7 % |
| gate–anode + anode–top screen | 1.64 % | 6.69 % | 8.33 % | +10 % | 0.197 | 13.4 % | 7.0 % | 11.0 % |
| gate–anode + anode–top screen + cathode–bottom screen | 1.70 % | 7.51 % | 9.21 % | +21 % | 0.184 | 6.9 % | 5.8 % | 12.1 % |

## Reading

- S2: light collection +14 % (gate–anode) / +13 % (anode–top screen) alone, **+29 % with both**, +33 % with all three;
  the light that now dies in the rings and leaves the TPC sideways (41 %) drops to 13 %. The top fraction hardly
  changes (0.56–0.59). Cathode–bottom screen matters little for S2 (+4 %).
- S1: +7 % / +2 % / +11 % alone, +21 % with all three; cathode–bottom screen helps S1 most (bottom PMT).
- Caveats: model v1 treats everything outside |x|, |y| < 60 mm as black, so the real sideways loss may be smaller and
  the gain somewhat smaller; PTFE reflectivity in gas (0.75) is a free parameter (range 0.60–0.90); the three pillars
  between gate and anode are not modelled. Not looked at: HV (PTFE across 5 kV gate–anode: surface paths, charge-up of
  PTFE in the extraction region and its effect on the field near the edge), mechanics.
