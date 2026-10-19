# Optics and parameters

All optical properties are flat over 6–8 eV (178 nm). `config/materials.yaml` (`optics`) has one value per parameter:
the fitted value where the optical fit of 2026-10-11 constrained it
(`../simulations/2026-10-05_optical_model_and_fit/results/clean_joint`), otherwise a plausible value. Scans vary them
with `--set` (scan files, `grid:`); `xamssim/g4config.py` rejects a range in the YAML.

| quantity | value / range | config path |
|---|---|---|
| LXe refractive index | 1.69 | `optics.lxe.refractive_index` |
| LXe Rayleigh length | 45 cm (fit; grid 30 / 45 / 60) | `optics.lxe.rayleigh_length_cm` |
| LXe absorption length | 550 cm (not fitted; plausible 100–1000) | `optics.lxe.absorption_length_cm` |
| GXe refractive index | 1.00 | `optics.gxe.refractive_index` |
| PTFE in liquid: reflectivity / specular fraction | 0.95 / 0.1 (fit) | `optics.ptfe_in_liquid.*` |
| PTFE in gas (only for extra PTFE in the design study) | 0.75 / 0.15 (not fitted) | `optics.ptfe_in_gas.*` |
| stainless steel (mesh bars, rings, foil rims) | 0.2, Lambertian (fit; low preferred) | `optics.stainless_steel_reflectivity` |
| copper field-shaping rings | 0.3, Lambertian (not fitted; plausible 0.2–0.4) | `optics.copper_reflectivity` |
| PMT window (fused silica) | n = 1.60; transmission folded into the QE | `optics.pmt_window_refractive_index` |
| PMT QE at 178 nm | 0.33 (both PMTs) | `pmt_common.qe_178nm` |
| SiPM detection efficiency | 1 | `sipms.pde` |

## Surface models

- **Liquid–gas surface, window faces:** plain boundaries — Fresnel reflection and refraction from the refractive
  indices, total internal reflection beyond 36.3° (liquid → gas).
- **PTFE, steel, copper:** Geant4 UNIFIED model, ground, dielectric–metal: with probability R the photon is reflected,
  a fraction *f* of those as a mirror (specular spike), the rest diffusely (Lambertian); otherwise it is absorbed.
- **Photocathodes:** absorb every photon that reaches them; detected with probability QE (no reflection).
- `"surfaces": 0` in the config makes PTFE, steel and copper black (used in a check).
