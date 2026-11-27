"""NEST quanta with field: which NEST electron-recoil model each ER cluster gets (physics.er_model).

    beta   (default) NEST's beta-ER model per cluster, as fuse NestYields: Geant4 makes the gamma's electrons, every
           cluster is an electron of the cluster's energy.
    gamma  NEST's gamma-ER model per cluster (test, 2026-11-21). NEST's gamma-ER is fitted to full-absorption gamma
           lines; at 97 V/cm it gives more light and less charge than beta-ER (662 keV: 42.3 / 31.5 vs 33.5 / 40.3
           quanta per keV) and a weaker fall of the light per keV with energy. Reweighting the photopeak clusters of MC
           990068 / 990071 predicts that it removes the S2 excess (1.55 -> 1.01) and half of the Co-60 S1 deficit
           (simulations 2026-11-19_sr2026_3_t16_t18, results/nest_gamma_reweight.json).
Fluctuations: NEST's GetQuanta with the run's width parameters, as before. NR and other models unchanged.
"""
from __future__ import annotations

import nestpy
import strax
from fuse.plugins.micro_physics.yields import NestYields

from .zero import ER_MODELS, GAMMA

export, __all__ = strax.exporter()

ER_MODEL_CHOICES = ("beta", "gamma")


@export
class XamsGammaERYields(NestYields):
    """NestYields with NEST's gamma-ER model for every electron-recoil cluster (physics.er_model: gamma)."""

    __version__ = "0.1.0"

    def get_yields_from_NEST(self, en, model, e_field, A, Z, density):
        if model not in ER_MODELS:
            return super().get_yields_from_NEST(en, model, e_field, A, Z, density)
        return self.nc.GetYields(interaction=nestpy.INTERACTION_TYPE(GAMMA), energy=en, drift_field=e_field, A=A, Z=Z,
                                 density=density, ERYieldsParam=self.nest_er_yields_parameters_list,
                                 nuisance_parameters=self.nest_nr_yields_parameters_list)
