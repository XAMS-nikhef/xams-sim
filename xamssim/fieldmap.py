"""Field maps: the 3D field of the COMSOL model, read through COMSOL's own API, into the map registry.

The solved model `efield/comsol/build/XAMS_efield.mph` (from `efield/comsol/run.sh`) holds the 3D solution of every HV
case it was solved for. `read_comsol` starts a COMSOL client with the `mph` package (licence needed; COMSOL writes no
files, so its "File system access" preference does not matter), finds the solution of an HV case by its electrode
voltages and evaluates V and E on a regular (x, y, z) grid in the frame of geometry.yaml (the data frame).

Registry file `<data>/maps/field/<key>/efield_xyz.npz`:
    x, y, z          grid axes [mm]
    V [V], Ex, Ey, Ez [V/cm]   shape (nx, ny, nz), float32
    case, voltages, electrodes, mph, mph_mtime   provenance

The meshes are solid discs in the full model (holes not resolved): close to a mesh the mesh-cell models apply (later).

    xamssim maps --state sept --export field          # after efield/comsol/run.sh --states sept
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import yaml

from .config import ROOT, Resolved
from .maps import MAPS, find, register

MPH = ROOT / "efield" / "comsol" / "build" / "XAMS_efield.mph"
FILE = "efield_xyz.npz"
# electrode name in efield/cases.yaml -> parameter in the COMSOL model
ELECTRODES = {"A": "Va", "G": "Vg", "C": "Vc", "BS": "Vbs", "TS": "Vts", "PMT_T": "Vpt", "PMT_B": "Vpb", "SIPM": "Vsipm"}
GRID = dict(step=0.5, xy=36.0)            # mm; z from the bottom to the top PMT window (geometry.yaml)


def _find_solution(num, case: dict, level_mm: float, n_max: int = 50) -> int:
    """Solution number whose electrode parameters equal the case's voltages; the model's liquid level must match."""
    import jpype
    keys = list(ELECTRODES)
    num.setInterpolationCoordinates(jpype.JArray(jpype.JDouble, 2)([[0.0], [0.0], [-25.0]]))
    num.set("expr", ["level"])
    num.set("solnum", jpype.JArray(jpype.JInt)([1]))
    model_level = float(np.array(num.getReal(), float).ravel()[0]) * 1e3       # COMSOL evaluates in SI (m)
    if abs(model_level - level_mm) > 1e-6:
        raise LookupError(f"COMSOL model solved for liquid level {model_level} mm, state has {level_mm} mm: "
                          f"efield/comsol/run.sh --states <state>")
    num.set("expr", [ELECTRODES[k] for k in keys])
    want = np.array([case[k] for k in keys], float)
    for s in range(1, n_max + 1):
        try:
            num.set("solnum", jpype.JArray(jpype.JInt)([s]))
            got = np.array(num.getReal(), float).ravel()
        except Exception:
            break
        if np.allclose(got, want, atol=0.5):
            return s
    raise LookupError(f"no solution in the COMSOL model with voltages {dict(zip(keys, want))}: "
                      f"efield/comsol/run.sh --cases <case>")


def grid_axes(geometry: dict, step: float = GRID["step"], xy: float = GRID["xy"]):
    pz = [p["window_z_mm"] for p in geometry["pmts"]]
    x = np.round(np.arange(-xy, xy + 1e-9, step), 4)
    z = np.round(np.arange(min(pz), max(pz) + 1e-9, step), 4)
    return x, x.copy(), z


def read_comsol(case_name: str, level_mm: float, geometry: dict, mph_file: Path = MPH, step: float = GRID["step"],
                xy: float = GRID["xy"], cores: int = 4, log=print) -> dict:
    """V, Ex, Ey, Ez (V, V/cm) of one HV case on the (x, y, z) grid, from the solved COMSOL model."""
    import jpype
    import mph
    mph_file = Path(mph_file)
    if not mph_file.exists():
        raise FileNotFoundError(f"{mph_file} missing: efield/comsol/run.sh --states <state>")
    case = yaml.safe_load(open(ROOT / "efield" / "cases.yaml"))["cases"][case_name]
    x, y, z = grid_axes(geometry, step, xy)
    t0 = time.time()
    client = mph.start(cores=cores)
    model = client.load(str(mph_file))
    num = model.java.result().numerical().create("xamssim_grid", "Interp")
    sol = _find_solution(num, case, level_mm)
    log(f"COMSOL {client.version}, {mph_file.name}: case {case_name} = solution {sol}")
    num.set("expr", ["V", "es.Ex", "es.Ey", "es.Ez"])
    num.set("solnum", jpype.JArray(jpype.JInt)([sol]))
    X, Y = np.meshgrid(x, y, indexing="ij")
    out = np.empty((4, len(x), len(y), len(z)), np.float32)
    for k, zk in enumerate(z):
        pts = np.stack([X.ravel(), Y.ravel(), np.full(X.size, zk)])
        num.setInterpolationCoordinates(jpype.JArray(jpype.JDouble, 2)(pts.tolist()))
        out[:, :, :, k] = np.array(num.getReal(), float).T.reshape(4, len(x), len(y))   # getReal: (points, expr)
    out[1:] /= 100.0                                            # V/m -> V/cm
    log(f"  {len(x)} x {len(y)} x {len(z)} grid points in {time.time() - t0:.0f} s")
    return dict(x=x, y=y, z=z, V=out[0], Ex=out[1], Ey=out[2], Ez=out[3], case=case_name, level_mm=level_mm,
                voltages=np.array([case[k] for k in ELECTRODES], float), electrodes=np.array(list(ELECTRODES)),
                mph=str(mph_file),
                mph_mtime=time.strftime("%Y-%m-%dT%H:%M", time.localtime(mph_file.stat().st_mtime)))


def export(res: Resolved, mph_file: Path = MPH) -> dict:
    """3D field of the state's HV case from the COMSOL model -> <data>/maps/field/<key>/efield_xyz.npz, registered."""
    case = res.state["hv_case"]
    key = res.map_keys()["field"]
    d = read_comsol(case, res.state["liquid_level_mm"], res.geometry, mph_file)
    rel = f"field/{key}/{FILE}"
    (MAPS / rel).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(MAPS / rel, **d)
    return register(res, "field", [rel], producer_version=f"{Path(mph_file).name} solved {d['mph_mtime']}")


def path(res: Resolved) -> Path:
    """The state's registered 3D field map."""
    e = find("field", res.map_keys()["field"])
    if e is None:
        raise FileNotFoundError(f"no field map for state '{res.state_name}' (key {res.map_keys()['field']}): "
                                f"efield/comsol/run.sh --states {res.state_name} && "
                                f"xamssim maps --state {res.state_name} --export field")
    return MAPS / e["files"][0]


class FieldMap:
    """|E| or a component at (x, y, z) in mm, trilinear on the grid; positions outside are moved to the grid edge."""

    def __init__(self, file):
        from scipy.interpolate import RegularGridInterpolator
        d = np.load(file)
        self.x, self.y, self.z = d["x"], d["y"], d["z"]
        self.lo = np.array([self.x[0], self.y[0], self.z[0]])
        self.hi = np.array([self.x[-1], self.y[-1], self.z[-1]])
        grid = (self.x, self.y, self.z)
        comp = {c: d[c] for c in ("Ex", "Ey", "Ez")}
        emag = np.sqrt(comp["Ex"].astype(float) ** 2 + comp["Ey"].astype(float) ** 2 + comp["Ez"].astype(float) ** 2)
        self._itp = {"E": RegularGridInterpolator(grid, emag)}
        self._itp.update({c: RegularGridInterpolator(grid, a) for c, a in comp.items()})

    def __call__(self, x, y, z, what: str = "E"):
        p = np.clip(np.stack([np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)], axis=-1),
                    self.lo, self.hi)
        return self._itp[what](p)
