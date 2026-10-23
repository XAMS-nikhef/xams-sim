"""NEST yields and fluctuations without a simulation (plan S9, NEST study): the figures of NEST's light and charge
yield against energy, as in the NEST review / C. Fuselli's thesis (ch. 4, Fig. 2 and 4), for the fields of XAMS states
and with the NEST settings of run files (physics.nest), plus the Cs-137 photopeak in quanta.

    xamssim nest --state sept --state cmb50_a36            # NEST defaults at the drift field of each state
    xamssim nest --field 23 --field 145                     # fields given directly [V/cm]
    xamssim nest --run runs/a.yaml --run runs/b.yaml        # each run file: its state's field and its physics.nest
    xamssim nest ... --types beta,gamma,nr --out nest.png

Uses nestpy as the chain's quanta step (fuse NestYields) does: GetYields (mean photon / electron yields; ER / NR
yield parameters) and GetQuanta (event-by-event fluctuations; the width parameters). The field of a state is the
mean |E| of its field map in the drift region (r < 0.9 of the field cage, 2 mm from gate and cathode); the density is
that of liquid xenon in materials.yaml. Bands: +-1 sigma of the NEST fluctuations per event.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .config import DATA, Resolved, resolve, resolve_state

TYPES = {"beta": "beta", "gamma": "gammaRay", "nr": "NR"}          # name -> nestpy interaction
TITLES = {"beta": "β-ER", "gamma": "γ-ER", "nr": "NR"}
WIDTH_KEYS = ("fano_ions_NR", "fano_excitons_NR", "A_NR", "xi_NR", "omega_NR", "skewness_NR",
              "fano_ER", "A_ER", "omega_ER", "xi_ER", "alpha_skewness_ER")   # NRERWidthsParam order (as fuse)
CS137_KEV = 661.657


def drift_field(res: Resolved) -> tuple[float, float]:
    """Mean and spread of |E| [V/cm] in the drift region of a state's field map."""
    from .fieldmap import FieldMap, path
    g = res.geometry
    z = {m["name"]: m["z_mm"] for m in g["meshes"]}
    r_cage = g["ptfe_cylinder"]["inner_diameter_mm"] / 2
    fm = FieldMap(path(res))
    rng = np.random.default_rng(1)
    n = 20000
    r = 0.9 * r_cage * np.sqrt(rng.random(n))
    phi = 2 * np.pi * rng.random(n)
    zz = rng.uniform(z["cathode"] + 2, z["gate"] - 2, n)
    e = fm(r * np.cos(phi), r * np.sin(phi), zz)
    return float(np.mean(e)), float(np.std(e))


def lxe_density(res: Resolved) -> float:
    return float(res.materials["materials"]["liquid_xenon"]["density_g_cm3"])


class Nest:
    """nestpy with a set of NEST settings (run file physics.nest; {} = NEST's defaults)."""

    def __init__(self, nest: dict | None = None):
        import nestpy
        self.np = nestpy
        self.nc = nestpy.NESTcalc(nestpy.VDetector())
        nest = nest or {}
        er, nr = nest.get("er_yields", -1), nest.get("nr_yields", -1)
        self.er = nestpy.default_er_yields_params() if er == -1 else [float(x) for x in er]
        self.nr = nestpy.default_nr_yields_params() if nr == -1 else [float(x) for x in nr]
        self.widths = list(self.nc.default_NRERWidthsParam)
        for k, v in (nest.get("widths") or {}).items():
            self.widths[WIDTH_KEYS.index(k)] = float(v)

    def yields(self, kind: str, energy: float, field: float, density: float):
        return self.nc.GetYields(interaction=getattr(self.np, TYPES[kind]), energy=float(energy),
                                 drift_field=float(field), A=131.293, Z=54.0, density=float(density),
                                 ERYieldsParam=self.er, nuisance_parameters=self.nr)

    def quanta(self, y, n: int) -> tuple[np.ndarray, np.ndarray]:
        q = [self.nc.GetQuanta(y, free_parameters=self.widths) for _ in range(n)]
        return np.array([x.photons for x in q], float), np.array([x.electrons for x in q], float)

    def curves(self, kind: str, field: float, density: float, energies, n_fluct: int = 200) -> dict:
        out = {k: [] for k in ("ly", "qy", "ly_sd", "qy_sd")}
        for e in energies:
            y = self.yields(kind, e, field, density)
            ph, el = self.quanta(y, n_fluct)
            out["ly"].append(y.PhotonYield / e)
            out["qy"].append(y.ElectronYield / e)
            out["ly_sd"].append(ph.std() / e)
            out["qy_sd"].append(el.std() / e)
        return {k: np.array(v) for k, v in out.items()}


def cases(states=(), fields=(), runs=()) -> list:
    """(label, field [V/cm], density, NEST settings) per curve set."""
    from .chain import physics
    out = []
    for s in states:
        res = resolve_state(s)
        f, sd = drift_field(res)
        out.append((f"{s} ({f:.0f} V/cm)", f, lxe_density(res), {}))
    for f in fields:
        out.append((f"{float(f):g} V/cm", float(f), 2.8748, {}))
    for r in runs:
        res = resolve(r)
        f, sd = drift_field(res)
        nest = physics(res).get("nest") or {}
        tag = ", ".join(f"{k}={v}" for k, v in (nest.get("widths") or {}).items()) or "NEST defaults"
        if nest.get("er_yields", -1) != -1 or nest.get("nr_yields", -1) != -1:
            tag += ", yield parameters set"
        out.append((f"{Path(r).stem}: {res.state_name} {f:.0f} V/cm, {tag}", f, lxe_density(res), nest))
    if not out:
        raise ValueError("give --state, --field or --run")
    return out


def cs137_table(cs: list, n: int = 4000) -> list:
    """The Cs-137 photopeak (662 keV gamma) in quanta per case: mean and relative width of photons and electrons,
    their correlation, the width of the combined quanta (photons + electrons)."""
    rows = []
    for label, field, rho, nest in cs:
        ne = Nest(nest)
        ph, el = ne.quanta(ne.yields("gamma", CS137_KEV, field, rho), n)
        rows.append(dict(case=label, photons=ph.mean(), photons_rel_sd=ph.std() / ph.mean(), electrons=el.mean(),
                         electrons_rel_sd=el.std() / el.mean(), corr=float(np.corrcoef(ph, el)[0, 1]),
                         quanta_rel_sd=(ph + el).std() / (ph + el).mean()))
    return rows


def figure(cs: list, kinds=("beta", "gamma"), emin: float = 0.3, emax: float = 1000.0, n_e: int = 50,
           n_fluct: int = 200):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    energies = np.logspace(np.log10(emin), np.log10(emax), n_e)
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    fig, ax = plt.subplots(2, len(kinds), figsize=(5.6 * len(kinds), 7.5), sharex=True, squeeze=False)
    for j, kind in enumerate(kinds):
        for i, (label, field, rho, nest) in enumerate(cs):
            c = colors[i % len(colors)]
            k = Nest(nest).curves(kind, field, rho, energies, n_fluct)
            ax[0, j].plot(energies, k["ly"], color=c, label=label)
            ax[0, j].fill_between(energies, k["ly"] - k["ly_sd"], k["ly"] + k["ly_sd"], color=c, alpha=0.15, lw=0)
            ax[1, j].plot(energies, k["qy"], color=c)
            ax[1, j].fill_between(energies, k["qy"] - k["qy_sd"], k["qy"] + k["qy_sd"], color=c, alpha=0.15, lw=0)
        if kind != "nr":
            for a in ax[:, j]:
                a.axvline(CS137_KEV, color="0.6", lw=0.6, ls=":")
        ax[0, j].set(title=f"NEST {TITLES[kind]}", ylabel="Ly [photons/keV]", ylim=(0, None))
        ax[1, j].set(xscale="log", xlabel="energy [keV" + ("nr]" if kind == "nr" else "]"), ylabel="Qy [electrons/keV]",
                     ylim=(0, None))
    ax[0, 0].legend(fontsize=7)
    fig.suptitle("NEST light and charge yields\nlines: mean; bands: ±1σ of the fluctuations per event; "
                 "dotted: Cs-137 662 keV", fontsize=9)
    fig.tight_layout()
    return fig


def main(states=(), fields=(), runs=(), kinds=("beta", "gamma"), out=None, n_fluct: int = 200) -> Path:
    cs = cases(states, fields, runs)
    out = Path(out) if out else DATA / "nest" / "nest_yields.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig = figure(cs, kinds=kinds, n_fluct=n_fluct)
    fig.savefig(out, dpi=110)
    print(f"figure: {out}")
    nc = Nest().nc
    print("NEST width defaults (nestpy): " + ", ".join(f"{k} {v:g}" for k, v in zip(WIDTH_KEYS, nc.default_NRERWidthsParam)))
    print("Cs-137 photopeak (662 keV gamma) in quanta, NEST per event:")
    print(f"  {'case':60s} {'photons':>8s} {'σ/μ':>6s} {'electrons':>9s} {'σ/μ':>6s} {'corr':>6s} {'(ph+el) σ/μ':>11s}")
    for r in cs137_table(cs):
        print(f"  {r['case'][:60]:60s} {r['photons']:8.0f} {r['photons_rel_sd']:6.3f} {r['electrons']:9.0f} "
              f"{r['electrons_rel_sd']:6.3f} {r['corr']:+6.2f} {r['quanta_rel_sd']:11.3f}")
    return out
