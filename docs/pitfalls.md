# Pitfalls

- **Run Geant4 only inside `conda activate g4`**, otherwise it cannot find its data files and stops.
- **Macros:** an edited macro in `g4/macros/` is only used after copying it to `g4/build/`.
- **Moved folder:** after renaming / moving the repository, reconfigure the build (remove `g4/build/CMakeCache.txt`,
  `cmake -S g4 -B g4/build`), the cache keeps absolute paths.
- **Note PDF:** `notes/make_note.py` needs reportlab (base conda Python, not in `g4`).
- **Scans skip finished parts:** after a geometry or code change, move the old `run/scans/<name>/` away first, or the
  old results are reused.
- **`-d` output:** the `.bin` holds only detected photons; use `n_photons` / the tally for fractions of all photons.
- **Frames:** x_data = −x_sim.
- **Outside the model:** the TPC sits in the PTFE bucket inside the closed steel vessel (v4); beyond the vessel
  nothing. The three PTFE pillars between gate and anode are missing; bucket bottom, vessel ends and the gap below
  the bucket are defaults.
- **Free parameters** (reflectivities, Rayleigh and absorption length, PTFE specular fraction) sit at the middle of
  their range unless set (`--set` or a scan grid).
- **Equal QE** (0.33) on both PMTs; the data top/bottom ratio also contains the relative QE and gain calibration.
- `run/` and `g4/build/` are not in git; everything there can be regenerated.
