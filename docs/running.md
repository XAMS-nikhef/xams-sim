# Running

All commands from the repository root (`xams-sim/`), inside `conda activate xamssim` — the Geant4 program `xamsg4`
is started in the `g4` env automatically ([setup](setup.md)). The direct `./xamsg4` lines further down also work, but
only inside `conda activate g4`.

## Look at the geometry (viewer)

```bash
xamssim optical --vis --state cmb50          # optical viewer (liquid level from the state; or --level 4.0)
xamssim particle config/runs/vis_cs137.yaml --vis   # particle viewer: Cs-137 events (/run/beamOn 10)
```

A Qt window opens (drag = rotate, scroll = zoom). Type commands in the box at the bottom:

| command | does |
|---|---|
| `/xamsg4/source/shape s2`, `/xamsg4/source/rmax 30 mm`, `/run/beamOn 50` | shoot 50 S2 photons, tracks drawn |
| `/vis/viewer/clearCutawayPlanes` | the viewer starts cut open (plane x = 0, keeps x < 0: a plane keeps the side its normal points to); this closes it |
| `/vis/viewer/addCutawayPlane 0 0 0 m 0 1 0` | add another cut (intersection mode: only what is on the kept side of all planes; `/vis/viewer/set/cutawayMode union` for any) |
| `/vis/geometry/set/visibility Vessel 0 false` | hide the steel vessel (also `Bucket`) |
| `/vis/viewer/set/viewpointThetaPhi 90 90 deg` / `0 0 deg` | side view / top view |
| `/vis/viewer/set/style wireframe` | wireframe |
| `/vis/geometry/set/colour Liquid 0 0.15 0.35 0.85 0.3` | colour + opacity of a volume |

Only the xenon is drawn see-through: in this viewer, see-through volumes inside the see-through xenon are not drawn.

## Exact cross sections

The viewer is a rendering; for the exact geometry ask Geant4's navigator which volume sits at every grid point:

```bash
cd g4/build && ./xamsg4 -c ../../run/config_level4.json -o /tmp/s.bin section.mac && cd ../..
python optical/plot_section.py g4/build/section_xz.bin --zoom 25 50 -14 22    # → g4/build/section_xz.png
```

`section.mac` makes an x–z plane at y = 0 and an x–y plane through the gate; the command is
`/xamsg4/section <file> <xz|yz|xy> <offset> <u_min> <u_max> <v_min> <v_max> <step>` (mm).

## One run

```bash
cat > g4/build/my_run.mac <<'MAC'
/run/initialize
/xamsg4/source/shape s2
/xamsg4/source/rmax 30 mm
/run/beamOn 1000000
MAC
cd g4/build && ./xamsg4 -c ../../run/config_level4.json -o ../../run/my_run.bin -s 1 -d my_run.mac && cd ../..
```

| option | meaning |
|---|---|
| `-c file` | config (from `make_config.py`) |
| `-o file` | output file (`.bin` + `.bin.summary.json` + `.bin.volumes.json`) |
| `-s n` | random seed |
| `-d` | records only for detected photons (all photons still counted in the summary); without it every photon gets a record of 36 bytes |
| `-v` | allow pictures in batch mode |
| no macro | interactive viewer |

Source commands: `/xamsg4/source/shape` `s2 | s1 | point | cylinder | beam | beam_disc`, `/xamsg4/source/rmax`,
`/xamsg4/source/position`, `/xamsg4/source/direction`, `/xamsg4/source/zmin`, `/xamsg4/source/zmax`.
Speed: ~1.5·10⁵ photons per second per process.

## A scan (recommended)

Write a YAML file, e.g. `scans/my_scan.yaml`:

```yaml
name: my_scan                 # output goes to run/scans/my_scan/
source: s2                    # s2 = gas gap, s1 = drift region
rmax_mm: 30                   # photons start at r < 30 mm
photons: 10000000             # per point (~10 s on the Mac for S2; S1 slices in z need ~1e8)
chunks: 8                     # parallel parts per point
seed: 70000                   # change it for an independent repetition
base:
  level: 4.0                  # liquid level above the gate (mm) for every point
  set: {optics.lxe.rayleigh_length_cm: 45}     # fixed overrides (any path in config.json)
grid:                         # every combination is one point
  optics.ptfe_in_liquid.reflectivity: [0.90, 0.95, 0.99]
  optics.copper_reflectivity: [0.2, 0.4]
```

```bash
python optical/run_scan.py scans/my_scan.yaml --jobs 8
```

Interrupted? Run it again: finished parts are skipped. To redo a scan from scratch, first move `run/scans/my_scan/`
away. Existing scan files: `optical/scans/s2_optics.yaml`, `s1_optics.yaml`, `s2_rayleigh.yaml`, `design_ptfe_*.yaml`
(written by `optical/scans/make_design_ptfe.py`), `step5_reference*.yaml`.

## Changing parameters or the design

- One value for one run: `python optical/make_config.py --level 3.0 --set optics.stainless_steel_reflectivity=0.5 --out run/my.json`.
- Permanent geometry changes: edit `config/geometry.yaml`; material and optics changes: `config/materials.yaml` (every value has its source written next to it).
- Design options without changing the code: `extra_ptfe` (extra PTFE cylinders, see `optical/scans/make_design_ptfe.py`).
- New kinds of parts need C++ in `g4/src/XamsGeometry.cc`.

## Checks

`python optical/check_step1.py` … `check_step5.py` re-validate the program (each prints `PASSED` / `FAILED`); run them
after changing C++ code. See [Validation](validation.md).
