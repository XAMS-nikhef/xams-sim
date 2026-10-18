# Optics and parameters

All optical properties are flat over 6–8 eV (178 nm). Free parameters have a range in `config/materials.yaml` (`optics`); unless set,
`xamssim/g4config.py` takes the middle of the range.

| quantity | value / range | config path |
|---|---|---|
| LXe refractive index | 1.69 | `optics.lxe.refractive_index` |
| LXe Rayleigh length | 30–60 cm (free) | `optics.lxe.rayleigh_length_cm` |
| LXe absorption length | 100–1000 cm (free) | `optics.lxe.absorption_length_cm` |
| GXe refractive index | 1.00 | `optics.gxe.refractive_index` |
| PTFE in liquid: reflectivity / specular fraction | 0.90–0.99 / 0–0.2 | `optics.ptfe_in_liquid.*` |
| PTFE in gas (only for extra PTFE in the design study) | 0.60–0.90 / 0–0.3 | `optics.ptfe_in_gas.*` |
| stainless steel (mesh bars, rings, foil rims) | 0.2–0.5, Lambertian | `optics.stainless_steel_reflectivity` |
| copper field-shaping rings | 0.2–0.4, Lambertian | `optics.copper_reflectivity` |
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
