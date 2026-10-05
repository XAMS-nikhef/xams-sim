# XAMS optical simulation

A Geant4 simulation of how the 178 nm scintillation light travels through the XAMS TPC: through the liquid and the
gas, through (and onto) the five etched meshes, reflecting on PTFE and steel, until it reaches a photocathode or is
lost. Built to answer whether the light distribution we see — in particular the low S2 light on the top PMT — follows
from the geometry.

![XAMS geometry, cut open](results/geometry/view_cut.png){ width="420" }

## Main findings so far (geometry v2, 5 October 2026)

- **Geometry and optics give an S2 top fraction of 0.54–0.59**, almost independent of the liquid level. Data without a
  source are close (0.55 at 10–20 kPE); the much lower Cs-137 / Na-22 values are the load effect of the top PMT.
- **The top-sector light pattern matches the data** over ±24 mm for every source: the geometry is right.
- **S1 top fraction vs depth:** same shape as the data, one constant factor 0.70 in the top/bottom ratio (small-signal
  efficiency of the top PMT / QE ratio).
- Only ~23 % of the S2 photons reach a photocathode; PTFE also between gate, anode and top screen would give ~+36 %.

Full write-up: the PDF note `notes/XAMS_optical_simulation_2026-10-05.pdf` and the [Results](results.md) pages.

## Quick start

```bash
conda activate g4
cd /Users/acolijn/Documents/XAMS_DAQ/optical_sim
mkdir -p build && cd build && cmake .. && make -j8 && cd ..        # once
python tools/make_config.py --level 4.0 --out run/config_level4.json
cd build && ./xamsopt -c ../run/config_level4.json -o /tmp/vis.bin  # the viewer
```

Then: [how it works](concepts.md) → [running](running.md) → [your own analysis](analysis.md).

## This documentation

Written in Markdown in `optical_sim/docs/`, built with MkDocs (same setup as the XAMS handbook). To read it in a
browser:

```bash
cd /Users/acolijn/Documents/XAMS_DAQ/optical_sim
../xams-handbook/.venv/bin/mkdocs serve        # then open http://127.0.0.1:8000
```

(or `pip install -r requirements-docs.txt` in any Python environment and `mkdocs serve`). `mkdocs build` writes a
static site to `site/`.
