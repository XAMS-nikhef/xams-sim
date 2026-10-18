# File map

| Path | What it is | You edit it? |
|---|---|---|
| `config/geometry.yaml` | **all dimensions**: meshes (z, angle, foil side), rings, PTFE, copper rings, PMTs, SiPMs, which part is which material, data targets — each with its source | yes |
| `config/materials.yaml` | **all material properties** (single source): densities and Geant4 definitions, conductor / dielectric (ε), and the optics (refractive indices, Rayleigh / absorption lengths, reflectivities with their fit ranges); reference 2 bar, 175 K | yes |
| `config/mesh_holes.json` | the 456 etched holes of the mesh foils (from the gate drawing) | no |
| `optical/make_config.py` | `geometry.yaml` → one `config.json` (liquid level, free parameters at mid-range unless `--set`) | no |
| `xamsg4.cc` | main program (options `-c -o -s -d -v`) | no |
| `g4/src/XamsGeometry.cc` | builds the XAMS geometry from the config | for new parts |
| `g4/src/DetectorConstruction.cc` | materials, optical surfaces, test geometries | rarely |
| `g4/src/PrimaryGeneratorAction.cc` | photon sources | rarely |
| `g4/src/PhotonActions.cc`, `g4/src/Output.cc` | follow each photon; write records and summary | no |
| `g4/src/SectionScan.cc` | `/xamsg4/section` (exact cross sections) | no |
| `g4/src/PhysicsList.cc`, `g4/src/Config.cc` | optical physics; config reader | no |
| `g4/macros/production.mac` | template for scans | no |
| `g4/macros/vis_interactive.mac` | viewer setup (colours) | to taste |
| `g4/macros/section.mac` | cross sections | sometimes |
| `macros/step*.mac`, `init_only.mac`, `vis_section.mac` | checks, quick test, offscreen picture | no |
| `scans/*.yaml` | scan definitions | yes, make your own |
| `optical/run_scan.py` | runs a scan | no |
| `optical/read_output.py`, `optical/scan_data.py` | readers (one file / a scan) | no — use them |
| `optical/plot_section.py` | draws a cross section | no |
| `optical/check_step1..5.py` | validation checks | no |
| `optical/step6_results.py`, `step7_compare.py`, `design_ptfe.py` | make the result figures / tables | copy them |
| `optical/targets/data_2026-10-05.json` | measured numbers from the data | no |
| `results/` | result notes and figures (also shown in this documentation) | — |
| `notes/make_note.py` → `notes/*.pdf` | the PDF note | — |
| `optical/examples/my_first_analysis.py` | start of your own analysis | copy it |
| `docs/`, `mkdocs.yml` | this documentation | yes |
| `run/`, `g4/build/` | generated output / compiled program (not in git) | — |
