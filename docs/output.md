# Output files

Every run writes three files: `xxx.bin`, `xxx.bin.summary.json`, `xxx.bin.volumes.json`.

## `xxx.bin` — one record per photon

36 bytes per photon (with `-d`: per detected photon), little-endian, in this order:

| field | type | meaning |
|---|---|---|
| `event` | int32 | photon number in the run |
| `x0, y0, z0` | float32, mm | start position |
| `x1, y1, z1` | float32, mm | end position |
| `end_code` | int16 | 1 detected · 2 absorbed in the xenon · 3 absorbed on a surface (also: entered an absorbing material) · 4 left the world · 0 unknown (should not happen) |
| `sensor` | int16 | 0 bottom PMT · 1–4 top-PMT sectors I–IV (= ch1–ch4) · 6, 7 SiPMs · −1 not detected |
| `volume` | int16 | where it ended: index into `xxx.bin.volumes.json` (e.g. `anodeBar`, `PTFE`, `World`) |
| `n_refl` | int16 | number of reflections on the way (Fresnel, total internal, PTFE, steel, copper) |

## `xxx.bin.summary.json` — every photon counted

`n_photons`; `tally` = list of `{end_code, volume, n}` over all photons (also undetected ones without a record);
`detected_by_sensor`; `info` (config, seed, macro). Use it for fractions of all emitted photons.

## `xxx.bin.volumes.json`

Volume index → name. Names: `<mesh>Foil` (the steel of a mesh foil, mesh = top_screen / anode / gate / cathode / bottom_screen), `<mesh>Hole` (inside a hole),
`<mesh>Ring` (ring body), `<mesh>Rim` (foil on the ring face), `PTFE`, `PTFE_gas`, `CopperRing`, `TopPMTSector`,
`BottomPMTCathode`, `TopPMTWindow`, `*Frame`, `*Body`, `SiPM`, `Liquid`, `Gas`, `World` (= left the modelled region).

## Scan directories

`run/scans/<name>/`: `points.json` (index: parameters of every point), per point `point_<i>.json` (its config) and
per part k = 0..7 `point_<i>_<k>.bin` (+ the two JSON files, `.log`, `.mac`), `timing.json`.

## Coordinates and conventions

- mm; z = 0 at the gate foil, z up. Liquid surface at z = level (2–4 mm). Anode +8, top screen +18, cathode −51.8,
  bottom screen −59.6; top-PMT window +22.5, bottom-PMT window −64.1.
- Top sectors seen from above: I at (−x, +y), II (+x, +y), III (−x, −y), IV (+x, −y).
- **The data frame (position reconstruction v2) is mirrored in x:** x_data = −x_sim, y_data = y_sim.
- "Detected" includes the QE (0.33). Photons that reached a photocathode but were not converted end with code 3 on
  `TopPMTSector` / `BottomPMTCathode`.
