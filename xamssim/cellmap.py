"""Mesh-cell fields: the field through one cell of the etched gate and cathode meshes, for the composite field (S4).

The full-TPC COMSOL model has the meshes as solid discs. The mesh-cell models (`efield/comsol/run_cell.sh gate|cathode
--states ...`) solve one quarter cell of the real etched mesh (square hole of 2.45 mm, bars 0.15 mm, pitch 2.6 mm, foil
0.15 mm), periodic in x-y (symmetry walls), between planes at the potentials of the TPC. This module reads their 3D
field through COMSOL's API (`mph`) on a fine grid of the quarter cell:

    u, v in [0, p/2] (hole centre at 0, bar centre at p/2), z_loc relative to the mesh mid-plane

Registry file `<data>/maps/mesh_cells/<key>/cells.npz`, per electrode (`gate_*`, `cathode_*`): u, v, z axes [mm],
Ex, Ey, Ez [V/cm] (NaN inside the bars), and the cell average of each component per z (the uniform field the cell
assumes far from the mesh). Used by xamssim.driftmap to build the composite field near each mesh.

    xamssim maps --state sept --export cells          # needs the solved cell models (.mph) and the COMSOL licence
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from .config import ROOT, Resolved
from .maps import MAPS, find, register

BUILD = ROOT / "efield" / "comsol" / "build"
FILE = "cells.npz"
# electrode -> (cell-model parameters that identify the case's solution -> case voltage key, z_loc range [mm]); the gate
# cell ends on the anode plane (Vtop), the cathode cell on the bottom screen (Vbot); gate and cathode: composite field of the
# drift; stack (gate + liquid surface + anode + top screen, anode aligned): extraction and EL (xamssim.elmap)
ELECTRODES = {"gate": ({"Vel": "G", "Vtop": "A"}, (-3.2, 3.98)), "cathode": ({"Vel": "C", "Vbot": "BS"}, (-3.6, 3.6))}
STACK = ({"Vel": "G", "Va": "A"}, (3.4, 12.0))
STEP = 0.02


def read_cell(electrode: str, case: dict, geometry: dict, step: float = STEP, cores: int = 4, log=print,
              spec=None) -> dict:
    import jpype
    import mph
    f = BUILD / f"XAMS_cell_{electrode}.mph"
    if not f.exists():
        raise FileNotFoundError(f"{f} missing: efield/comsol/run_cell.sh {electrode} --states <state>")
    params, (z0, z1) = spec or ELECTRODES[electrode]
    h = geometry["mesh_common"]["pitch_mm"] / 2
    u = np.round(np.arange(0.0, h + 1e-9, step), 4)
    z = np.round(np.arange(z0, z1 + 1e-9, step), 4)
    t0 = time.time()
    client = mph.start(cores=cores)
    model = client.load(str(f))
    from .fieldmap import check_geometry_tag
    check_geometry_tag(model, geometry, f.name)
    num = model.java.result().numerical().create("xamssim_cell", "Interp")
    num.setInterpolationCoordinates(jpype.JArray(jpype.JDouble, 2)([[0.5 * h], [0.5 * h], [z0]]))
    num.set("expr", list(params))
    want = np.array([case[k] for k in params.values()], float)
    sol = None
    for s in range(1, 30):
        try:
            num.set("solnum", jpype.JArray(jpype.JInt)([s]))
            v = np.array(num.getReal(), float).ravel()
        except Exception:
            break
        if np.allclose(v, want, atol=0.5):
            sol = s
            break
    if sol is None:
        raise LookupError(f"no solution with {dict(zip(params, want))} V in {f.name}: run_cell.sh {electrode} --states <state>")
    num.set("expr", ["es.Ex", "es.Ey", "es.Ez"])
    U, V = np.meshgrid(u, u, indexing="ij")
    out = np.full((3, len(u), len(u), len(z)), np.nan, np.float32)
    for k, zk in enumerate(z):
        pts = np.stack([U.ravel(), V.ravel(), np.full(U.size, zk)])
        num.setInterpolationCoordinates(jpype.JArray(jpype.JDouble, 2)(pts.tolist()))
        out[:, :, :, k] = np.array(num.getReal(), float).T.reshape(3, len(u), len(u))
    out /= 100.0                                                             # V/m -> V/cm
    client.remove(model)
    mean = np.nanmean(out, axis=(1, 2))                                      # (3, nz): cell average per z
    mean[:2] = 0.0                    # x, y average of the full cell is zero by symmetry (not of the quarter cell)
    log(f"  {electrode} cell: solution {sol}, {len(u)} x {len(u)} x {len(z)} points, "
        f"far field {mean[2, 0]:.0f} / {mean[2, -1]:.0f} V/cm ({time.time() - t0:.0f} s)")
    return dict(u=u, z=z, Ex=out[0], Ey=out[1], Ez=out[2], mean=mean.astype(np.float32),
                mph=f.name, mph_mtime=time.strftime("%Y-%m-%dT%H:%M", time.localtime(f.stat().st_mtime)))


def export(res: Resolved) -> dict:
    data = {}
    for el in ELECTRODES:
        d = read_cell(el, res.hv_case, res.geometry)
        data.update({f"{el}_{k}": v for k, v in d.items()})
    key = res.map_keys()["mesh_cells"]
    rel = f"mesh_cells/{key}/{FILE}"
    (MAPS / rel).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(MAPS / rel, **data)
    return register(res, "mesh_cells", [rel], producer_version=f"cell models solved {data['gate_mph_mtime']}")


def path(res: Resolved) -> Path:
    e = find("mesh_cells", res.map_keys()["mesh_cells"])
    if e is None:
        raise FileNotFoundError(f"no mesh-cell fields for state '{res.state_name}' (key {res.map_keys()['mesh_cells']}): "
                                f"xamssim maps --state {res.state_name} --export cells")
    return MAPS / e["files"][0]
