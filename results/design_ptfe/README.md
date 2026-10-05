# Design study: extra PTFE cylinders (2026-10-05, geometry v3)

Simulation (geometry v3: drawings incl. the 456-hole mesh pattern, level 4 mm, middle optics: PTFE R 0.945 in liquid / 0.75 in gas,
steel R 0.35, copper R 0.3, QE 0.33). Extra cylinders with the radii of the drift-region PTFE (r 31–36 mm,
inside the ring bores): gate–anode z 0.075–7.925 mm (foil to foil, split at the liquid surface, gas part with
the gas reflectivity), anode–top screen 8.075–17.925 mm, cathode–bottom screen −59.525 to −51.875 mm. Scans
`scans/design_ptfe_s2.yaml`, `_s1.yaml` (8·10⁶ photons each). Light collection = detected / emitted, QE
included.

## S2 (gas gap)

| extra PTFE | top | bottom | total | gain vs now | top fraction | rings (steel + copper) | leaves | PTFE absorbed |
|---|---|---|---|---|---|---|---|---|
| none (as built) | 4.26 % | 3.30 % | 7.56 % | +0 % | 0.564 | 10.3 % | 21.9 % | 2.8 % |
| gate–anode | 4.95 % | 4.00 % | 8.96 % | +19 % | 0.553 | 6.5 % | 13.4 % | 3.6 % |
| anode–top screen | 5.21 % | 3.54 % | 8.75 % | +16 % | 0.596 | 5.9 % | 16.8 % | 3.0 % |
| cathode–bottom screen | 4.27 % | 3.64 % | 7.91 % | +5 % | 0.540 | 9.6 % | 21.3 % | 3.2 % |
| gate–anode + anode–top screen | 6.01 % | 4.32 % | 10.33 % | +37 % | 0.582 | 1.6 % | 7.5 % | 3.8 % |
| gate–anode + anode–top screen + cathode–bottom screen | 6.04 % | 4.76 % | 10.79 % | +43 % | 0.559 | 0.5 % | 6.7 % | 4.4 % |

## S1 (drift region)

| extra PTFE | top | bottom | total | gain vs now | top fraction | rings (steel + copper) | leaves | PTFE absorbed |
|---|---|---|---|---|---|---|---|---|
| none (as built) | 1.34 % | 6.23 % | 7.57 % | +0 % | 0.176 | 8.9 % | 11.1 % | 9.9 % |
| gate–anode | 1.53 % | 6.70 % | 8.24 % | +9 % | 0.186 | 5.3 % | 8.8 % | 11.5 % |
| anode–top screen | 1.49 % | 6.24 % | 7.73 % | +2 % | 0.193 | 8.1 % | 10.7 % | 9.9 % |
| cathode–bottom screen | 1.39 % | 7.20 % | 8.59 % | +13 % | 0.161 | 5.6 % | 9.0 % | 11.1 % |
| gate–anode + anode–top screen | 1.71 % | 6.75 % | 8.46 % | +12 % | 0.202 | 4.4 % | 8.2 % | 11.5 % |
| gate–anode + anode–top screen + cathode–bottom screen | 1.80 % | 7.88 % | 9.67 % | +28 % | 0.186 | 0.6 % | 5.8 % | 12.9 % |

## Reading

- S2: light collection +19 % (gate–anode) / +16 % (anode–top screen) alone, **+37 % with both**, +43 % with all three; the light leaving sideways or ending on the rings drops from 32 % to 7 %. The top fraction hardly changes (0.54–0.60).
- S1: +9 / +2 / +13 % alone, +28 % with all three; cathode–bottom screen helps S1 most (bottom PMT).
- In absolute terms: S2 detected light goes from 7.6 % to 10.8 % of the emitted photons (factor 1.43) — most rescued photons still end on meshes, PMT frames or in the photocathode (QE).
- Caveats: everything outside |x|, |y| < 60 mm is black (the real sideways loss may be smaller, and the gain
  with it); PTFE reflectivity in gas (0.75) is free (0.60–0.90); the three gate–anode pillars are not modelled.
  Not looked at: HV (PTFE across 5 kV gate–anode: surface paths, charge-up in the extraction region), mechanics.

