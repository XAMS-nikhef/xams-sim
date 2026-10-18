# Geometry

All dimensions live in `config/geometry.yaml` (material properties and optics in `config/materials.yaml`), each with its source (drawings in `reference/XAMS design/`: grid assembly,
PTFE cylinder, field shaping, PTFE bucket, inner cryostat vessel, the cryostat `XAMS_cryostat.pdf`; thesis; position reconstruction v2; the user).
Built by `g4/src/XamsGeometry.cc`; the COMSOL field model (`efield/comsol/make_model.py`) reads the same file.

**Frame:** the data frame of the position reconstruction (since geometry v5): z = 0 at the gate, z up; +x towards the
top-PMT sectors I and III (ch1, ch3), +y towards I and II (ch1, ch2). Every program works in this frame; there are no
conversions.

![Cross section y = 0](img/geometry_section_xz.png)

*Cross section at y = 0 from Geant4's own navigator — exactly what the simulation uses.*

## Parts

| part | model |
|---|---|
| PTFE around the PMTs (v4) | top and bottom alike (drawings `PTFE_between_TS_PMT.pdf`, `PTFE_between_BS_PMT.pdf`, CAD picture: the PMT sits in the slot): a plate from the screen-ring assembly to the window face (2.8 mm of the 7 mm plate) with a 50 mm square opening, and a block around the PMT from the window face to its back with a square slot (top 56 = PMT outline, drawing 54; bottom 56.9); both out to r = 46.3 mm (mesh-ring outer radius) |
| PTFE bucket (v4) | Ø112 / Ø132 mm, 129 mm high (drawing `PTFE_bucket.pdf`); the weir 1.78 mm below the rim **sets the liquid level**, so the rim is at level + 1.78 mm (z = +5.78 mm at 4 mm) and the bucket moves with the simulated level. Bottom 10 mm (not on the drawing). The weir notch is not modelled |
| liquid / gas | liquid xenon fills the bucket up to the level (2 / 3 / 4 mm above the gate; from z = −113 mm); gas above it and all around the bucket |
| inner cryostat vessel | stainless steel tube Ø146.86 / Ø152.4 mm, 305 mm (= the gas cavity in the model); at each end a flange ring Ø152.4–202.5 × 21 mm around the tube end and a blind flange Ø202.5 × 24 mm closing it (drawing `XAMS_cryostat.pdf`, simplified: no bolt holes, gasket, recesses, ports). Centred on the middle of the drift region (z = −25.9 mm); the bucket bottom is ~55 mm above the cavity bottom. Steel reflectivity, Lambertian (also the blind-flange faces) |
| outer cryostat vessel | stainless steel tube Ø248.46 / Ø254 mm, 456 mm (= the vacuum cavity); flange rings Ø254–290 × 12 mm and blind flanges Ø290 × 12 mm at both ends; vacuum between the vessels; the inner vessel's centre 24 mm below the outer one's (read off the drawing). Matters for the particle mode (gammas from outside); no photon reaches it |
| meshes (5) | solid 0.15 mm steel foils (Ø80) with **456 square holes** of 2.45 mm (pitch 2.6 mm) etched only in a staircase-shaped area (drawing `XAMS_XAMS grid.pdf`; outermost hole corners at r = 32.8 mm; list in `mesh_holes.json`); everything else up to the ring is solid steel. All at 29.4° to the anodes, two bars crossing on the axis. Open area: 0.888 inside the etched area, 0.67 over the Ø72 bore |
| mesh z | top screen +18, anode +8, gate 0, cathode −51.8, bottom screen −59.6 mm (foil mid-plane) |
| mesh rings | steel, Ø72–92.6 mm, 1.8 mm assembly; the foil (Ø80) on one face, the ring body on the other side of the foil: below the gate and bottom screen, above the cathode, anode and top screen |
| PTFE cylinder | Ø62 / Ø72 mm, 50.85 mm long, in the bores of the gate and cathode rings, against the gate foil; 0.8 mm gap above the cathode foil (real) |
| copper rings | four field-shaping rings Ø72–92.6 × 1.8 mm around the PTFE, centres at z = −10.6, −20.4, −30.2, −40.0 mm (8 mm gaps; gate ring → ring 1 assumed 8 mm) |
| PMTs | two R12699: silica window 54.6 mm square, 2.5 mm thick; photocathode 48.5 mm square behind it (top: 4 sectors 24.25 mm = ch1–ch4); absorbing frame and body. Windows at z = +22.5 (top, facing down) and −64.1 mm (bottom, facing up) |
| SiPMs | two, on the PTFE inner wall at z = −25 mm, azimuths 90° / 180° (data frame), 1 mm recessed |
| outside the outer vessel | vacuum ("World", ±160 × ±160 × ±260 mm by default, larger in the particle mode if the source needs it); no lab, no support structure |

Consequences: the gate–anode gap is open sideways between r = 36 and 46 mm (both ring bodies point away from it);
the anode ring sits in the anode–top-screen gap; the copper rings are hidden behind the PTFE.

## Close-ups

![Gate, anode, top screen](img/geometry_section_xz_zoom_top.png){ width="48%" }
![Copper ring 4, cathode, bottom screen](img/geometry_section_xz_zoom_bottom.png){ width="48%" }

![Gate mesh: 456 etched holes](img/geometry_section_gate_xy.png){ width="48%" }
![Seen from the top (top PMT hidden)](img/geometry_view_top.png){ width="48%" }

![The cryostat: inner vessel (gas) in the outer vessel (vacuum), flanges simplified](img/geometry_cryostat_xz.png){ width="48%" }
![Viewer start view (cut open)](img/geometry_view_cut_v4.png){ width="48%" }

Pictures made with `/xamsg4/section` + `xamssim/section.py` and the viewer (geometry version 4).

## Not (yet) in the model

The three PTFE pillars between gate and anode; holders and structure outside the rings; the weir notch; the SiPM
filters; the vessel lid and what hangs from it. 
