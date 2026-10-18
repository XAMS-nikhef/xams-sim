# XAMS optical simulation

A Geant4 simulation of how the 178 nm scintillation light travels through the XAMS TPC: through the liquid and the
gas, through (and onto) the five etched meshes, reflecting on PTFE and steel, until it reaches a photocathode or is
lost. Built to answer whether the light distribution we see — in particular the low S2 light on the top PMT — follows
from the geometry.

![XAMS geometry, cut open](results/geometry/view_cut_v4.png){ width="420" }

## Main findings so far (geometry v4 from the drawings, 7 October 2026)

- **Geometry and optics give an S2 top fraction of 0.52–0.58**, almost independent of the liquid level. Data without a
  source are close (0.55 at 10–20 kPE); the much lower Cs-137 / Na-22 values are the load effect of the top PMT.
- **The top-sector light pattern matches the data** over ±24 mm for every source: the geometry is right.
- **Fit (step 8):** the shapes of S2 vs r, S1 vs z and the sector pattern are reproduced with two efficiency factors
  on the top/bottom ratio, ε_S2 = 1.17 and ε_S1 = 0.74 (single scatters; QE ratio and the top-PMT small-signal loss);
  low steel reflectivity preferred, the other optical parameters are not constrained. The central dip of the S2 top fraction in the data is not an insensitive cross on the PMT.
- Only ~25 % of the S2 photons reach a photocathode; PTFE also between gate, anode and top screen would give ~+36 %.
- The surroundings (PTFE bucket, cryostat vessel) change nothing; the PTFE PMT holders add 7–9 % light on both PMTs.

Full write-up: the PDF note `notes/XAMS_optical_simulation_2026-10-07.pdf` and the [Results](results.md) pages.

## Quick start

```bash
conda activate g4 && cd ~/Documents/XAMS/xams-sim
cmake -S g4 -B g4/build && cmake --build g4/build -j8   # once: compile xamsg4 (the only thing that needs g4)
conda activate xamssim
xamssim optical --vis --state cmb50                     # the optical viewer
xamssim optical optical/scans/fit_s2.yaml               # an optical scan
xamssim particle config/runs/s2_cs137_raised.yaml       # Cs-137 energy deposits (particle mode)
```

Then: [how it works](concepts.md) → [running](running.md) → [your own analysis](analysis.md).

## This documentation

Written in Markdown in `xams-sim/docs/`, built with MkDocs (same setup as the XAMS handbook). To read it in a
browser:

```bash
cd ~/Documents/XAMS/xams-sim
conda activate xamssim && mkdocs serve   # then open http://127.0.0.1:8000
```

(the `xamssim` env has MkDocs from `requirements-docs.txt`; any Python env with `pip install -r requirements-docs.txt` works too). `mkdocs build` writes a
static site to `site/`.
