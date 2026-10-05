# Results — summary

The full write-up with all numbers is the PDF note `notes/XAMS_optical_simulation_2026-10-05.pdf`
(made by `notes/make_note.py`). Detailed pages: [first physics](results/step6/README.md),
[comparison with data](results/step7/README.md), [design study](results/design_ptfe/README.md).

## S2 top fraction from geometry and optics

0.537–0.586 over all optics ranges and liquid levels; liquid level 2 → 4 mm only +0.009. Strongest knobs: PTFE
specular fraction, steel and PTFE reflectivity.

![S2 top fraction](results/step6/s2_topfraction.png)

## Where the light ends

Only ~23 % of the S2 photons reach a photocathode (7.6 % detected with QE 0.33). About 39 % leave sideways through the
open gaps into the rings or out of the model; the mesh bars take ~27 %.

![Losses](results/step6/losses.png)

## Comparison with the data

The top-sector pattern matches the data for every source (geometry right). S2 area fraction top: simulation 0.56–0.60,
data without a source 0.55 at 10–20 kPE, but much lower and size-dependent with Cs-137 / Na-22 (top-PMT load). S1:
same shape, constant top/bottom factor 0.70. The data show a central dip in the S2 area fraction top that the model
does not have.

![Data vs simulation](results/step7/compare.png)

## Design study

Extra PTFE cylinders in the gate–anode and anode–top-screen gaps: S2 light collection +36 % (+42 % with the
cathode–bottom-screen gap too), top fraction unchanged.
