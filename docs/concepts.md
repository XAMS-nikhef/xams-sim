# How it works

```
geometry.yaml ──make_config.py──► config.json ──┐
 (all numbers,                   (one concrete    │
  from the drawings)              setting)        ▼
                                  macro.mac ──► xamsopt (Geant4) ──► photons.bin  (+ .summary.json, .volumes.json)
                                  (what to do:                         one record per photon
                                   source, how many)                        │
                                                                            ▼
                                                    Python: optical/read_output.py, optical/scan_data.py → your analysis
```

- **One event = one photon.** A 178 nm photon is started at a random place in the source volume with a random
  direction and polarisation, and followed until it is detected or lost. No scintillation or electrons are
  simulated: only the light.
- **Sources:** `s2` = uniform in the gas gap (liquid surface to just below the anode foil), `s1` = uniform in the
  drift region (cathode to gate), both within a radius `rmax`. The z range follows the liquid level automatically.
- **One record per photon:** where it started, where it ended, how (detected / absorbed / left), which sensor, how
  many reflections.
- **No position grid:** start positions are random and stored per photon, so maps (vs r, x–y, z) are made afterwards
  by binning. One run covers all positions for one parameter setting.
- **A scan** = the same run for a grid of parameter values (liquid level, reflectivities, design options), each point
  split into 8 parallel parts with independent seeds. `optical/run_scan.py` does all of it from one small YAML file.
- **Physics:** Geant4's optical physics — refraction and reflection at boundaries (Fresnel, total internal reflection),
  absorption and Rayleigh scattering in the liquid, reflection on surfaces (PTFE, steel, copper), and detection on the
  photocathodes with probability QE. See [Optics and parameters](optics.md).
