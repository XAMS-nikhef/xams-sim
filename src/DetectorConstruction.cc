#include "DetectorConstruction.hh"

#include <G4Box.hh>
#include <G4Exception.hh>
#include <G4LogicalBorderSurface.hh>
#include <G4LogicalVolume.hh>
#include <G4Material.hh>
#include <G4MaterialPropertiesTable.hh>
#include <G4NistManager.hh>
#include <G4OpticalSurface.hh>
#include <G4PVPlacement.hh>
#include <G4SystemOfUnits.hh>

#include <vector>

#include "Config.hh"

namespace {
// all optical properties are defined flat over a band around 178 nm (6.97 eV)
const std::vector<G4double> kEnergies = {6.0 * eV, 8.0 * eV};

std::vector<G4double> Flat(double v) { return {v, v}; }
}  // namespace

G4Material* DetectorConstruction::LiquidXenon() {
  static G4Material* mat = nullptr;
  if (mat) return mat;
  const auto& cfg = Config::Get();
  mat = new G4Material("LXe", 54., 131.29 * g / mole, 2.953 * g / cm3, kStateLiquid, 165. * kelvin);
  auto* mpt = new G4MaterialPropertiesTable();
  mpt->AddProperty("RINDEX", kEnergies, Flat(cfg.Num("optics/lxe/refractive_index", 1.69)));
  mpt->AddProperty("ABSLENGTH", kEnergies, Flat(cfg.Num("optics/lxe/absorption_length_cm", 1e6) * cm));
  mpt->AddProperty("RAYLEIGH", kEnergies, Flat(cfg.Num("optics/lxe/rayleigh_length_cm", 1e6) * cm));
  mat->SetMaterialPropertiesTable(mpt);
  return mat;
}

G4Material* DetectorConstruction::Photocathode() {
  // the bulk is irrelevant: photons stop at its surface (detected with probability QE, else absorbed)
  static G4Material* mat = nullptr;
  if (!mat) mat = G4NistManager::Instance()->FindOrBuildMaterial("G4_Al");
  return mat;
}

void DetectorConstruction::MakeSensor(G4LogicalVolume*, G4VPhysicalVolume* from, G4VPhysicalVolume* to, double qe) {
  auto* surf = new G4OpticalSurface("Photocathode_" + to->GetName(), unified, polished, dielectric_metal);
  auto* mpt = new G4MaterialPropertiesTable();
  mpt->AddProperty("REFLECTIVITY", kEnergies, Flat(0.0));
  mpt->AddProperty("EFFICIENCY", kEnergies, Flat(qe));
  surf->SetMaterialPropertiesTable(mpt);
  new G4LogicalBorderSurface("Border_" + from->GetName() + "_" + to->GetName(), from, to, surf);
}

G4VPhysicalVolume* DetectorConstruction::BuildTestBox() {
  const auto& cfg = Config::Get();
  const double half = 200. * mm;
  const double d = cfg.Num("test_distance_mm", 30.) * mm;
  const double side = cfg.Num("pmt_common/photocathode_square_mm", 48.5) * mm;
  const double thick = 0.1 * mm;

  auto* worldS = new G4Box("World", half, half, half);
  auto* worldL = new G4LogicalVolume(worldS, LiquidXenon(), "World");
  auto* worldP = new G4PVPlacement(nullptr, {}, worldL, "World", nullptr, false, 0, true);

  auto* cathS = new G4Box("TestCathode", 0.5 * side, 0.5 * side, 0.5 * thick);
  auto* cathL = new G4LogicalVolume(cathS, Photocathode(), "TestCathode");
  // copy number = sensor id (10 = test cathode); the front face is at z = d
  auto* cathP = new G4PVPlacement(nullptr, G4ThreeVector(0, 0, d + 0.5 * thick), cathL, "TestCathode", worldL, false, 10, true);
  MakeSensor(cathL, worldP, cathP, cfg.Num("test_qe", 1.0));
  return worldP;
}

G4VPhysicalVolume* DetectorConstruction::Construct() {
  const auto mode = Config::Get().Str("geometry_mode", "xams");
  if (mode == "test_box") return BuildTestBox();
  G4Exception("DetectorConstruction", "GEOM001", FatalException,
              ("geometry_mode '" + mode + "' not implemented yet (XAMS geometry: step 3)").c_str());
  return nullptr;
}
