# Output formats

All binary files are fixed-size little-endian records, readable with `numpy.fromfile`; no ROOT. Coordinates in mm in
the geometry frame (z = 0 at the gate foil, z up; the data frame is mirrored in x: x_data = −x_sim).

## Particle mode — `run/g4/<run>/`

### `deposits.bin` — one record per energy deposit (46 bytes)

One record per Geant4 step with energy deposited in liquid or gas xenon.

| field | type | meaning |
|---|---|---|
| `event` | int32 | event number |
| `x, y, z` | float32, mm | mid-point of the step |
| `t` | float64, ns | post-step time (decay products start at 0) |
| `edep` | float32, keV | deposited energy |
| `particle` | int16 | code of the particle (name in the header) |
| `parent_particle` | int16 | code of the parent's particle (`none` for primaries) |
| `track`, `parent` | int32 | Geant4 track ids (parent 0 for primaries) |
| `creaproc` | int16 | code of the process that created the track (`primary` for primaries) |
| `edproc` | int16 | code of the process that limited the step (`eIoni`, `compt`, `phot`, `msc`, …) |
| `volume` | int16 | code of the volume (`Liquid`, `Gas`, `gateHole`, …) |

### `deposits.events.bin` — one record per event (28 bytes)

`event` (int32), `x_pri, y_pri, z_pri` (float32, mm: primary vertex), `n_deposits` (int32), `edep_lxe`, `edep_gxe`
(float32, keV: total per event in liquid and gas).

### `deposits.json` — header

`deposit_dtype`, `event_dtype` (field names and numpy types) and their byte sizes; `units`; `codes` (code → name
tables: `particle`, `process`, `volume`); `info` (config path, seed, macro, the full config); `counts` (events,
deposits, events with a deposit in the liquid). The code tables are built during the run: always decode with the
header of the same run.

## Optical mode

Every run writes `xxx.bin`, `xxx.bin.summary.json` and `xxx.bin.volumes.json`.

### `xxx.bin` — one record per photon (36 bytes)

With `-d` only detected photons get a record (all photons are still counted in the summary).

| field | type | meaning |
|---|---|---|
| `event` | int32 | photon number in the run |
| `x0, y0, z0` | float32, mm | start position |
| `x1, y1, z1` | float32, mm | end position |
| `end_code` | int16 | 1 detected · 2 absorbed in the xenon · 3 absorbed on a surface (also: entered an absorbing material) · 4 left the world · 0 unknown |
| `sensor` | int16 | 0 bottom PMT · 1–4 top-PMT sectors I–IV (= ch1–ch4) · 6, 7 SiPMs · −1 not detected |
| `volume` | int16 | where it ended: index into `xxx.bin.volumes.json` |
| `n_refl` | int16 | number of reflections on the way |

"Detected" includes the QE: photons that reached a photocathode but were not converted end with code 3 on
`TopPMTSector` / `BottomPMTCathode`.

### `xxx.bin.summary.json`

`n_photons`; `tally` = list of `{end_code, volume, n}` over all photons; `detected_by_sensor`; `info` (config,
seed, macro). Use it for fractions of all emitted photons.

### `xxx.bin.volumes.json`

Volume index → name: `<mesh>Foil` (steel of a mesh foil), `<mesh>Hole` (an etched opening), `<mesh>Ring`,
`<mesh>Rim`, `PTFE`, `PTFE_gas`, `CopperRing`, `TopPMTSector`, `BottomPMTCathode`, `TopPMTWindow`, `*Frame`,
`*Body`, `SiPM`, `Liquid`, `Gas`, `Vessel`, `Bucket`, `World`; `<mesh>` = top_screen, anode, gate, cathode,
bottom_screen.

### Scan folders — `run/scans/<name>/`

`points.json` (index: parameters of every point), per point `point_<i>.json` (its config) and per part
`point_<i>_<k>.bin` (+ the two JSON files, `.log`, `.mac`), `timing.json`.

## Electric field — `results/efield/comsol/`

`checks.json` (built-in checks per case), `maps_rz.npz` (V, E_r, E_z on the (r, z) plane through the first SiPM per
case; `r`, `z` axes), `cell_<electrode>.json`, plots. The solved models are `efield/comsol/build/*.mph`.

## Sensors and coordinates (both modes)

- Top-PMT sectors seen from above: I at (−x, +y), II (+x, +y), III (−x, −y), IV (+x, −y).
- z: liquid surface at the level (4 mm), anode +8, top screen +18, cathode −51.8, bottom screen −59.6, top-PMT window
  +22.5, bottom-PMT window −64.1 mm.
