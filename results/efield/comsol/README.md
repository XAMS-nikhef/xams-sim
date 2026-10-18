# Electric-field results (COMSOL models)

Results of the field models (manual: `docs/efield.md`). Figures and JSON in this folder;
the 3D views `cell3d_*.html` are not in git (regenerate with `efield/comsol/plot_cell3d.py`).

## Full-TPC model

Checks (`checks.json`): drift field at the centre / nominal = 1.006–1.009; gas / liquid field in the gap = 1.96; chain
current 150 nA at 750 V (5 GΩ); wall potential at the SiPM height as expected from the chain.

## Mesh cells (2026-10-12)

Results (2026-10-12): gate — all drift lines pass, focused into ~0.6 mm channels at the hole centres, zero-field point
~0.8 mm below each bar. Cathode — the reverse field pulls electrons from a layer above the cathode through the holes
(lost for S2): Sept 1.17 mm, BS2 1.22 mm, REF-a 0.86 mm, CM-B 0.23 mm, BS3 0; slow drift just above that layer.

Gate + anode (`run_cell.sh stack` = anode aligned with the gate, `stackx` = anode shifted half a pitch in x; liquid
surface at 4 mm, top screen at 18 mm): aligned — electrons pass the anode holes and land on the bars from above (gas
path 5.3 mm); shifted — they land on the underside of the bar above each gate hole (3.9 mm). Electroluminescence per
electron (140·E − 116·p, p = 2 bar) is 8–18 % higher when shifted (Sept 347 → 375, REF-a 144 → 166, CM-B 98 → 116), so
a misalignment between the meshes gives a moiré S2-gain pattern over x-y.
