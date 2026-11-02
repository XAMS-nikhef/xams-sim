"""Extraction and electroluminescence map: what an electron arriving at the liquid surface gives (plan S5).

From the stack cell model of the state (gate + liquid surface + anode + top screen, etched meshes, anode aligned with
the gate; `efield/comsol/run_cell.sh stack --states <s>`), read through COMSOL's API like the other cells. Electrons
start on a grid over one quarter cell just above the liquid surface (u, v relative to the gate-hole centre; the gate
focuses them near u = v = 0) and are tracked against the gas field to the anode bars. Per start point:
    ext_eff    extraction efficiency from the field just below the surface (materials liquid_xenon.transport.extraction
               or the state's `extraction`: NEST CalculateG2, NEST moved along the field, or a table; extraction_curve)
    n_el       EL photons per extracted electron: integral of 140 E[kV/cm] - 116 p_eq[bar] per cm along the path
               (Monteiro et al. 2007; p_eq = pressure at 293 K with the density of the gas)
    t_transit  time from the surface to the anode [µs], with the gas drift velocity of materials.yaml
    t_q        times [µs] at which 5 %, 10 %, ..., 95 % of the electron's EL light has been emitted (S2 shape)
Registry file `<data>/maps/extraction_el/<key>/el.npz`.

    xamssim maps --state sept --export el
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .config import Resolved
from .maps import MAPS, find, register

FILE = "el.npz"
QUANTILES = np.round(np.arange(0.05, 0.951, 0.05), 3)
STEP_MM = 0.01
START_STEP_MM = 0.025
R_293K_1BAR = 131.29 * 1e5 / (8.314462 * 293.15) / 1e6       # g/cm³ of xenon at 1 bar, 293.15 K (ideal gas)


def gas_model(res: Resolved) -> dict:
    mats = res.materials["materials"]
    g, lq = mats["gas_xenon"], mats["liquid_xenon"]
    tr = g.get("transport", {})
    if tr.get("el_yield") != "monteiro2007":
        raise ValueError("materials.yaml: only el_yield 'monteiro2007' is implemented")
    # electron velocity in the gas: a table v(|E|) (drift_velocity_table, e.g. from Magboltz), v = mobility x |E|
    # (drift_mobility_mm_us_per_kV_cm), or a constant (drift_velocity_mm_us)
    tab = tr.get("drift_velocity_table")
    mu = tr.get("drift_mobility_mm_us_per_kV_cm")
    return dict(v_gas=float(tr["drift_velocity_mm_us"]) if tab is None and mu is None else None,
                mu_gas=None if mu is None else float(mu),
                v_table=None if tab is None else (np.asarray(tab["E_kV_cm"], float), np.asarray(tab["v_mm_us"], float)),
                p_eq=g["density_g_cm3"] / R_293K_1BAR,
                eps_ratio=lq["electrical"]["relative_permittivity"] / g["electrical"]["relative_permittivity"])


def gas_velocity(gm: dict, e_v_cm):
    """Electron drift velocity in the gas [mm/µs] at |E| [V/cm] (array): table v(E), mobility x E, or the constant velocity."""
    if gm.get("v_table") is not None:
        e_tab, v_tab = gm["v_table"]
        return np.interp(np.asarray(e_v_cm) / 1e3, e_tab, v_tab)
    if gm["mu_gas"] is not None:
        return np.maximum(gm["mu_gas"] * np.asarray(e_v_cm) / 1e3, 0.05)      # floor: never stall in a field-free corner
    return np.full(np.shape(e_v_cm), gm["v_gas"])


def extraction_table():
    """(E_gas [kV/cm], extraction efficiency) from NEST."""
    import nestpy
    e = np.linspace(3.2, 25.0, 110)
    eff = []
    for x in e:
        d = nestpy.VDetector()
        d.set_E_gas(float(x))
        eff.append(nestpy.NESTcalc(d).CalculateG2(False)[1])
    return e, np.clip(np.array(eff), 0, 1)


def extraction_curve(res: Resolved):
    """The extraction efficiency as a function of the liquid field just below the surface [kV/cm] (array -> array), from
    liquid_xenon.transport.extraction (with the state's `extraction`, config.with_extraction):
        nest                                         NEST CalculateG2 (its E_gas = E_liq x eps_liq / eps_gas)
        {model: nest, shift_kV_cm: s}                NEST at E_liq + s (s > 0: threshold s lower, same shape)
        {model: table, E_liq_kV_cm: [..], eff: [..]} linear in the table, 0 below it, the last value above it"""
    mats = res.materials["materials"]
    spec = (mats["liquid_xenon"].get("transport") or {}).get("extraction", "nest")
    eps = mats["liquid_xenon"]["electrical"]["relative_permittivity"] / mats["gas_xenon"]["electrical"]["relative_permittivity"]
    if spec == "nest":
        spec = {"model": "nest"}
    if not isinstance(spec, dict) or spec.get("model") not in ("nest", "table"):
        raise ValueError(f"extraction: 'nest', {{model: nest, shift_kV_cm}} or {{model: table, E_liq_kV_cm, eff}}, not {spec!r}")
    if spec["model"] == "nest":
        unknown = set(spec) - {"model", "shift_kV_cm", "note"}
        if unknown:
            raise ValueError(f"extraction (nest): unknown key(s) {sorted(unknown)}")
        et, ee = extraction_table()
        shift = float(spec.get("shift_kV_cm", 0.0))
        return lambda e_liq: np.interp((np.asarray(e_liq, float) + shift) * eps, et, ee, left=0.0)
    unknown = set(spec) - {"model", "E_liq_kV_cm", "eff", "note"}
    e_t, f_t = np.asarray(spec.get("E_liq_kV_cm", []), float), np.asarray(spec.get("eff", []), float)
    if unknown or len(e_t) < 2 or len(e_t) != len(f_t) or np.any(np.diff(e_t) <= 0) or np.any((f_t < 0) | (f_t > 1)):
        raise ValueError("extraction (table): E_liq_kV_cm increasing (>= 2 points), eff in [0, 1] of the same length"
                         + (f"; unknown key(s) {sorted(unknown)}" if unknown else ""))
    return lambda e_liq: np.interp(np.asarray(e_liq, float), e_t, f_t, left=0.0, right=f_t[-1])


def compute(res: Resolved, cell: dict | None = None, log=print) -> dict:
    """The extraction / EL map of a state (cell: the stack cell field, else read from the state's cell model)."""
    from scipy.ndimage import map_coordinates
    from . import cellmap
    gm = gas_model(res)
    mc = res.geometry["mesh_common"]
    z_gate = next(m["z_mm"] for m in res.geometry["meshes"] if m["name"] == "gate")
    z_anode = next(m["z_mm"] for m in res.geometry["meshes"] if m["name"] == "anode") - z_gate
    level = res.state["liquid_level_mm"]
    h, hole, foil = mc["pitch_mm"] / 2, mc["hole_size_mm"], mc["foil_thickness_mm"]
    if cell is None:
        cell = cellmap.read_cell("stack", res.hv_case, res.geometry, spec=cellmap.stack_spec(level), log=log)
    u, zc = cell["u"], cell["z"]
    comp = [np.nan_to_num(cell[k]).astype(np.float32) for k in ("Ex", "Ey", "Ez")]
    du, dz = u[1] - u[0], zc[1] - zc[0]

    def field(p):
        idx = np.stack([np.clip(p[:, 0] / du, 0, len(u) - 1), np.clip(p[:, 1] / du, 0, len(u) - 1),
                        np.clip((p[:, 2] - zc[0]) / dz, 0, len(zc) - 1)])
        return np.stack([map_coordinates(c, idx, order=1, mode="nearest") for c in comp], axis=1)

    us = np.round(np.arange(0.0, h + 1e-9, START_STEP_MM), 4)
    U, V = np.meshgrid(us, us, indexing="ij")
    n = U.size
    # extraction: field just below and above the surface
    e_liq = np.linalg.norm(field(np.stack([U.ravel(), V.ravel(), np.full(n, level - 0.05)], axis=1)), axis=1) / 1e3
    e_gas_surf = np.linalg.norm(field(np.stack([U.ravel(), V.ravel(), np.full(n, level + 0.05)], axis=1)), axis=1) / 1e3
    ext = extraction_curve(res)(e_liq)
    # gas: track to the anode bars
    p = np.stack([U.ravel(), V.ravel(), np.full(n, level + 0.01)], axis=1)
    photons = np.zeros(n)
    t = np.zeros(n)
    path = np.zeros(n)
    end = np.zeros(n, np.int8)                       # 0 stuck, 1 anode bar, 2 top of the cell
    hist_t, hist_y = [np.zeros(n)], [np.zeros(n)]
    active = np.arange(n)
    t0 = time.time()
    for k in range(4000):
        if not len(active):
            break
        q = p[active]
        f = field(q)
        emag = np.linalg.norm(f, axis=1)                                  # V/cm
        d = -f / np.maximum(emag, 1e-6)[:, None]
        dy = np.clip(140.0 * emag / 1e3 - 116.0 * gm["p_eq"], 0, None) * STEP_MM / 10.0   # photons in this step
        q = q + d * STEP_MM
        q[:, :2] = np.abs(q[:, :2])                                       # mirror walls of the quarter cell
        over = q[:, :2] > h
        q[:, :2][over] = 2 * h - q[:, :2][over]
        p[active] = q
        photons[active] += dy
        t[active] += STEP_MM / gas_velocity(gm, emag)
        path[active] += STEP_MM
        tt, yy = np.zeros(n), np.zeros(n)
        tt[active], yy[active] = t[active], photons[active]
        hist_t.append(np.where(np.isin(np.arange(n), active), tt, np.nan))
        hist_y.append(np.where(np.isin(np.arange(n), active), yy, np.nan))
        on_bar = (np.abs(q[:, 2] - z_anode) <= foil / 2) & ((q[:, 0] > hole / 2) | (q[:, 1] > hole / 2))
        top = q[:, 2] >= zc[-1] - dz
        end[active[on_bar]] = 1
        end[active[top & ~on_bar]] = 2
        active = active[~(on_bar | top)]
    # emission-time quantiles per electron from the cumulative light
    T, Y = np.array(hist_t), np.array(hist_y)
    tq = np.full((n, len(QUANTILES)), np.nan)
    for i in range(n):
        ok = np.isfinite(T[:, i])
        if photons[i] > 0:
            tq[i] = np.interp(QUANTILES * photons[i], Y[ok, i], T[ok, i])
    shape = U.shape
    log(f"  EL map: {n} start points, {(end == 1).mean():.2f} end on anode bars, photons / e "
        f"{np.median(photons):.0f} (median), transit {np.median(t):.2f} µs, extraction {np.median(ext):.3f} "
        f"({time.time() - t0:.0f} s)")
    return dict(u=us, ext_eff=ext.reshape(shape), n_el=photons.reshape(shape), t_transit_us=t.reshape(shape),
                t_q_us=tq.reshape(shape + (len(QUANTILES),)), quantiles=QUANTILES, path_mm=path.reshape(shape),
                end=end.reshape(shape), e_liq_kV_cm=e_liq.reshape(shape), e_gas_kV_cm=e_gas_surf.reshape(shape),
                v_gas_mm_us=np.nan if gm["v_gas"] is None else gm["v_gas"], v_table=np.nan if gm.get("v_table") is None else np.array(gm["v_table"]),
                mu_gas_mm_us_per_kV_cm=np.nan if gm["mu_gas"] is None else gm["mu_gas"], p_eq_bar=gm["p_eq"])


def _rescaled_from_other_velocity(res: Resolved, log=print) -> dict | None:
    """The EL map of the same inputs except the gas velocity parameter, with its times scaled: no COMSOL needed. The
    paths, the extraction and the EL photons do not depend on it; every time is path / v (constant velocity) or
    sum(step / (mu E)) (mobility), so a map scales from another map of the same kind (velocity -> velocity or mobility ->
    mobility) by v_old / v_new or mu_old / mu_new."""
    from .maps import load_manifest
    want = json.loads(json.dumps(res.map_inputs()["extraction_el"], default=str))
    tw = want["gas"]["transport"]
    if "drift_velocity_table" in tw:
        return None                                                # a velocity table: no rescaling, compute
    key = "drift_mobility_mm_us_per_kV_cm" if "drift_mobility_mm_us_per_kV_cm" in tw else "drift_velocity_mm_us"
    x_new = float(tw[key])
    for e in load_manifest()["maps"]:
        if e["kind"] != "extraction_el":
            continue
        inp = json.loads(json.dumps(e.get("inputs", {}), default=str))
        try:
            ti = inp["gas"]["transport"]
            if key not in ti:
                continue
            x_old = float(ti[key])
            ti[key] = x_new
        except (KeyError, TypeError):
            continue
        if inp == want and all((MAPS / f).exists() for f in e["files"]):
            d = dict(np.load(MAPS / e["files"][0]))
            for k in ("t_transit_us", "t_q_us"):
                d[k] = d[k] * (x_old / x_new)
            d["v_gas_mm_us" if key == "drift_velocity_mm_us" else "mu_gas_mm_us_per_kV_cm"] = np.float64(x_new)
            log(f"  EL map from {e['key']} ({key} {x_old} -> {x_new}, times scaled)")
            return d
    return None


def _reextracted_from_other_model(res: Resolved, log=print) -> dict | None:
    """The EL map of the same inputs except the extraction model, with ext_eff recomputed from its stored liquid field
    below the surface (e_liq_kV_cm): no COMSOL needed. Paths, EL photons and times do not depend on the extraction."""
    from .maps import load_manifest
    want = json.loads(json.dumps(res.map_inputs()["extraction_el"], default=str))
    want.pop("liquid_extraction", None)
    for e in load_manifest()["maps"]:
        if e["kind"] != "extraction_el":
            continue
        inp = json.loads(json.dumps(e.get("inputs", {}), default=str))
        inp.pop("liquid_extraction", None)
        if inp == want and all((MAPS / f).exists() for f in e["files"]):
            d = dict(np.load(MAPS / e["files"][0]))
            d["ext_eff"] = extraction_curve(res)(d["e_liq_kV_cm"]).reshape(d["e_liq_kV_cm"].shape)
            log(f"  EL map from {e['key']} (extraction recomputed: median {np.median(d['ext_eff']):.3f})")
            return d
    return None


def export(res: Resolved) -> dict:
    d = _reextracted_from_other_model(res)
    if d is not None:
        key = res.map_keys()["extraction_el"]
        rel = f"extraction_el/{key}/{FILE}"
        (MAPS / rel).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(MAPS / rel, **d)
        return register(res, "extraction_el", [rel], producer_version="xamssim elmap v2, extraction recomputed from "
                                                                       "another map's liquid field (no COMSOL)")
    d = _rescaled_from_other_velocity(res)
    if d is not None:
        key = res.map_keys()["extraction_el"]
        rel = f"extraction_el/{key}/{FILE}"
        (MAPS / rel).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(MAPS / rel, **d)
        return register(res, "extraction_el", [rel], producer_version="xamssim elmap v1, times scaled from another "
                                                                       "gas drift velocity (no COMSOL)")
    d = compute(res)
    key = res.map_keys()["extraction_el"]
    rel = f"extraction_el/{key}/{FILE}"
    (MAPS / rel).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(MAPS / rel, **d)
    return register(res, "extraction_el", [rel], producer_version="xamssim elmap v1 (stack cell, NEST extraction, "
                                                                   "Monteiro EL)")


def path(res: Resolved) -> Path:
    e = find("extraction_el", res.map_keys()["extraction_el"])
    if e is None:
        raise FileNotFoundError(f"no extraction / EL map for state '{res.state_name}' (key "
                                f"{res.map_keys()['extraction_el']}): xamssim maps --state {res.state_name} --export el")
    return MAPS / e["files"][0]


class ELMap:
    """Look-ups at gate-hole coordinates (u, v) [mm] (nearest grid point of the quarter cell, mirrored)."""

    def __init__(self, file):
        d = np.load(file)
        self.u = d["u"]
        self.d = {k: d[k] for k in ("ext_eff", "n_el", "t_transit_us", "t_q_us", "end")}
        self.quantiles = d["quantiles"]

    def __call__(self, u, v, what):
        du = self.u[1] - self.u[0]
        i = np.clip(np.rint(np.abs(u) / du).astype(int), 0, len(self.u) - 1)
        j = np.clip(np.rint(np.abs(v) / du).astype(int), 0, len(self.u) - 1)
        return self.d[what][i, j]
