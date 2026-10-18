# Your own analysis

Reading the output needs only numpy (no Geant4). From the repository root (`xams-sim/`), in the `xamssim` env:

```python
import sys; sys.path.insert(0, "tools")
import numpy as np
from read_output import read, summary
from scan_data import load, top_fraction
```

## One file

```python
rec, volumes = read("run/my_run.bin")       # rec: numpy structured array, volumes: {index: name}
det = rec[rec["end_code"] == 1]             # detected photons
print(summary(rec, volumes))
```

With `-d` the file holds only detected photons; fractions of *all* emitted photons come from
`run/my_run.bin.summary.json` (`n_photons`, `tally`).

## A scan

```python
scan = load("s2_optics")                    # reads run/scans/s2_optics/
for p in scan["points"]:
    rec = p["rec"]                          # detected photons of all 8 parts together
    f, err = top_fraction(rec)              # top / (top + bottom), binomial error
    lce_top = np.isin(rec["sensor"], (1, 2, 3, 4)).sum() / p["n_photons"]
    print(p["params"], f, lce_top)
    # p["tally"]: {(end_code, volume): n} over ALL photons; p["config_json"]: the full config of this point
```

`load(name, records=False)` reads only the tallies (fast).

## Typical selections

```python
r = np.hypot(rec["x0"], rec["y0"])                    # radius of the S2 / S1 origin
central = rec[r < 10]
s1_slice = rec[(rec["z0"] > -30) & (rec["z0"] < -28)]  # S1 from one depth slice (source s1)
top = rec[np.isin(rec["sensor"], (1, 2, 3, 4))]
u = np.where(np.isin(top["sensor"], (1, 3)), 1, -1)    # per photon; mean over a spot = asymmetry u
```

## Worked example

```bash
python optical/examples/my_first_analysis.py
```

It shows what a scan contains, one photon record, the S2 top fraction overall and versus radius, the sector shares
for S2s in a small spot, where the undetected photons went, and saves a figure. Copy it and change it. For larger
examples see `optical/step6_results.py` (figures of step 6) and `optical/step7_compare.py` (comparison with data in the
same bins as the data analysis).

## Comparing with data

The measured numbers are in `optical/targets/data_2026-10-05.json` (made by
`analysis_SR2026.2/studies/optsim_targets.py`: S2 / S1 area fraction top per source, vs S2 size, r and z, and the
top-array asymmetries u, v vs position). Remember the x mirror between the frames and that the data area fractions
depend on the top-PMT load.
