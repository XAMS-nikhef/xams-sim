# Validation checks

Run them after changing C++ code or the geometry (in the `xamssim` env; each starts `xamsg4` itself):

```bash
python checks/check_step1.py      # ... check_step5.py; each prints PASSED or FAILED
python -m pytest tests             # Python package
```

| check | what it tests | pass criterion |
|---|---|---|
| `check_step1.py` | point source in front of a 48.5 mm photocathode at 10 / 30 / 60 mm (`test_box`) | detected fraction = solid angle |
| `check_step2.py` | beam onto the liquid–gas surface at 0–80° (`test_interface`) | reflected fraction = (Rs + Rp)/2; total internal reflection beyond the critical angle (36.3°) |
| `check_step3.py` | collimated beam through one mesh at θ = 0–75°, φ = 0 / 29.4 / 45° (`test_mesh`); overlap check | Geant4 = analytic ray trace photon by photon; transmission 0.888 at normal incidence |
| `check_step4.py` | beam onto PTFE / steel (`test_surface`); XAMS with black vs R = 0 surfaces; XAMS with R = 1 | reflected fraction = R, specular share = f, diffuse part Lambertian; bookkeeping closes |
| `check_step5.py` | source z ranges vs liquid level, uniformity, bookkeeping, precision (needs the scan `<data>/scans/step5_reference (`xamssim optical checks/scans/step5_reference.yaml`)`) | as expected; every photon counted once |
| `tests/` | configuration, map keys, registry, materials, particle-mode helpers and reader, launcher, chain input / field map / fuse run | pytest |

The checks live in `checks/` (with the reference scans of check 5 in `checks/scans/`). Known: `check_step4.py` part (c)
(bookkeeping with all surfaces at R = 1) fails with the v4+ geometry, which has absorbing parts (copper, bucket, PMT
holders) the v1-era check does not expect; `check_step5.py` needs its reference scans to exist.

The checks of the roadmap steps against data (S2 particle mode: Cs-137 spectrum and depth profile; S3 micro-physics:
clusters, volumes, NEST yields, anticorrelation) are studies: they are in `../simulations/2026-10-18_s2_particle/` and
`../simulations/2026-10-18_s3_microphysics/` with their run files, scripts and results.
