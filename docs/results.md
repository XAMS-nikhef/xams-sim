# Results — summary

The full write-up with all numbers is the PDF note `notes/XAMS_optical_simulation_2026-10-05.pdf`
(made by `notes/make_note.py`). Detailed pages: [first physics](results/step6/README.md),
[comparison with data](results/step7/README.md), [fit](results/step8/README.md), [design study](results/design_ptfe/README.md).

## S2 top fraction from geometry and optics

0.531–0.584 over all optics ranges and liquid levels; liquid level 2 → 4 mm only +0.010. Strongest knobs: PTFE
specular fraction, steel and PTFE reflectivity.

![S2 top fraction](results/step6/s2_topfraction.png)

## Where the light ends

Only ~23 % of the S2 photons reach a photocathode (7.6 % detected with QE 0.33). The mesh foils take ~35 % (including
the solid band outside the etched area) and ~32 % leave sideways into the rings or out of the model.

![Losses](results/step6/losses.png)

## Comparison with the data

The top-sector pattern matches the data for every source (geometry right). S2 area fraction top: simulation 0.56–0.60,
data without a source 0.55 at 10–20 kPE, but much lower and size-dependent with Cs-137 / Na-22 (top-PMT load). S1:
same shape, constant top/bottom factor 0.72. The data show a central dip in the S2 area fraction top that the model
does not have.

## Fit (step 8)

Shapes reproduced with two efficiency factors on the top/bottom ratio: ε_S2 = 1.13, ε_S1 = 0.77. Low steel reflectivity
and a small specular PTFE part preferred; PTFE reflectivity and Rayleigh length not constrained. A dead cross on the
top PMT does not explain the central dip.

![Best fit](results/step8/best_fit.png)

![Data vs simulation](results/step7/compare.png)

## Design study

Extra PTFE cylinders in the gate–anode and anode–top-screen gaps: S2 light collection +37 % (+43 % with the
cathode–bottom-screen gap too), top fraction unchanged.
