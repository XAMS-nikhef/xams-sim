"""Writes optical/scans/design_ptfe_s2.yaml and _s1.yaml: extra PTFE cylinders (same radii as the main one) between the foils
of gate-anode, anode-top screen and cathode-bottom screen, alone and combined."""
import yaml

GA = {"name": "gate_anode", "z_bottom_mm": 0.075, "z_top_mm": 7.925}          # gate foil to anode foil
AT = {"name": "anode_topscreen", "z_bottom_mm": 8.075, "z_top_mm": 17.925}  # in the anode ring bore, up to the top-screen foil
CB = {"name": "cathode_bottomscreen", "z_bottom_mm": -59.525, "z_top_mm": -51.875}  # cathode foil to bottom-screen foil
OPTS = [[], [GA], [AT], [CB], [GA, AT], [GA, AT, CB]]
for src, seed in (("s2", 50000), ("s1", 51000)):
    spec = dict(name=f"design_ptfe_{src}", source=src, rmax_mm=30, photons=8000000, chunks=8, seed=seed,
                base=dict(level=4.0), grid={"extra_ptfe": OPTS})
    with open(f"scans/design_ptfe_{src}.yaml", "w") as f:
        f.write(f"# Design study ({src}): extra PTFE cylinders; written by optical/scans/make_design_ptfe.py\n")
        yaml.safe_dump(spec, f, sort_keys=False)
