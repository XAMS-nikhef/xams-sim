# Validation

Each implementation step ended with a check against an analytic result (`optical/check_step1.py` … `check_step5.py`,
each prints `PASSED` / `FAILED`; details in the [plan](plan.md)).

| step | check | result |
|---|---|---|
| 1 skeleton | point source in front of a 48.5 mm cathode at 10 / 30 / 60 mm | detected fraction = solid angle (pulls 0.02, 0.19, −1.06) |
| 2 materials | beam onto the liquid–gas surface at 0–80° | reflected fraction = (Rs + Rp)/2; total internal reflection from the critical angle 36.3° |
| 3 geometry | overlap check; cross sections vs drawings; collimated beam through one mesh at θ = 0–75°, φ = 0 / 29.4 / 45° | no overlaps; Geant4 = analytic ray trace photon by photon (3·10⁶ photons); transmission 0.888 at normal incidence and the expected drop with angle |
| 4 surfaces | beam onto PTFE / steel; XAMS with black vs R = 0 surfaces; XAMS with R = 1 | reflected fraction = R, specular share = f, diffuse part Lambertian; black = R 0; bookkeeping closes at R = 1 |
| 5 sources | z ranges vs liquid level; uniformity; bookkeeping; precision | as expected; every photon counted once; S2 top fraction ±0.16 % at 4·10⁶ photons |
| 6 physics | each scan point split into two halves with independent seeds | agree (worst pull 2.3) |
