# Results — summary

The full write-up with all numbers is the PDF note `notes/XAMS_optical_simulation_2026-10-07.pdf`
(made by `notes/make_note.py`; all results with geometry v4 since 2026-10-07). Detailed pages: [first physics](results/step6/README.md),
[comparison with data](results/step7/README.md), [fit](results/step8/README.md), [design study](results/design_ptfe/README.md).

## S2 top fraction from geometry and optics

0.524–0.584 over all optics ranges and liquid levels; liquid level 2 → 4 mm only +0.010. Strongest knobs: PTFE
specular fraction, steel and PTFE reflectivity.

![S2 top fraction](results/step6/s2_topfraction.png)

## Where the light ends

Only ~25 % of the S2 photons reach a photocathode (8.1 % detected with QE 0.33). The mesh foils take ~40 % (including
the solid band outside the etched area), the mesh and copper rings ~15 %, the cryostat vessel ~10 % and the PTFE
bucket ~2 %.

![Losses](results/step6/losses.png)

## Comparison with the data

The top-sector pattern matches the data for every source (geometry right). S2 area fraction top: simulation 0.55–0.60,
data without a source 0.55 at 10–20 kPE, but much lower and size-dependent with Cs-137 / Na-22 (top-PMT load). S1:
same shape, constant top/bottom factor 0.68–0.76. The data show a central dip in the S2 area fraction top that the model
does not have.

## Fit (step 8)

Shapes reproduced with two efficiency factors on the top/bottom ratio (single scatters): ε_S2 = 1.17, ε_S1 = 0.74.
Low steel reflectivity preferred (robust); PTFE reflectivity, specular part and Rayleigh length not constrained (their
best values moved between geometry v3 and v4). A dead cross on the
top PMT does not explain the central dip.

![Best fit](results/step8/best_fit.png)

![Data vs simulation](results/step7/compare.png)

The central dip versus S2 size: the centre stays at ≈ 0.50 for every size while the ring value falls with size —
more likely a top-PMT signal-processing effect than geometry.

![Central dip vs S2 size](results/step7/central_dip_vs_size.png)

## Design study

Extra PTFE cylinders in the gate–anode and anode–top-screen gaps: S2 light collection +36 % (+43 % with the
cathode–bottom-screen gap too), top fraction unchanged.
