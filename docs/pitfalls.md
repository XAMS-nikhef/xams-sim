# Pitfalls

- **Run Geant4 only inside `conda activate g4`**, otherwise it cannot find its data files and stops.
- **Macros:** an edited macro in `macros/` is only used after copying it to `build/`.
- **Scans skip finished parts:** after a geometry or code change, move the old `run/scans/<name>/` away first, or the
  old results are reused.
- **`-d` output:** the `.bin` holds only detected photons; use `n_photons` / the tally for fractions of all photons.
- **Frames:** x_data = −x_sim.
- **Outside the model:** everything beyond |x|, |y| = 60 mm, below z = −90 mm or above +45 mm absorbs; the three
  PTFE pillars between gate and anode are missing. Light that leaves sideways never comes back.
- **Free parameters** (reflectivities, Rayleigh and absorption length, PTFE specular fraction) sit at the middle of
  their range unless set (`--set` or a scan grid).
- **Equal QE** (0.33) on both PMTs; the data top/bottom ratio also contains the relative QE and gain calibration.
- `run/` and `build/` are not in git; everything there can be regenerated.
