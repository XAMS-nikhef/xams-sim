# Viewers

Both modes have an interactive Geant4 viewer (Qt window; drag = rotate, scroll = zoom, commands in the box at the
bottom).

```bash
xamssim optical  --vis --state cmb50                  # photons; liquid level from the state (or --level 4.0)
xamssim particle config/runs/vis_cs137.yaml --vis      # particles; source from the run
```

| viewer | macro (`g4/macros/`) | start events with | notes |
|---|---|---|---|
| optical | `vis_interactive.mac` | `/run/beamOn 20` | default source: S2 photons in the gas gap; `/xamsg4/source/shape s1` for S1 |
| particle | `vis_particle.mac` | `/run/beamOn 10` | tracks by particle: γ green, e⁻ red, e⁺ blue, others grey; step points shown; 50 events accumulate |

`vis_cs137.yaml` uses the source `cs137_vis_cone`: 662 keV gammas from the raised position in a 20° cone towards the
TPC. For real decays point the run at `cs137_raised` (most decays then miss the TPC).

## Useful commands

| command | does |
|---|---|
| `/vis/viewer/clearCutawayPlanes` | the view starts cut open (plane x = 0, keeps x < 0); this closes it |
| `/vis/viewer/addCutawayPlane 0 0 0 m 0 1 0` | add a cut (point, unit, normal; a plane keeps the side its normal points to) |
| `/vis/viewer/set/cutawayMode union` | keep what is on the kept side of any plane (default: all planes) |
| `/vis/geometry/set/visibility Vessel 0 false` | hide a volume (`Vessel`, `Bucket`, `PTFE`, `CopperRing`, …) |
| `/vis/viewer/set/viewpointThetaPhi 90 90 deg` | side view (`0 0 deg`: top view) |
| `/vis/viewer/set/style wireframe` | wireframe |
| `/vis/scene/endOfEventAction refresh` | show only the last event (particle viewer) |
| `/tracking/verbose 1` | print every step of the next events (particle, volume, energy, process) |

Only the xenon is drawn see-through; see-through volumes inside it are not drawn.

## Exact cross sections

The viewer is a rendering; for the exact geometry ask Geant4's navigator which volume is at every grid point (in the
`g4` env, from `g4/build/`):

```bash
cd g4/build && ./xamsg4 -c ../../run/config_level4.json -o /tmp/s.bin section.mac && cd ../..
python optical/plot_section.py g4/build/section_xz.bin --zoom 25 50 -14 22     # -> g4/build/section_xz.png
```

`section.mac` makes an x–z plane at y = 0 and an x–y plane through the gate. Command:
`/xamsg4/section <file> <xz|yz|xy> <offset> <u_min> <u_max> <v_min> <v_max> <step>` (mm).
