"""Writes scans/design_ptfe_s2.yaml and _s1.yaml: extra PTFE cylinders (same radii as the main one) between the rings
of gate-anode, anode-top screen and cathode-bottom screen, alone and combined."""
import yaml

GA = {"name": "gate_anode", "z_bottom_mm": 0.9, "z_top_mm": 7.1}
AT = {"name": "anode_topscreen", "z_bottom_mm": 8.9, "z_top_mm": 17.1}
CB = {"name": "cathode_bottomscreen", "z_bottom_mm": -58.7, "z_top_mm": -52.7}
OPTS = [[], [GA], [AT], [CB], [GA, AT], [GA, AT, CB]]
for src, seed in (("s2", 50000), ("s1", 51000)):
    spec = dict(name=f"design_ptfe_{src}", source=src, rmax_mm=30, photons=8000000, chunks=8, seed=seed,
                base=dict(level=4.0), grid={"extra_ptfe": OPTS})
    with open(f"scans/design_ptfe_{src}.yaml", "w") as f:
        f.write(f"# Design study ({src}): extra PTFE cylinders; written by scans/make_design_ptfe.py\n")
        yaml.safe_dump(spec, f, sort_keys=False)
