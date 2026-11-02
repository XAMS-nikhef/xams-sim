# Critical parameters: gas gap, liquid level, extraction

The S2 signal of the simulation depends very strongly on a few numbers of the detector state that are hard to measure
directly. Found on the SR-2026.3 R900 / anode-scan data (2026-11-01, study `simulations/2026-10-31_sr2026_3_r900`, note
`notes/XAMS_s2_width_geometry_*.pdf`). Check them first when MC and data S2s disagree.

## What depends on what

| quantity | depends on | sensitivity (R900, gate–anode 8 mm) |
|---|---|---|
| S2 width (w50, EL transit) | gas thickness d_g and gas field E_gas: w50 ≈ 0.61 × d_g / v_gas(E_gas) | 4 → 2.5 mm liquid: w50 0.67 → 1.04 µs (+55 %) |
| extraction efficiency | liquid field just below the surface E_liq = E_gas / 1.96 | near threshold: NEST 1.8 % at 1.84 kV/cm, 10 % at 2.14 kV/cm |
| EL photons per electron | (140 E_gas − 116 p_eq) × d_g (Monteiro) | flat within a few % between 2 + 6 and 4 + 4 mm |
| S2 size | extraction × EL yield × light collection | 4 + 4 → 2 + 6 mm: MC S2 / data 2.77 → 0.6 |

With the gap fixed, the liquid level sets both the gas thickness and the fields:
E_gas = f_mesh × ΔV / (d_g + d_l / 1.96), with f_mesh ≈ 0.92 for the etched meshes (COMSOL stack cell vs parallel plates).

## Inputs and where they live

| parameter | where | how known |
|---|---|---|
| gate–anode gap | `config/detectors/<d>/geometry.yaml` (`meshes`: z, `foil_side`) | drawing (8 mm); orientation of the anode ring matters (flipped: 9.65 mm, `xams2026_flip`) |
| liquid level above the gate | `config/states/<s>.yaml` `liquid_level_mm` | **not measured directly**; from the S2 width (below) |
| gas pressure / temperature | state `pressure_bar`; Magboltz table at 1118 Torr, 172.3 K | sc_snapshot (pmain absolute), PT100s |
| gas drift velocity v_gas(E) | `config/materials.yaml` `gas_xenon.transport.drift_velocity_table` | PyBoltz (Magboltz, Biagi cross sections) |
| extraction efficiency | `materials.yaml` `liquid_xenon.transport.extraction` (NEST) or the state's `extraction` (NEST moved by `shift_kV_cm`, or a table; `xamssim.elmap.extraction_curve`) | literature threshold 1.5–2 kV/cm: uncertain near threshold; fit to the S2 size vs ΔV (below) |

## How to determine the level from data

1. Measure the main-band S2 w50 (S2 2000–20000 PE, r < 20 mm, drift 10–35 µs, w50 > 0.75 µs to remove the narrow edge
   events) for several anode / gate voltages.
2. Fit d_l with the gap fixed: `simulations/2026-10-31_sr2026_3_r900/analysis/liquid_level_scan.py`.
3. Fit the extraction to the S2 size vs ΔV at that geometry: `analysis/extraction_fit.py` (NEST moved along the liquid
   field; the shape of cS2 vs ΔV fixes the shift, the absolute scale stays free). Put the shift in the state
   (`extraction: {model: nest, shift_kV_cm: s}`) and make its EL map: `xamssim maps --state <s> --export el` recomputes
   only the extraction from an EL map of the same geometry (no COMSOL).
4. Run the MC at the fitted level and extraction.

The S2 size vs ΔV alone does not choose the geometry: with a free shift both 2.5 + 5.5 mm (shift 0.09 kV/cm, chi2 9.0 / 7)
and the flipped anode 4.0 + 5.65 mm (0.30 kV/cm, chi2 6.8 / 7) fit; the widths of both S2 populations do.

Results so far (gap 8 mm): SR-2026.3 2.35 mm (believed 4), October 2024 fill 0.75 mm (believed 2). Both ~1.5 mm below
the believed level; state `r900b_l25` (2.5 mm) is the compromise of width and size.

## Not explained by these parameters

The excess of events at short drift time (liquid above the gate, field leak below it) lasts ~3.4 µs in the data and
~2 µs in every 8 mm MC, also after the width cut. Open.
