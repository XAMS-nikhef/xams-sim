# xams-sim — XAMS simulation

Simulation of the XAMS TPC (repository `XAMS-nikhef/xams-sim`, until 2026-10-18 `acolijn/xams-optical-sim`; the last
state before the restructure is tag `optical-sim-final`). Layout:

| Folder | What |
|---|---|
| `config/` | geometry (`geometry.yaml`, `mesh_holes.json`), `materials.yaml`, detector `states/`, `sources/`, simulation `runs/` |
| `g4/` | Geant4 application (optical mode now; particle mode planned) — build: `cmake -S g4 -B g4/build && cmake --build g4/build -j8` |
| `optical/` | optical scans, fits and analysis tools (was `tools/`), scan definitions, data targets, examples |
| `efield/` | electric field (COMSOL), drift lines, mesh cells |
| `xamssim/` | simulation chain: config resolution, map registry, CLI (`xamssim status config/runs/<run>.yaml`) |
| `maps/` | generated maps (not in git) · `results/`, `notes/`, `docs/` as before · `run/` scan output (not in git) |

Geant4 particle mode (plan S2): `xamssim g4 config/runs/<run>.yaml [--events N]` → `run/g4/<run>/deposits.{bin,events.bin,json}`
(one record per energy deposit in xenon, read with `xamssim.g4io.read`); check: `validation/s2_particle_check.py`,
`results/s2_particle/`.

Full-chain plan: `docs/xams_sim_plan.md`. Environment for the chain: conda env `xamssim` (Python 3.12, strax 2.2.3,
fuse 1.6.3, nestpy 2.0.6, amstrax; `pip install -e .[test]`); Geant4 stays in the `g4` env.

## Optical simulation

Geant4 optical simulation of the XAMS TPC, to find out how much of the observed light distribution (in particular the
low S2 light on the top PMT) follows from the geometry: the etched meshes, the liquid surface, the PTFE cylinder and the
PMT photocathodes.

**Documentation: MkDocs site in [`docs/`](docs/index.md)** — `../xams-handbook/.venv/bin/mkdocs serve` and open
http://127.0.0.1:8000 (how it works, running, output format, your own analysis, geometry, optics, validation,
results). **Findings: PDF note `notes/XAMS_optical_simulation_2026-10-05.pdf`** (`python notes/make_note.py`).

## Status

- 2026-10-04: implementation plan `PLAN.md`; geometry sheet `geometry.yaml` (draft, values from the drawings, the thesis and the SR-2026.2 analysis;
  open values marked `null` with a question).
- 2026-10-05: steps 0–5 done (environment, skeleton with solid-angle check, materials with Fresnel check, XAMS
  geometry v1 with mesh-transparency check, optical surfaces of PTFE and steel, S1/S2 sources and scan runner);
  progress in `PLAN.md`.
- 2026-10-05: step 6 — first results in `results/step6/README.md`: S2 top fraction from geometry and optics 0.53–0.59
  (data at low load 0.52; Cs/Na values are load effects); liquid level hardly matters.
- 2026-10-05: geometry v2 from the drawings (grid assembly, PTFE cylinder, copper field-shaping rings): ring bore
  Ø72 with the ring body on the side of the foil as built, PTFE 50.85 mm in the gate/cathode ring bores, four copper
  rings around the PTFE. All scans rerun and `results/` regenerated with v2 (v1 outputs in `run/scans_v1_20261005`).

## Build and run

```bash
conda activate g4
cmake -S g4 -B g4/build && cmake --build g4/build -j8
python optical/make_config.py --level 4.0 --out run/config.json
g4/build/xamsopt -c run/config.json -o run/photons.bin g4/build/<macro>.mac
```

Look at the geometry:

```bash
cd g4/build && ./xamsopt -c ../../run/config.json -o /tmp/vis.bin             # Qt viewer; /run/beamOn 20 draws photons
cd g4/build && ./xamsopt -c ../../run/config.json -o /tmp/vis.bin section.mac  # exact cross sections from Geant4's navigator
python optical/plot_section.py g4/build/section_xz.bin                      # -> g4/build/section_xz.png (--zoom u0 u1 v0 v1)
```

Production scans (parameter grid in `scans/<name>.yaml`, output in `run/scans/<name>/`):

```bash
python optical/run_scan.py optical/scans/s2_optics.yaml --jobs 8
python -c "import sys; sys.path.insert(0, 'tools'); from scan_data import load, top_fraction; ..."
```

Checks: `python optical/check_step1.py`, `check_step2.py`, `check_step3.py`, `check_step4.py`, `check_step5.py` (each prints PASSED / FAILED).

## Model v1

Only what matters first order:

1. the five meshes (top screen, anode, gate, cathode, bottom screen) as real stainless-steel bars (pitch 2.6 mm,
   0.15 mm bars, 0.15 mm foil; lattice as in the gate drawing, bars crossing on the axis),
2. the PMT photocathodes (two R12699-406-M4; top read out in 4 sectors) with their windows,
3. liquid xenon up to the liquid level (Fresnel reflection and total internal reflection at the surface),
4. gas xenon above,
5. the inner PTFE cylinder (diffuse + specular, separate reflectivity in liquid and gas).

Everything else absorbs. Optical photons (178 nm) are generated directly: S2 in the gas gap, S1 in the liquid. Free
optical parameters (PTFE reflectivity, mesh reflectivity, Rayleigh length, QE) are fitted to the data: S2 and S1
top fractions, the top-anode light pattern, and the change between the Oct-2024 (2 + 6 mm) and current (4 + 4 mm)
liquid levels.

## Note on the data

The S2 top fraction depends strongly on the source rate (Cs 0.29, Na-22 0.38, no source 0.52 for S2 > 20 kPE), the
same pattern as the top-PMT gain drop under load (analysis_SR2026.2/notes/XAMS_delayed_signals_SR2026.2.pdf). Compare
the simulation with the low-load value, not with the Cs value.
