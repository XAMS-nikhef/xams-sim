# Geometry (v4, from the drawings)

All numbers live in `geometry.yaml`, each with its source (drawings in `reference/XAMS design/`: grid assembly,
PTFE cylinder, field shaping, PTFE bucket, inner cryostat vessel; thesis; position reconstruction v2; the user).
Built by `src/XamsGeometry.cc`.

![Cross section y = 0](results/geometry/section_xz.png)

*Cross section at y = 0 from Geant4's own navigator — exactly what the simulation uses.*

## Parts

| part | model |
|---|---|
| PTFE around the PMTs (v4) | top and bottom alike (drawings `PTFE_between_TS_PMT.pdf`, `PTFE_between_BS_PMT.pdf`, CAD picture: the PMT sits in the slot): a plate from the screen-ring assembly to the window face (2.8 mm of the 7 mm plate) with a 50 mm square opening, and a block around the PMT from the window face to its back with a square slot (top 56 = PMT outline, drawing 54; bottom 56.9); both out to r = 46.3 mm (mesh-ring outer radius) |
| PTFE bucket (v4) | Ø112 / Ø132 mm, 129 mm high (drawing `PTFE_bucket.pdf`); the weir 1.78 mm below the rim **sets the liquid level**, so the rim is at level + 1.78 mm (z = +5.78 mm at 4 mm) and the bucket moves with the simulated level. Bottom 10 mm (not on the drawing). The weir notch is not modelled |
| liquid / gas | liquid xenon fills the bucket up to the level (2 / 3 / 4 mm above the gate; from z = −113 mm); gas above it and all around the bucket |
| cryostat vessel (v4) | stainless steel, Ø146.86 / Ø152.4 mm, 305 mm (drawing `Inner_cryostat_vessel.pdf`), closed; ends 2.77 mm and inner bottom 10 mm below the bucket (both assumed); steel reflectivity, Lambertian |
| meshes (5) | solid 0.15 mm steel foils (Ø80) with **456 square holes** of 2.45 mm (pitch 2.6 mm) etched only in a staircase-shaped area (drawing `XAMS_XAMS grid.pdf`; outermost hole corners at r = 32.8 mm; list in `mesh_holes.json`); everything else up to the ring is solid steel. All at 29.4° to the anodes, two bars crossing on the axis. Open area: 0.888 inside the etched area, 0.67 over the Ø72 bore |
| mesh z | top screen +18, anode +8, gate 0, cathode −51.8, bottom screen −59.6 mm (foil mid-plane) |
| mesh rings | steel, Ø72–92.6 mm, 1.8 mm assembly; the foil (Ø80) on one face, the ring body on the other side of the foil: below the gate and bottom screen, above the cathode, anode and top screen |
| PTFE cylinder | Ø62 / Ø72 mm, 50.85 mm long, in the bores of the gate and cathode rings, against the gate foil; 0.8 mm gap above the cathode foil (real) |
| copper rings | four field-shaping rings Ø72–92.6 × 1.8 mm around the PTFE, centres at z = −10.6, −20.4, −30.2, −40.0 mm (8 mm gaps; gate ring → ring 1 assumed 8 mm) |
| PMTs | two R12699: silica window 54.6 mm square, 2.5 mm thick; photocathode 48.5 mm square behind it (top: 4 sectors 24.25 mm = ch1–ch4); absorbing frame and body. Windows at z = +22.5 (top, facing down) and −64.1 mm (bottom, facing up) |
| SiPMs | two, on the PTFE inner wall at z = −25 mm, azimuth 0° and 90° |
| outside the vessel | absorbing ("World"; no photon gets there) |

Consequences: the gate–anode gap is open sideways between r = 36 and 46 mm (both ring bodies point away from it);
the anode ring sits in the anode–top-screen gap; the copper rings are hidden behind the PTFE.

## Close-ups

![Gate, anode, top screen](results/geometry/section_xz_zoom_top.png){ width="48%" }
![Copper ring 4, cathode, bottom screen](results/geometry/section_xz_zoom_bottom.png){ width="48%" }

![Gate mesh: 456 etched holes](results/geometry/section_gate_xy.png){ width="48%" }
![Seen from the top (top PMT hidden)](results/geometry/view_top.png){ width="48%" }

![3-D view](results/geometry/view.png){ width="48%" }
![3-D view, cut](results/geometry/view_cut.png){ width="48%" }

![Whole setup: TPC in the PTFE bucket in the steel vessel](results/geometry/section_xz_wide.png){ width="48%" }
![Viewer start view (cut open)](results/geometry/view_cut_v4.png){ width="48%" }

## Effect of the surroundings (v4 vs v3)

One parameter point (level 4 mm, PTFE R 0.95 / specular 0.1, steel R 0.35, Rayleigh 45 cm;
`tools/surroundings_compare.py`, `results/surroundings/`). Bucket + vessel alone changed < 1 %; with the PTFE around
the PMTs: S2 light collection top +6.6 %, bottom +8.5 %, S2 top fraction 0.563 → 0.558; S1 top +9 %, bottom +7 %, S1
top fraction 0.177 → 0.179. The shapes (vs r, vs z) do not change. Still ~10 % of the S2 light ends on the vessel
(it leaves sideways through the gate–anode and anode–top-screen gaps). All results were rerun with v4 on
2026-10-07; the fit gives ε_S2 1.17 / ε_S1 0.74 (v3: 1.23 / 0.79), within the ranges of v3.

![v4 vs v3](results/surroundings/compare.png)

## Not (yet) in the model

The three PTFE pillars between gate and anode; holders and structure outside the rings; the weir notch; the SiPM
filters; the vessel lid and what hangs from it. ~10 % of the S2 light ends on the vessel (see above).
