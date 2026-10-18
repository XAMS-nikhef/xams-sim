# Reading the output

In the `xamssim` env, from the repository root. Reading needs only numpy.

## Particle mode

```python
from xamssim import g4io
h, dep, ev = g4io.read("run/g4/s2_cs137_raised")     # header (dict), deposits, events (numpy structured arrays)
g4io.names(h, "particle", dep["particle"])           # codes -> names
g4io.code(h, "process", "phot")                       # name -> code (-1 if it never occurred)
h, dep, ev = g4io.read("run/g4/big_run", mmap=True)   # memory-mapped deposits for large files
```

Typical selections:

```python
import numpy as np
r = np.hypot(dep["x"], dep["y"])
tpc = dep[(r < 31) & (dep["z"] > -51.8) & (dep["z"] < 0)]           # drift region (liquid inside the PTFE)
e_tpc = np.bincount(tpc["event"], weights=tpc["edep"], minlength=len(ev))   # energy per event in the drift region
photopeak = e_tpc >= 655                                               # Cs-137
electrons = dep[g4io.names(h, "particle", dep["particle"]) == "e-"]
```

Example script: `validation/s2_particle_check.py` (spectrum, photopeak fraction, depth profile).

## Optical mode

```python
import sys; sys.path.insert(0, "optical")
import numpy as np
from read_output import read, summary
from scan_data import load, top_fraction

rec, volumes = read("run/my_run.bin")        # one file: records + {index: volume name}
det = rec[rec["end_code"] == 1]              # detected photons
print(summary(rec, volumes))

scan = load("fit_s2")                        # a scan: run/scans/fit_s2/
for p in scan["points"]:
    rec = p["rec"]                           # detected photons of all parts together
    f, err = top_fraction(rec)               # top / (top + bottom), binomial error
    lce_top = np.isin(rec["sensor"], (1, 2, 3, 4)).sum() / p["n_photons"]
    print(p["params"], f, lce_top)           # p["tally"]: {(end_code, volume): n} over ALL photons
```

`load(name, records=False)` reads only the tallies (fast). With `-d` a file holds only detected photons; fractions of
all photons come from the summary (`n_photons`, `tally`).

```python
r = np.hypot(rec["x0"], rec["y0"])                     # radius of the photon origin
s1_slice = rec[(rec["z0"] > -30) & (rec["z0"] < -28)]  # S1 from one depth slice (source s1)
top = rec[np.isin(rec["sensor"], (1, 2, 3, 4))]
```

Worked example: `python optical/examples/my_first_analysis.py` (what a scan contains, one record, the S2 top
fraction overall and vs radius, sector shares, where undetected photons went, a figure).

## Comparing with data

Measured targets are in `optical/targets/` (made by `analysis_SR2026.2/studies/optsim_targets.py`). Remember the x
mirror between the frames and that the measured area fractions depend on the top-PMT load.

## Electric field

```python
import numpy as np
M = np.load("results/efield/comsol/maps_rz.npz")      # r, z axes; <case>_V, <case>_Er, <case>_Ez (V, V/m)
E = np.hypot(M["cmb50_Er"], M["cmb50_Ez"]) / 100       # |E| in V/cm on the (r, z) plane through a SiPM
```
