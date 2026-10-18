# Reading the output

In the `xamssim` env. Reading needs only numpy. All outputs are in the data folder `DATA`
(`from xamssim.config import DATA`; default `../simulations/data`, or `$XAMSSIM_DATA`).

## Particle mode

```python
from xamssim import g4io
from xamssim.config import DATA
h, dep, ev = g4io.read(DATA / "g4" / "cs137_cmb50_001")     # header (dict), deposits, events (numpy structured arrays)
g4io.names(h, "particle", dep["particle"])           # codes -> names
g4io.code(h, "process", "phot")                       # name -> code (-1 if it never occurred)
h, dep, ev = g4io.read(DATA / "g4" / "big_run", mmap=True)   # memory-mapped deposits for large files
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
import numpy as np
from xamssim.read_output import read, summary
from xamssim.scan_data import load, top_fraction

rec, volumes = read("/tmp/my_run.bin")        # one file: records + {index: volume name}
det = rec[rec["end_code"] == 1]              # detected photons
print(summary(rec, volumes))

scan = load("example_s2")                    # a scan: <data>/scans/example_s2/
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


## Comparing with data

Comparisons with data are studies (`../simulations/`); the targets of the optical fit are in its study folder (made by
`analysis_SR2026.2/studies/optsim_targets.py`). Simulation and data share one frame (geometry v5); the measured area
fractions depend on the top-PMT load.

## Electric field

```python
import numpy as np
from xamssim.config import DATA
M = np.load(DATA / "efield" / "comsol" / "maps_rz.npz")      # r, z axes; <case>_V, <case>_Er, <case>_Ez (V, V/m)
E = np.hypot(M["cmb50_Er"], M["cmb50_Ez"]) / 100       # |E| in V/cm on the (r, z) plane through a SiPM
```
