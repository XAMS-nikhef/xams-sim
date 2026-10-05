// Geometry, chosen by config "geometry_mode":
//   "test_box"       (step 1): a cube of liquid xenon with one square photocathode (48.5 mm) at z = test_distance_mm;
//                            photons reaching the outer boundary leave the world (escaped)
//   "test_interface" (step 2): liquid xenon below z = 0, gas xenon above (a plain boundary: Fresnel + total internal
//                            reflection from the refractive indices); photons escape at the top or the bottom
//   "xams"     (step 3): model v1 of the XAMS TPC (not yet implemented)
#pragma once

#include <G4VUserDetectorConstruction.hh>

class G4LogicalVolume;
class G4Material;
class G4VPhysicalVolume;

class DetectorConstruction : public G4VUserDetectorConstruction {
 public:
  G4VPhysicalVolume* Construct() override;

 private:
  G4VPhysicalVolume* BuildTestBox();
  G4VPhysicalVolume* BuildTestInterface();
  G4Material* LiquidXenon();
  G4Material* GasXenon();
  G4Material* Silica();
  G4Material* StainlessSteel();
  G4Material* Photocathode();
  void MakeSensor(G4LogicalVolume* lv, G4VPhysicalVolume* from, G4VPhysicalVolume* to, double qe);
};
