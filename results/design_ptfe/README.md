# Design study: extra PTFE cylinders (2026-10-05; geometry v4 2026-10-07)

Simulation (geometry v4: drawings incl. the 456-hole mesh pattern, PMT holders, PTFE bucket and cryostat vessel; level 4 mm, middle optics: PTFE R 0.945 in liquid / 0.75 in gas,
steel R 0.35, copper R 0.3, QE 0.33). Extra cylinders with the radii of the drift-region PTFE (r 31–36 mm,
inside the ring bores): gate–anode z 0.075–7.925 mm (foil to foil, split at the liquid surface, gas part with
the gas reflectivity), anode–top screen 8.075–17.925 mm, cathode–bottom screen −59.525 to −51.875 mm. Scans
`scans/design_ptfe_s2.yaml`, `_s1.yaml` (8·10⁶ photons each). Light collection = detected / emitted, QE
included.

## S2 (gas gap)

| extra PTFE | top | bottom | total | gain vs now | top fraction | rings (steel + copper) | bucket + vessel | PTFE absorbed |
|---|---|---|---|---|---|---|---|---|
| none (as built) | 4.53 % | 3.57 % | 8.10 % | +0 % | 0.559 | 14.9 % | 11.9 % | 3.0 % |
| gate–anode | 5.27 % | 4.33 % | 9.60 % | +18 % | 0.549 | 8.5 % | 6.1 % | 3.9 % |
| anode–top screen | 5.46 % | 3.88 % | 9.35 % | +15 % | 0.585 | 9.9 % | 6.8 % | 3.2 % |
| cathode–bottom screen | 4.57 % | 3.94 % | 8.52 % | +5 % | 0.537 | 13.5 % | 11.8 % | 3.6 % |
| gate–anode + anode–top screen | 6.32 % | 4.71 % | 11.04 % | +36 % | 0.573 | 2.7 % | 0.2 % | 4.1 % |
| gate–anode + anode–top screen + cathode–bottom screen | 6.37 % | 5.21 % | 11.58 % | +43 % | 0.550 | 0.6 % | 0.0 % | 4.9 % |

## S1 (drift region)

| extra PTFE | top | bottom | total | gain vs now | top fraction | rings (steel + copper) | bucket + vessel | PTFE absorbed |
|---|---|---|---|---|---|---|---|---|
| none (as built) | 1.45 % | 6.65 % | 8.10 % | +0 % | 0.179 | 13.6 % | 1.7 % | 10.2 % |
| gate–anode | 1.67 % | 7.17 % | 8.83 % | +9 % | 0.189 | 8.0 % | 1.2 % | 11.8 % |
| anode–top screen | 1.61 % | 6.70 % | 8.31 % | +3 % | 0.194 | 12.6 % | 1.1 % | 10.2 % |
| cathode–bottom screen | 1.54 % | 7.69 % | 9.23 % | +14 % | 0.167 | 8.2 % | 1.2 % | 11.7 % |
| gate–anode + anode–top screen | 1.85 % | 7.23 % | 9.08 % | +12 % | 0.204 | 6.9 % | 0.5 % | 11.9 % |
| gate–anode + anode–top screen + cathode–bottom screen | 1.96 % | 8.42 % | 10.38 % | +28 % | 0.189 | 0.7 % | 0.0 % | 13.6 % |

## Reading

- S2: light collection +18 % (gate–anode) / +15 % (anode–top screen) alone, **+36 % with both**, +43 % with all three; the light ending on the rings, the bucket or the vessel drops from 27 % to 1 %. The top fraction hardly changes (0.54–0.58).
- S1: +9 / +3 / +14 % alone, +28 % with all three; cathode–bottom screen helps S1 most (bottom PMT).
- In absolute terms: S2 detected light goes from 8.1 % to 11.6 % of the emitted photons (factor 1.43) — most rescued photons still end on meshes, PMT frames or in the photocathode (QE).
- Caveats: PTFE reflectivity in gas (0.75) is free (0.60–0.90); the three gate–anode pillars are not modelled;
  bucket bottom, vessel ends and the gap below the bucket are defaults.
  Not looked at: HV (PTFE across 5 kV gate–anode: surface paths, charge-up in the extraction region), mechanics.

