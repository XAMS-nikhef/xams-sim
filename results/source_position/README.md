# Where was the Cs-137 source? (2026-10-12, quick estimate)

Run groups at Δ750 V (run tables): standard 7645–49, 7668–69, 7687–91; 2 cm lower 7665–67; rotated ~170° 7692–96;
rotated 90° clockwise 7707–10, 7713–20. Source height not recorded in the run plans.

- **3D point-source fit** (`optical/source_position.py`: background-shaped acceptance × [B + A exp(−μ s)/d²], LXe
  attenuation 0.022 /mm inside the bucket): not reliable — the distance runs to its lower bound (80 mm), χ²/ndf 5–19,
  absurd source/background ratios, and "2 cm lower" comes out at the same height. Material outside the bucket, the
  rings and the x-y frame are missing. Only the azimuth is consistent: ~150–160° (data x-y frame) for the standard
  position.
- **Height from the Cs-137 / no-source ratio versus z** (`height_from_z_profile.png/.json`, r < 20 mm): peak at
  z = −36 ± 6 mm (standard) and −36 ± 11 mm (2 cm lower): difference 0.3 ± 12 mm instead of −20. The excess is broad
  (0.7 below the gate → 1.3 at z ≈ −30…−40 mm, high to the cathode) and set mainly by detector effects (near-gate
  population and slow-drift pile-up in the reference), not by the source position.
- Indication only: source at or below the lower half of the TPC, probably near / below cathode level, and/or far
  away. For the next fill: measure the height by tape; collimated z-scan.
