# Validation checks

Run them after changing C++ code or the geometry (in the `xamssim` env; each starts `xamsg4` itself):

```bash
python optical/check_step1.py      # ... check_step5.py; each prints PASSED or FAILED
python -m pytest tests             # Python package
```

| check | what it tests | pass criterion |
|---|---|---|
| `check_step1.py` | point source in front of a 48.5 mm photocathode at 10 / 30 / 60 mm (`test_box`) | detected fraction = solid angle |
| `check_step2.py` | beam onto the liquid–gas surface at 0–80° (`test_interface`) | reflected fraction = (Rs + Rp)/2; total internal reflection beyond the critical angle (36.3°) |
| `check_step3.py` | collimated beam through one mesh at θ = 0–75°, φ = 0 / 29.4 / 45° (`test_mesh`); overlap check | Geant4 = analytic ray trace photon by photon; transmission 0.888 at normal incidence |
| `check_step4.py` | beam onto PTFE / steel (`test_surface`); XAMS with black vs R = 0 surfaces; XAMS with R = 1 | reflected fraction = R, specular share = f, diffuse part Lambertian; bookkeeping closes |
| `check_step5.py` | source z ranges vs liquid level, uniformity, bookkeeping, precision (needs the scan `run/scans/step5_reference`) | as expected; every photon counted once |
| `tests/` | configuration, map keys, registry, materials, particle-mode helpers and reader, launcher, chain input / field map / fuse run | pytest |

Known: `check_step4.py` part (c) (bookkeeping with all surfaces at R = 1) fails with the v4 geometry, which has
absorbing parts (copper, bucket, vessel) the v1-era check does not expect; `check_step5.py` needs its reference scan to
exist. Both behave the same since before the restructure (tag `optical-sim-final`).

The particle mode is checked with `validation/s2_particle_check.py` (Cs-137 spectrum: photopeak, Compton edge;
photopeak rate and depth profile).

The micro-physics chain is checked with `validation/s3_microphysics_check.py` (after
`xamssim chain config/runs/s2_cs137_raised.yaml --target quanta`): Geant4 energy per xenon region, clusters per event
and single-scatter / multiple-scatter / gamma-X fractions, their sensitivity to the clustering settings, fuse NEST
yields against standalone nestpy at 100 / 145 / 500 V/cm, and the photon–electron anticorrelation at 662 keV. Output in
`results/s3_microphysics/`.
