# Design study: extra PTFE cylinders (2026-10-05, geometry v2)

Simulation (geometry v2 from the drawings, level 4 mm, middle optics: PTFE R 0.945 in liquid / 0.75 in gas,
steel R 0.35, copper R 0.3, QE 0.33). Extra cylinders with the radii of the drift-region PTFE (r 31–36 mm,
inside the ring bores): gate–anode z 0.075–7.925 mm (foil to foil, split at the liquid surface, gas part with
the gas reflectivity), anode–top screen 8.075–17.925 mm, cathode–bottom screen −59.525 to −51.875 mm. Scans
`scans/design_ptfe_s2.yaml`, `_s1.yaml` (8·10⁶ photons each). Light collection = detected / emitted, QE
included.

## S2 (gas gap)

| extra PTFE | top | bottom | total | gain vs now | top fraction | rings (steel + copper) | leaves | PTFE absorbed |
|---|---|---|---|---|---|---|---|---|
| none (as built) | 4.34 % | 3.31 % | 7.65 % | +0 % | 0.568 | 13.2 % | 25.7 % | 3.1 % |
| gate–anode | 4.99 % | 3.98 % | 8.98 % | +17 % | 0.556 | 7.7 % | 16.8 % | 3.6 % |
| anode–top screen | 5.24 % | 3.61 % | 8.85 % | +16 % | 0.592 | 7.4 % | 19.0 % | 3.3 % |
| cathode–bottom screen | 4.36 % | 3.67 % | 8.03 % | +5 % | 0.542 | 12.2 % | 23.8 % | 3.6 % |
| gate–anode + anode–top screen | 6.04 % | 4.33 % | 10.38 % | +36 % | 0.582 | 1.9 % | 9.4 % | 3.9 % |
| gate–anode + anode–top screen + cathode–bottom screen | 6.09 % | 4.79 % | 10.88 % | +42 % | 0.560 | 0.6 % | 7.1 % | 4.5 % |

## S1 (drift region)

| extra PTFE | top | bottom | total | gain vs now | top fraction | rings (steel + copper) | leaves | PTFE absorbed |
|---|---|---|---|---|---|---|---|---|
| none (as built) | 1.39 % | 6.28 % | 7.67 % | +0 % | 0.181 | 11.5 % | 14.8 % | 10.1 % |
| gate–anode | 1.53 % | 6.73 % | 8.26 % | +8 % | 0.185 | 6.7 % | 12.2 % | 11.5 % |
| anode–top screen | 1.53 % | 6.32 % | 7.85 % | +2 % | 0.195 | 10.3 % | 13.8 % | 10.1 % |
| cathode–bottom screen | 1.45 % | 7.31 % | 8.76 % | +14 % | 0.166 | 7.4 % | 10.4 % | 11.6 % |
| gate–anode + anode–top screen | 1.71 % | 6.80 % | 8.51 % | +11 % | 0.201 | 5.6 % | 11.1 % | 11.5 % |
| gate–anode + anode–top screen + cathode–bottom screen | 1.82 % | 7.94 % | 9.76 % | +27 % | 0.186 | 0.8 % | 6.1 % | 13.3 % |

## Reading

- S2: light collection +17 % (gate–anode) / +16 % (anode–top screen) alone, **+36 % with both**, +42 % with all three; the light leaving sideways or ending on the rings drops from 39 % to 8 %. The top fraction hardly changes (0.54–0.59).
- S1: +8 / +2 / +14 % alone, +27 % with all three; cathode–bottom screen helps S1 most (bottom PMT).
- In absolute terms: S2 detected light goes from 7.6 % to 10.9 % of the emitted photons (factor 1.42) — most rescued photons still end on meshes, PMT frames or in the photocathode (QE).
- Caveats: everything outside |x|, |y| < 60 mm is black (the real sideways loss may be smaller, and the gain
  with it); PTFE reflectivity in gas (0.75) is free (0.60–0.90); the three gate–anode pillars are not modelled.
  Not looked at: HV (PTFE across 5 kV gate–anode: surface paths, charge-up in the extraction region), mechanics.

