// Geometry, chosen by config "geometry_mode":
//   "test_box" (step 1): a cube of liquid xenon with one square photocathode (48.5 mm) at z = test_distance_mm;
//                        photons reaching the outer boundary leave the world (escaped)
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
  G4Material* LiquidXenon();
  G4Material* Photocathode();
  void MakeSensor(G4LogicalVolume* lv, G4VPhysicalVolume* from, G4VPhysicalVolume* to, double qe);
};
