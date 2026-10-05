# XAMS optical simulation

Geant4 optical simulation of the XAMS TPC, to find out how much of the observed light distribution (in particular the
low S2 light on the top PMT) follows from the geometry: the etched meshes, the liquid surface, the PTFE cylinder and the
PMT photocathodes.

## Status

- 2026-10-04: implementation plan `PLAN.md`; geometry sheet `geometry.yaml` (draft, values from the drawings, the thesis and the SR-2026.2 analysis;
  open values marked `null` with a question).
- 2026-10-05: steps 0–5 done (environment, skeleton with solid-angle check, materials with Fresnel check, XAMS
  geometry v1 with mesh-transparency check, optical surfaces of PTFE and steel, S1/S2 sources and scan runner);
  progress in `PLAN.md`.
- 2026-10-05: step 6 — first results in `results/step6/README.md`: S2 top fraction from geometry and optics 0.53–0.59
  (data at low load 0.52; Cs/Na values are load effects); liquid level hardly matters.

## Build and run

```bash
conda activate g4
mkdir -p build && cd build && cmake .. && make -j8 && cd ..
python tools/make_config.py --level 4.0 --out run/config.json
build/xamsopt -c run/config.json -o run/photons.bin build/<macro>.mac
```

Look at the geometry:

```bash
cd build && ./xamsopt -c ../run/config.json -o /tmp/vis.bin             # Qt viewer; /run/beamOn 20 draws photons
cd build && ./xamsopt -c ../run/config.json -o /tmp/vis.bin section.mac  # exact cross sections from Geant4's navigator
python tools/plot_section.py build/section_xz.bin                      # -> build/section_xz.png (--zoom u0 u1 v0 v1)
```

Production scans (parameter grid in `scans/<name>.yaml`, output in `run/scans/<name>/`):

```bash
python tools/run_scan.py scans/s2_optics.yaml --jobs 8
python -c "import sys; sys.path.insert(0, 'tools'); from scan_data import load, top_fraction; ..."
```

Checks: `python tools/check_step1.py`, `check_step2.py`, `check_step3.py`, `check_step4.py`, `check_step5.py` (each prints PASSED / FAILED).

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
