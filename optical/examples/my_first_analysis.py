#!/usr/bin/env python3
"""Example: read simulation output and do a small analysis of your own.

Run from optical_sim/ (any Python with numpy + matplotlib; Geant4 not needed):
    python optical/examples/my_first_analysis.py

It reads the scan run/scans/s2_optics (made by: python optical/run_scan.py optical/scans/s2_optics.yaml) and shows
  1. what is in a scan (points and their parameters),
  2. what one photon record looks like,
  3. the S2 top fraction, overall and versus radius,
  4. the share of each top-PMT sector for S2s in a small spot,
  5. where the photons that were NOT detected ended up,
and saves a figure optical/examples/my_first_analysis.png.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "optical"))
from scan_data import load, top_fraction  # noqa: E402

# ------------------------------------------------------------------ 1. a scan = a list of points (parameter settings)
scan = load("s2_optics")                       # reads run/scans/s2_optics/
print("scan settings:", {k: scan["spec"][k] for k in ("source", "photons", "rmax_mm")})
for p in scan["points"][:5]:
    print(f"  point {p['id']}: {p['params']}  photons {p['n_photons']:.3g}, detected {len(p['rec'])}")
print("  ...", len(scan["points"]), "points in total")

# pick the point you want, by its parameters
p = next(q for q in scan["points"]
         if q["params"]["level"] == 4.0
         and q["params"]["optics.ptfe_in_liquid.reflectivity"] == 0.95
         and q["params"]["optics.stainless_steel_reflectivity"] == 0.35)
rec = p["rec"]                                 # numpy structured array: one row per DETECTED photon

# ------------------------------------------------------------------ 2. one record
print("\nfields:", rec.dtype.names)
print("first record:", rec[0])
# x0, y0, z0 = where the photon started (mm, z = 0 at the gate); x1, y1, z1 = where it ended;
# sensor = 0 bottom PMT, 1-4 top-PMT sectors I-IV, 6/7 SiPMs; n_refl = number of reflections on the way

# ------------------------------------------------------------------ 3. S2 top fraction, overall and vs r
f, err = top_fraction(rec)
print(f"\nS2 top fraction {f:.4f} +- {err:.4f}")
r = np.hypot(rec["x0"], rec["y0"])
edges = np.arange(0, 31, 2.5)
tf_r = [top_fraction(rec[(r >= a) & (r < b)])[0] for a, b in zip(edges[:-1], edges[1:])]

# ------------------------------------------------------------------ 4. top-sector shares for S2s near (+10, +10) mm
top = rec[np.isin(rec["sensor"], (1, 2, 3, 4))]
spot = top[np.hypot(top["x0"] - 10, top["y0"] - 10) < 2]
shares = [(spot["sensor"] == s).mean() for s in (1, 2, 3, 4)]
print("sector shares (I, II, III, IV) for S2 at (+10, +10) mm:", np.round(shares, 3))

# ------------------------------------------------------------------ 5. where all photons ended (from the tally)
# the tally counts EVERY photon (also the undetected ones): {(end_code, volume name): number}
END = {1: "detected", 2: "absorbed in the xenon", 3: "absorbed on a surface", 4: "left the world"}
n = p["n_photons"]
print("\nlargest end places (fraction of all emitted photons):")
for (code, vol), k in sorted(p["tally"].items(), key=lambda x: -x[1])[:8]:
    print(f"  {k / n:6.3f}  {END.get(code, code):24s} {vol}")

# ------------------------------------------------------------------ figure
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
ax[0].plot(0.5 * (edges[1:] + edges[:-1]), tf_r, "o-")
ax[0].set(xlabel="S2 radius r [mm]", ylabel="S2 top fraction", title="top fraction vs r")
h = ax[1].hist2d(top["x0"], top["y0"], bins=40, range=[[-30, 30], [-30, 30]], weights=(top["sensor"] == 2) * 1.0)
cnt, _, _ = np.histogram2d(top["x0"], top["y0"], bins=40, range=[[-30, 30], [-30, 30]])
ax[1].cla()
with np.errstate(invalid="ignore"):
    ax[1].imshow((h[0] / cnt).T, origin="lower", extent=[-30, 30, -30, 30], vmin=0, vmax=1)
ax[1].set(xlabel="x [mm]", ylabel="y [mm]", title="share of top light on sector II vs S2 position")
fig.tight_layout()
out = ROOT / "optical" / "examples" / "my_first_analysis.png"
fig.savefig(out, dpi=110)
print("\nfigure:", out)
