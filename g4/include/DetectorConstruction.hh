// Geometry, chosen by config "geometry_mode":
//   "test_box"       (step 1): a cube of liquid xenon with one square photocathode (48.5 mm) at z = test_distance_mm;
//                            photons reaching the outer boundary leave the world (escaped)
//   "test_interface" (step 2): liquid xenon below z = 0, gas xenon above (a plain boundary: Fresnel + total internal
//                            reflection from the refractive indices); photons escape at the top or the bottom
//   "test_mesh"      (step 3): one mesh (no ring) in liquid xenon at z = 0, axes along x / y, for the transparency check
//   "test_surface"   (step 4): liquid xenon above a reflecting slab (top face at z = 0) of PTFE or steel
//                            (config "test_surface_material": ptfe | steel); reflected photons escape
//   "xams"           (step 3): model of the XAMS TPC (g4/src/XamsGeometry.cc); v4: in the PTFE bucket and steel vessel
// Optical surfaces (step 4): PTFE, mesh bars and rings reflect (unified model, ground: Lambertian + specular spike;
// reflectivity and specular fraction from the config; the rest absorbed). Config "surfaces": 0 makes them black.
// test_mesh keeps black bars (step-3 transparency check).
#pragma once

#include <G4VUserDetectorConstruction.hh>

#include <string>

class G4LogicalVolume;
class G4Material;
class G4OpticalSurface;
class G4VPhysicalVolume;

class DetectorConstruction : public G4VUserDetectorConstruction {
 public:
  G4VPhysicalVolume* Construct() override;

 private:
  G4VPhysicalVolume* BuildTestBox();
  G4VPhysicalVolume* BuildTestInterface();
  G4VPhysicalVolume* BuildTestMesh();
  G4VPhysicalVolume* BuildTestSurface();
  G4VPhysicalVolume* BuildXams();
  // one etched mesh: square holes, bars along the local x and y axes clipped to radius r_vis, foil thickness t,
  // centred at z in mother, rotated by angle_deg about z; returns the number of bar pieces
  int BuildMesh(G4LogicalVolume* mother, const std::string& name, double z, double angle_deg, double r_vis);
  void BuildPmt(G4LogicalVolume* mother, G4VPhysicalVolume* motherP, const std::string& name, double window_z,
                bool facing_down, bool sectors);
  G4Material* LiquidXenon();
  G4Material* GasXenon();
  G4Material* Silica();
  G4Material* StainlessSteel();
  G4Material* Photocathode();
  G4Material* Ptfe();
  G4Material* Absorber();
  void MakeSensor(G4LogicalVolume* lv, G4VPhysicalVolume* from, G4VPhysicalVolume* to, double qe);
  // reflecting skin on every face of lv: probability `reflectivity` to reflect, of which a fraction `specular` as a
  // mirror (spike) and the rest Lambertian; otherwise absorbed
  void MakeReflector(G4LogicalVolume* lv, double reflectivity, double specular);
  // the same, only on the boundary from -> to (a volume with different media on its two sides, e.g. the PTFE bucket)
  void MakeBorderReflector(G4VPhysicalVolume* from, G4VPhysicalVolume* to, double reflectivity, double specular);
  G4OpticalSurface* ReflectorSurface(const std::string& name, double reflectivity, double specular);
  // PTFE (liquid values), all mesh bars and rings (stainless steel, Lambertian)
  void ApplySurfaces();
};
