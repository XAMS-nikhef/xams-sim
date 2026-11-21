# Physics of the chain

What the simulation does physically at every step, from the energy deposit to the waveform: the model, its equations,
the parameter values with their units, where each number comes from (measurement, fit, literature, PyBoltz /
Magboltz, NEST, COMSOL), the range in which it is valid, and what is open. How to run each step is in
[Simulation chain](chain.md), [Electric field](efield.md) and [Optics](optics.md); the sensitive detector parameters
(gas gap, liquid level, extraction) in [Critical parameters](critical_parameters.md).

Numbers are for detector `xams_sr2026_3` (SR-2026.3, geometry v8: gate–anode 9.30 mm between the mesh mid-planes, 9.15 mm between the foil faces
(drawing), anode foil up, liquid 4.0 mm above the gate, gas gap 5.30 mm, 1.49 bar absolute) and, as the example, state `ma` (run 7984: anode +2101 V, gate −646 V,
cathode −1146 V, 97 V/cm). The same content, with figures, is in the PDF note
`simulations/SR2026.3/XAMS_SR2026.3_simulation_physics_v2.pdf` (studies repository).

!!! note "Status 2026-11-21"
    Geometry v8 (#53: anode foil 9.30 mm, PMT collection efficiency CE bottom 0.75 / top 0.70) and the extraction
    shift refitted for it (#54: 0.13 kV/cm). All maps were rebuilt from scratch (drift map 0.25 mm grid, EL map v3 with
    gas diffusion) and all earlier SR-2026.3 MC runs deleted. Reference run: 990068 (state `ma`, Cs-137 t16, 1e7),
    compared with data 7984 and approved 2026-11-21. Numbers marked *(v7)* are from the previous geometry (9.65 mm)
    and were not recomputed.

| step | model | main inputs | section |
|---|---|---|---|
| energy deposits | Geant4 11.3 particle mode, EM option 4, radioactive decay | geometry, source, position | [Deposits](#energy-deposits-and-clusters) |
| clusters | fuse `LineageClustering` + `MergeLineage` | particle lineage, 10 ns | [Deposits](#energy-deposits-and-clusters) |
| quanta | NEST β-ER yields and fluctuations (nestpy 2.0.6) | local \|E\|, density | [NEST](#quanta-nest) |
| field | COMSOL: full TPC (solid meshes) + three mesh-cell models | voltages, geometry, permittivities | [Fields](#electric-fields) |
| drift in the liquid | drift map in the composite field, NEST v(\|E\|), lifetime, electron cloud | τ, D_L, D_T | [Drift](#drift-in-the-liquid) |
| extraction | NEST `CalculateG2` at the liquid temperature (172.07 K), moved +0.13 kV/cm in E_liq | liquid field below the surface | [Extraction](#extraction) |
| electroluminescence | Monteiro et al. 2007 along the electron path | \|E\|(x), p_eq | [EL](#electroluminescence-yield) |
| EL map | 64 random-walking electrons per start point, PyBoltz v, D_L, D_T | stack cell field | [EL map](#the-el-map-gas-transport-and-gas-diffusion) |
| S2 time | EL emission quantiles ⊗ longitudinal diffusion | EL map, D_L | [S2 shape](#s2-time-profile-and-width) |
| light | Geant4 optical light maps (QE inside) | optics in `materials.yaml` | [Optics](#optics) |
| sensors, DAQ | double PE, SPE width and template, noise, self-trigger | `sensors.yaml`, `daq_*.yaml` | [Chain](chain.md) |

## Energy deposits and clusters

- **Source:** Cs-137 as an ion at rest, decayed by Geant4's radioactive-decay module; place from
  `config/positions.yaml` (z tape: r 129 mm, azimuth 198° ± 6°, z = (tape − 19.3 cm) × 10 mm). Physics list:
  `G4EmStandardPhysics_option4`, decay, radioactive decay (the long-lifetime threshold is lifted so that Cs-137
  decays); production cut 0.1 mm. Every energy deposit in the xenon is written out.
- **Clustering (lineage):** each γ interaction (Compton, photo-absorption) starts a cluster, the electron it frees and
  its secondaries stay in it; a lineage breaks after a 10 ns gap (`time_threshold_ns`), no distance threshold
  (`gamma_distance_threshold_cm`, `brem_distance_threshold_cm` 0). One row per cluster: energy-weighted position,
  summed energy, time, NEST interaction type. fuse classifies Compton and photo-absorption electrons as β, so every
  ER cluster uses NEST's β-ER model (decision 2026-11-01, as XENON).
- **Open:** the track size enters only the electron cloud (track σ 0.2 mm, a guess); no pile-up (source rate only
  places events on the timeline).

## Quanta (NEST)

Per cluster fuse's `NestYields` calls `GetYields(type, E, |E|_local, ρ)` and `GetQuanta`:

```
n_γ = N_ex + r N_i ,   n_e = (1 − r) N_i ,   n_γ + n_e = N_q = E / W
```

(N_ex / N_i the exciton / ion ratio, r the recombination fraction, depending on E and the field). The local field is
that of the state's 3D field map at the cluster, floored at 0.01 V/cm (NEST β yields are NaN for 0 < |E| < ~1e-3
V/cm; PR #22); the density is the saturated liquid at the state pressure (2.8947 g/cm³ at 1.49 bar). Widths: NEST
defaults (A_ER = 0.046452; fuse's comment 0.096452 is wrong). Zero-field states use NEST γ-ER at 0 V/cm per cluster
(β-ER is undefined at 0 V/cm; `physics.zero_field_yields`).

| model (662 keV, ρ 2.8947 g/cm³) | field [V/cm] | photons / keV | electrons / keV |
|---|---|---|---|
| β-ER (used) | 25 / 97 / 150 | 42.1 / 34.0 / 30.6 | 32.2 / 40.3 / 43.7 |
| γ-ER (reference) | 25 / 97 / 150 | 54.8 / 42.5 / 38.4 | 19.5 / 31.8 / 35.9 |

Sum 74.3 quanta per keV at every field (W = 13.5 eV at this density). **Against the data:** at 97 V/cm the data (Doke
fit) give 45.8 photons + 27.3 electrons per keV: β-ER has too few photons, γ-ER is closer. The charge follows NEST at
the effective field between 25 and 140 V/cm, the light does not (mostly a PMT non-linearity; field-scan note). In
quanta the 662 keV peak is 7–9 % wide per channel and 0.5 % in the sum: recombination fluctuations dominate. A_ER is
not tuned to the data.

## Electric fields

- **Full-TPC model** (COMSOL 6.2, generated from `geometry.yaml`, `materials.yaml`, `efield/cases.yaml`): permittivities
  LXe 1.96, GXe 1.00, PTFE 2.1; field-shaping rings on a 5 × 1 GΩ chain; meshes as solid discs. Drift field at the centre
  1.005 × nominal for every case (ma: 97.0 V/cm).
- **Etched meshes:** 0.15 mm foils, square holes 2.45 mm, bars 0.15 × 0.15 mm with **sharp edges**, pitch 2.6 mm (456
  holes). Cell models (quarter cell, mirror walls): gate, cathode, and the stack (gate + surface + anode + top screen).
- **Orientation:** the gate lattice is at 29.4° to the top-PMT anodes (from the data lattice, posrec fit). The survey of
  2026-11-17 confirmed that **anode and gate have the same orientation**, so the stack cell has the anode holes aligned
  above the gate holes; their **lateral offset was not measured** (zero in the model). The **top screen is rotated**
  (angle not recorded); it stays at 29.4° in the model, 8.35 mm above the anode it hardly matters.
- **Composite field** (drift map): `E = E_cell(position in its cell) + [E_full − ⟨E_cell⟩]`, bracket taken just outside
  the foil band; far from a mesh `E = E_full`.

| where (state ma) | value | source |
|---|---|---|
| drift field, TPC centre | 97.0 V/cm | full-TPC model |
| stack cell far below the gate / liquid above the gate | 96.5 / 2337 V/cm | stack cell |
| liquid below / gas above the surface (cell mean) | 1.70 / 3.33 kV/cm | EL map |
| max \|E\| (bar edges) | 24.7 kV/cm | stack cell (singular at sharp edges) |
| inside the aligned anode hole | down to 0.06 kV/cm at z 9.79 mm | stack cell track |

The etched meshes give f_mesh ≈ 0.92 of the parallel-plate gas field (3.57 → 3.3 kV/cm for ma). Above the anode the
field points the other way (anode +2101 V, top screen 0 V), so each anode hole holds a field null.

**Flux focusing into the gate holes:** the flux of one cell is conserved, so above the gate it fills the area fraction
`E_drift / E_above = 96.5 / 2337 = 0.041` of the cell: a bundle of half-width `(p/2) √0.041 ≈ 0.26 mm`. Electrons
cross the gate within ~0.2–0.27 mm of the hole centre; the field lines bend into the holes within ~1.5 mm below the
gate.

## Drift in the liquid

- **Velocity:** NEST `SetDriftVelocity(T, ρ, |E|)` at the saturated liquid of the state (172.07 K, 2.8947 g/cm³ at
  1.49 bar), with the local |E| of the composite field. Data (SR-2026.3 D scan) vs NEST at 172 K: 1–2.5 % slower at
  97–150 V/cm, 14 % faster at 25 V/cm (MC / data drift time 1.117 / 0.989 / 0.975 at 25 / 97 / 150 V/cm).
- **Lifetime:** survival `exp(−t/τ)`, τ of the state (ma 1044 µs).
- **Diffusion** (`materials.yaml`, `liquid_xenon.transport`): D_L 25 cm²/s, D_T 55 cm²/s (approximate literature
  values). The data imply D_L ≈ 20 cm²/s (clean ring sample, 2026-11-02). Drift-time spread `σ_t = √(2 D_L t) / v̄`.
- **Electron cloud** (`plugins/drift.py`): the drift map is read at `cloud_samples` = 16 points per cluster, Gaussian
  with

  ```
  σ_xy = √(σ_track² + 2 D_T t) ,   σ_z = √(σ_track² + 2 D_L t) ,   σ_track = 0.2 mm
  ```

  (t = the cluster's drift time, all diffusion applied at the start). The surface fraction multiplies the survival;
  drift time and the **gate crossing are the mean over the points that reach the surface**. That mean sets the S2
  position and the gate-cell coordinates at which the EL map is read.
- **Why the cloud mean washes out the mesh lattice:** single electrons cross the gate within 0.26 mm of a hole centre,
  so they map the 2.6 mm lattice exactly (coherence 0.87–0.89 at z −5 and −25 mm). A cloud wider than that reaches
  several holes (σ 0.3 mm: 72 % of the clouds), and the mean lands between holes: coherence 0.48 / 0.29 (1 mm map)
  and 0.57 / 0.35 / 0.24 at z −5 / −25 / −45 mm (0.25 mm map) *(v7)*. MC truth at the gate *(v7)*: 0.21 with the
  cloud mean, 0.79 without. Reconstructed, MC 990068 (v8): 0.089 / 0.080 at 2.58 mm (S2 > 10k: 0.12 / 0.12); data
  7984: 0.082 / 0.068 at 2.72 / 2.80 mm (S2 > 10k: 0.15 / 0.14). The lattice is reproduced. The cloud size (track σ,
  D_T) is therefore an open parameter, to be fitted on the data lattice vs drift time together with the S2 width.
- **Drift map grid:** one electron per start point, steps 0.1 mm (0.02 mm within 1 mm of a mesh). Grid 0.25 × 0.25 ×
  0.5 mm since PR #49 (2026-11-20; was 1 × 1 × 0.5 mm). On the 1 mm grid the hole catchments came out 2.3 and once 3.45
  mm wide instead of 2.6 mm (the hole of a start point decided at ±0.5 mm); on 0.25 mm 2.55–2.85 mm. ~0.37 ms per
  track, ~1 h per state. The grid is part of the drift key.

## Extraction

NEST's `CalculateG2` extraction efficiency at the liquid temperature T, parametrised in E_gas = E_liq · 1.96, moved
along the liquid field:

```
ε_ext(E_liq) = NEST_G2((E_liq + s) · ε_L / ε_G ; T) ,   s = 0.13 kV/cm   (state key extraction: {model: nest, shift_kV_cm: 0.13})
```

T is the liquid temperature of the state: xenon at saturation at the state's `pressure_bar` (pmain, absolute; NIST table
in `materials.yaml`), 172.07 K at 1.49 bar. It is taken from the pressure, not from the temperature sensors.

with E_liq the field 0.05 mm below the surface per EL-map start point (`xamssim.elmap.extraction_curve`).

- **Fit** (2026-11-21, study `2026-10-31_sr2026_3_r900`, `analysis/extraction_fit.py 172.07`): cS2 vs ΔV of the 9
  anode / gate sets at 4.0 mm LXe + 5.30 mm GXe (geometry v8), absolute scale free: **s = 0.134 kV/cm (0.130–0.140),
  χ² 9.9 / 7** (unshifted NEST χ² 1122). E_liq of the scan 1.77–2.23 kV/cm; **EE 0.078** at the operating point
  (R900, ma, D, FN) … 0.25 at the highest set.
- **Gap and shift are degenerate:** with the 9.65 mm geometry (v7) the same fit gave s = 0.212 (χ² 8.7 / 7); 0.35 mm
  less gap at fixed shift raises EE by ×1.4 (rough). The drawing (9.15 mm between the foil faces) fixes the gap.
- **Before** (2026-11-02): the same fit on nestpy's default `VDetector` temperature (177 K, not set) gave s = 0.302
  (χ² 6.8 / 7, EE 0.060 at R900). The shape fits equally well at both temperatures; at 172 K EE is ×1.30 higher in every
  set (the free scale ×0.77).
- **Field model** (v8): the field just below the surface is uniform over the cell (1.776 kV/cm at R900, 3.482 kV/cm
  just above), so it does not depend on where the focused electrons cross; it is 7 % below parallel plates
  (1.91 / 3.74 kV/cm): mesh leakage, effective ΔV 2.556 kV, 77 % of the loss at the anode. The top screen is at 0 V,
  8.70 mm above the anode; floating at anode voltage it would raise E_liq by only ~2.4 % *(v7)*.
- **What the shift is:** with parallel plates (no mesh leakage) the same data need **no shift** (s = 0.00, χ² 12.1 / 7):
  in the v8 geometry the shift compensates the mesh leakage relative to NEST's (parallel-plate) parametrisation.
  NEST at its default 177 K would need s = 0.224 (χ² 7.6 / 7). The fit uses the liquid temperature from the pressure.

## Electroluminescence yield

Monteiro et al. (2007), integrated along the tracked electron path (steps 0.01 mm), clipped at 0 below threshold:

```
dN_γ/dx [photons / cm] = 140 E[kV/cm] − 116 p_eq[bar] ,   p_eq = ρ_gas / ρ(293.15 K, 1 bar)
```

p_eq is the pressure the gas density would have at 293 K: saturated vapour at 1.49 bar (0.01426 g/cm³) gives
**p_eq = 2.65 bar**, EL threshold 116 p_eq / 140 = 2.19 kV/cm. For ma: 180 photons / cm at 3.48 kV/cm, ~95 over 5.30
mm in a uniform field; the EL map's cell mean is 114 photons per electron (map cb22a9ee9965; the field rises towards
the anode).
Validity: measured in uniform fields; here also used at the bar edges (up to ~25 kV/cm in the singular FE field) and
in the field null (below threshold: no light).

## The EL map: gas transport and gas diffusion

`xamssim/elmap.py`: from the stack cell, electrons start on a 0.025 mm (u, v) grid over a quarter gate cell, 0.01 mm
above the surface, and move against the gas field in 0.01 mm steps to the anode bars. Stored per start point:
extraction efficiency, photons per electron, transit time, emission-time quantiles 5 … 95 %.

**Gas transport (PyBoltz / Magboltz, Biagi cross sections; Xe 1118 Torr, 172.3 K, saturated vapour at 1.49 bar; not
tuned)** in `materials.yaml` `gas_xenon.transport`:

| \|E\| [kV/cm] | v [mm/µs] | D_L [cm²/s] | D_T [cm²/s] | PyBoltz run |
|---|---|---|---|---|
| 0.10 | 0.93 | 90 | 1000 | low field, 1e7 collisions (2026-11-20) |
| 0.50 | 1.26 | 90 | 1000 | low field |
| 1.00 | 1.48 | 90 | 710 | low field |
| 2.50 | 2.18 | 150 | 553 | fine, 1e8 collisions (2026-11-01) |
| 3.25 | 2.76 | 162 | 534 | fine |
| 7.00 | 6.40 | 242 | 506 | fine |

`drift_velocity_table` (0.1–7 kV/cm; below 2.5 kV/cm added 2026-11-20, before that v was held at 2.18 mm/µs) and
`diffusion_table` (new, 2026-11-20) are smoothed by hand (~10 % noise at low field); outside them the end values
hold. Raw PyBoltz points: v 0.93 ± 0.10 mm/µs, D_L 133, D_T 1034 cm²/s at 0.1 kV/cm. Studies:
`2026-10-31_sr2026_3_r900/analysis/pyboltz_gxe_fine.py`, `2026-11-19_sr2026_3_t16_t18/analysis/pyboltz_gxe_lowfield.py`.
Sanity check: 1.53 ± 0.03 mm/µs at 500 V/cm, 760 Torr, 295 K vs 1.42 ± 0.03 measured.

**Random walk (EL model v3, PR #50):** from every start point 64 electrons (`EL_ELECTRONS`) move along d = −E/|E|:

```
Δx = d (ℓ + g_∥ √(2 D_L Δt)) + g_⊥ √(2 D_T Δt) ,   Δt = ℓ / v(|E|) ,   ℓ = 0.01 mm
```

(g standard normal; D_L along, D_T across the field). The map holds their mean photons, transit and path and the
quantiles of their pooled emission times. Over the ~1.8 µs transit at 3.5 kV/cm, σ_T ≈ √(2 · 530 cm²/s · 1.8 µs) ≈ 0.44
mm, larger than the focused bundle (0.27–0.30 mm).

### The field null in the aligned anode holes

*(v7: found with the 9.65 mm stack cell and the EL map v2, 2026-11-20; not recomputed for v8. In the v8 map
cb22a9ee9965, with gas diffusion, the yield varies 103–120 photons per electron over the cell (104 / 108 / 113 / 117
at the four positions of the table) and no start point has an emission gap > 0.4 µs.)*

Without diffusion every electron of a start point followed one field line. The electrons that the liquid drift
focuses onto the gate-hole centre run straight into the aligned anode hole: ~80 % of the light is emitted at
3.3 kV/cm up to z ≈ 9.0 mm, then |E| drops to 0.06 kV/cm at z 9.79 mm (below the EL threshold), the electron crawls
sideways for ~0.5 µs without light and ends on the bar edge at 9–11 kV/cm, emitting the last ~20 % in 8 ns. In the
map: a 0.5–0.9 µs gap in the emission quantiles plus a sharp burst; in the waveforms a dip and a narrow spike
(w50 ~160–195 ns, 15–25 % of the area) that amstrax splits off as a separate peak. Data S2s never show it. Gas
diffusion moves the electrons off the central field line before the null: in the ma map the fraction of the cell with
a gap > 0.4 µs goes from 0.12 to 0.00.

| (u, v) [mm] in the gate cell, state ma | photons / e (v2 → v3) | transit [µs] | t at 80 / 95 % [µs] |
|---|---|---|---|
| (0, 0) hole centre | 92 → 101 | 2.72 → 2.21 | 1.79 / 2.72 → 1.92 / 2.35 |
| (0.3, 0.3) | 84 → 103 | 2.50 → 2.16 | 1.52 / 2.41 → 1.91 / 2.21 |
| (0.8, 0) | 109 → 107 | 1.97 → 2.01 | 1.92 / 1.97 → 1.83 / 2.04 |
| (1.2, 1.2) near the bars | 112 → 110 | 1.85 → 1.89 | 1.77 / 1.84 → 1.77 / 1.93 |

**S2 yield:** the focused electrons (r_cell < 0.4 mm) now give +9 % (92.5 → 101.1 photons), the whole cell +1 %
(106.4 → 107.6). The gas diffusion does **not** explain the MC / data S2 excess (≈ 1.17 beyond the optics).

## S2 time profile and width

Per cluster: S2 time = drift time + EL emission. The waveforms spread the S2 photoelectrons over 4 ns bins: the drift
time (Gaussian, σ_t from D_L) folded with the electron's EL emission profile. The chain's width per cluster:

```
w50 = √((t75 − t25)_EL² + (1.349 σ_t)²) ,   σ_t = √(2 D_L t) / v̄
```

The EL profile is roughly a box of the gas transit (~1.8 µs at 3.5 kV/cm); w50 / transit ≈ 0.55–0.61. With the
5.30 mm gas gap (v8) the MC S2 is 3–7 % narrower than the data: w50 MC 1045 → 1032 ns over 7–35 µs (990068), data
1075 → 1114 ns (7984). The MC shows no rise with drift time, where D_L = 25 cm²/s (literature value for
0.1–0.4 kV/cm) should give a few %; how the longitudinal spread is carried through the chain is under study. At
97 V/cm σ_t at the cathode is ≈ 0.33 µs, so w50 barely grows with drift time (data: visible only at 25 V/cm, 1.1 → 1.6
µs). Data also have a narrow population (w50 < 0.7 µs, edge events with a flat S2 pattern) not in the MC.

## Optics

Geant4 optical light maps: one 178 nm photon per event, Fresnel at the interfaces, PTFE (reflectivity 0.95, specular
0.1 in the liquid: fit 2026-10-11 on SR-2026.2 shapes), steel 0.2, copper 0.3, Rayleigh 45 cm, absorption 550 cm,
QE 0.33 in the map ([Optics](optics.md)). On top of the QE a **PMT collection efficiency** CE (`efficiency` in
`sensors.yaml`): **bottom 0.75, top 0.70** (2026-11-21). CE is degenerate with the photon yield (only yield × CE is
measured); the values are effective factors in the literature range and bridge the absolute light scale of the maps
(×1.4 too much light without them). Check with 990068 at r < 20 mm: S1 photopeak data / MC 0.964; efficiency fit vs
drift ε_bottom 1.029, ε_top 0.992. Open: the bottom S1 rises with depth +9.6 % / 10 µs faster in the data than in the
MC (not uniform optics, PMT non-linearity, angle-dependent QE or the cathode–PMT distance). Data positions stretched
5–8 % in r 5–20 mm and compressed at the edge *(v7)*.

## Reconstruction of the MC

amstrax processes the simulated records as data (context MC2, `xamssim.amstrax_io`). MC2 applies S1(z) and the
electron lifetime, but **no S2(x, y) map** (amstrax `Sites` with `sr_mode False`): the reco cS2 of the Cs photopeak
falls from 17.2k (r < 5 mm) to 12.7k (r > 20 mm). An own MC S2(x, y) map (8 mm cells) restores the 662 keV peak.
The data posrec map `pos_rec_map_v2` is an MC map of the old state `sept`.

## Open issues

| issue | status |
|---|---|
| drift velocity MC vs data | data slower than NEST at 172 K at 97–150 V/cm, faster at 25 V/cm; the drift-z note uses 183 K (cold head, not the liquid) and says faster at every field |
| S2 width vs drift | MC 3–7 % narrower, no rise with drift (D_L 25 should give a few %) |
| electron-cloud size | track σ 0.2 mm, D_T 55: the cloud mean decides the mesh lattice; fit on data |
| data central hotspot | r < 4 mm, narrow S2, low AFT, also without source; parked until the runs with extra PTFE parts; removed by the full data cuts |
| data posrec compression at the edge | data (u, v) span 0.62 vs MC 0.75 |
| excess above 750 keV | data / (MC + BG) 3.9 at all r, 1.26 at r < 20 mm: mostly at large r |
| S2 excess 1.55 | MC S2 too high relative to S1 (990068: data / MC S1 0.964, S2 0.622); single-electron gain test next |
| bottom-S1 depth slope | data / MC +9.6 % / 10 µs (top +3 %) |
| photopeak resolution | MC σ/µ 0.120 / 0.152 vs data 0.103 / 0.123 (cS1 / cS2_top) |
| zero-field S1 | data / MC 0.7–0.9 (NEST yield at 0 V/cm + the depth slope); ridge fit to do |
| extraction threshold | NEST at 172 K needs +0.13 kV/cm (v8); parallel plates need none: the shift is the mesh leakage |
| sharp bar edges | singular field, linear EL yield there |
| absolute light scale | bridged by CE 0.75 / 0.70; plan A (absolute optical fit + new maps) |
| gate–anode lattice offset, top-screen angle | not measured |
