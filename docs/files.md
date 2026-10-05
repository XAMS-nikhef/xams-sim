# File map

| Path | What it is | You edit it? |
|---|---|---|
| `geometry.yaml` | **all numbers**: meshes (z, angle, foil side), rings, PTFE, copper rings, PMTs, SiPMs, optics ranges, data targets — each with its source | yes |
| `tools/make_config.py` | `geometry.yaml` → one `config.json` (liquid level, free parameters at mid-range unless `--set`) | no |
| `xamsopt.cc` | main program (options `-c -o -s -d -v`) | no |
| `src/XamsGeometry.cc` | builds the XAMS geometry from the config | for new parts |
| `src/DetectorConstruction.cc` | materials, optical surfaces, test geometries | rarely |
| `src/PrimaryGeneratorAction.cc` | photon sources | rarely |
| `src/PhotonActions.cc`, `src/Output.cc` | follow each photon; write records and summary | no |
| `src/SectionScan.cc` | `/xamsopt/section` (exact cross sections) | no |
| `src/PhysicsList.cc`, `src/Config.cc` | optical physics; config reader | no |
| `macros/production.mac` | template for scans | no |
| `macros/vis_interactive.mac` | viewer setup (colours) | to taste |
| `macros/section.mac` | cross sections | sometimes |
| `macros/step*.mac`, `init_only.mac`, `vis_section.mac` | checks, quick test, offscreen picture | no |
| `scans/*.yaml` | scan definitions | yes, make your own |
| `tools/run_scan.py` | runs a scan | no |
| `tools/read_output.py`, `tools/scan_data.py` | readers (one file / a scan) | no — use them |
| `tools/plot_section.py` | draws a cross section | no |
| `tools/check_step1..5.py` | validation checks | no |
| `tools/step6_results.py`, `step7_compare.py`, `design_ptfe.py` | make the result figures / tables | copy them |
| `targets/data_2026-10-05.json` | measured numbers from the data | no |
| `results/` | result notes and figures (also shown in this documentation) | — |
| `notes/make_note.py` → `notes/*.pdf` | the PDF note | — |
| `examples/my_first_analysis.py` | start of your own analysis | copy it |
| `docs/`, `mkdocs.yml` | this documentation | yes |
| `run/`, `build/` | generated output / compiled program (not in git) | — |
