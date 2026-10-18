# S3 check — input, clustering, NEST yields (Cs-137)

`validation/s3_microphysics_check.py` (2026-10-18) on the S2 run `s2_cs137_raised`: 2·10⁶ Cs-137 decays, source outside
the outer vessel at r = 130 mm, z = −26 mm; state cmb50 (drift field ~100 V/cm). Chain: `xamssim chain … --target quanta`
(4 min on the laptop): our input plugin → fuse lineage clustering → four XAMS volumes → field from the COMSOL map →
NEST. Field map: COMSOL solve of 2026-10-12, (r, z) half plane, geometry v4 (sim frame).

**Superseded setup (same day, evening):** the chain now uses the 3D field map and geometry v5 (data frame). Sections 1–3
(where the energy goes, clusters, sensitivity) do not depend on the field; sections 4–5 used the field and are to be
redone with the 3D map once the cmb50 state is solved.

## 1. Where the energy goes (raw Geant4 deposits)

| region (r < 31 mm unless noted) | energy fraction | events |
|---|---|---|
| drift region (cathode → gate) | 0.134 | 13790 |
| liquid above gate (gate → surface, 4 mm) | 0.011 | 1881 |
| below cathode | 0.030 | 3920 |
| liquid outside the field cage (r ≥ 31 mm) | 0.749 | 87724 |
| gas (all r) | 0.017 | 4838 |

Three quarters of the energy is deposited in the liquid between the PTFE cylinder and the bucket, which is not
simulated further (behind the PTFE, no field). Of the deposits in the gas, 223 events lie inside r < 31 mm.

## 2. Clusters and event classes (lineage, defaults)

Volumes with electrons: drift region, liquid above gate, gas; below the cathode: light only (gamma-X).
Photopeak = summed cluster energy in the four volumes within 5 keV of 661.7 keV.

| | events | SS | MS | γ-X | SS, clusters < 1 mm in z merged | SS, < 3 mm merged | with a cluster above gate / in gas |
|---|---|---|---|---|---|---|---|
| energy in the drift region | 13646 | 0.455 | 0.489 | 0.056 | 0.606 | 0.715 | 0.031 |
| photopeak | 2774 | 0.188 | 0.725 | 0.087 | 0.366 | 0.525 | 0.040 |

1.82 clusters with electrons per drift-region event. All clusters get NEST's beta model (`nestid` 8): fuse classifies
Compton and photo-absorption electrons as betas.

## 3. Sensitivity of the photopeak SS fraction (first 10⁶ decays)

| clustering | setting | clusters / event | SS | SS (3 mm merged) | γ-X |
|---|---|---|---|---|---|
| lineage | time threshold 1, 10, 100, 1000 ns | 1.82 | 0.186 | 0.519 | 0.093 |
| lineage | gamma distance 0 / 0.05 / 0.2 / 0.5 cm | 1.82 / 1.69 / 1.62 / 1.49 | 0.186 / 0.241 / 0.261 / 0.332 | 0.519 / 0.519 / 0.519 / 0.542 | 0.093–0.086 |
| DBSCAN | cluster size 0.005 / 0.05 / 0.1 / 0.3 cm | 11.4 / 2.81 / 2.10 / 1.78 | 0.000 / 0.001 / 0.055 / 0.205 | 0.524 / 0.522 / 0.521 / 0.519 | 0.093 |

- The time window does not matter: the scatters of a 662 keV gamma in XAMS are < 1 ns apart.
- The raw SS fraction depends on the clustering (0–0.33); the SS fraction after merging in z at the S2 resolution
  does not (0.52 ± 0.01 for every setting). The physics answer is the merged one; the merge distance belongs to the
  detector response (S5 / S7), not to the clustering.
- DBSCAN at its XENON default (50 µm) splits each electron track into ~11 pieces; lineage keeps a track together.
  Lineage with the defaults stays the choice.

## 4. fuse NEST yields vs standalone nestpy (662 keV, liquid, 3000 draws each)

| model | field (V/cm) | photons fuse | nestpy | electrons fuse | nestpy | corr(ph, e) |
|---|---|---|---|---|---|---|
| beta | 100 | 22179 ± 28 | 22145 | 26783 ± 28 | 26818 | −0.990 |
| beta | 145 | 20181 ± 25 | 20198 | 28786 ± 25 | 28766 | −0.986 |
| beta | 500 | 14424 ± 19 | 14414 | 34543 ± 19 | 34549 | −0.977 |
| gamma | 100 | 27827 ± 35 | 27840 | 21136 ± 35 | 21123 | −0.993 |
| gamma | 145 | 25485 ± 34 | 25473 | 23485 ± 34 | 23491 | −0.993 |
| gamma | 500 | 18939 ± 32 | 18888 | 30023 ± 33 | 30075 | −0.992 |

Agreement within 1.6 σ everywhere: fuse calls NEST as standalone nestpy does. The beta and gamma models differ by
~25 % in charge at 662 keV — which one describes XAMS is a question for the data (charge yield of the Cs-137 peak).

## 5. Anticorrelation at 662 keV (photopeak, no γ-X, only drift-region clusters; 101 V/cm median)

- 2422 events (521 with one cluster): corr(photons, electrons) = −0.997; σ/μ photons 0.111, electrons 0.121, sum 0.0045.
- One cluster: 22061 photons / 26888 electrons; several clusters: 26487 / 22475. Lower-energy clusters recombine more
  (NEST non-linearity), so multi-site photopeak events have more light and less charge than single-site ones.

## Notes on the model

- fuse 1.6.3 needs `np.in1d` (removed in numpy 2.4); `xamssim.plugins` adds it back.
- Field: |E| on the (r, z) half plane at azimuth 270° (no SiPM), SiPMs at 0 V in the 3D model; below the bottom screen
  and above 12 mm the edge value of the plane (below-cathode reverse field ~2 kV/cm also used below the screen).
