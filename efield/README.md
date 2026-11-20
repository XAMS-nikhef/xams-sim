# efield — electric field and electron drift

COMSOL 6.2 models of the XAMS TPC (full TPC with the SiPMs; single mesh cells), generated from the detector's `config/detectors/<d>/geometry.yaml`,
`config/materials.yaml` and `cases.yaml`, solved in batch, analysed in Python.

**Manual: `docs/efield.md`** (also in the MkDocs site). Results of the models: `<data>/efield/comsol/README.md`.
Plan: `docs/efield_plan.md`.

```bash
conda activate xamssim
efield/comsol/run.sh --states r900,d25           # full-TPC model -> <data>/efield/comsol/checks.json, maps_rz.npz
python efield/comsol/plot_rz.py r900              # (r, z) plane through a SiPM with drift lines
efield/comsol/run_cell.sh gate --states r900      # one mesh cell (gate | cathode | stack | stackx)
```
