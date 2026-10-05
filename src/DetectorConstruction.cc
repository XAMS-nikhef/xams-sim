#include "DetectorConstruction.hh"

#include <G4Box.hh>
#include <G4Exception.hh>
#include <G4LogicalBorderSurface.hh>
#include <G4LogicalSkinSurface.hh>
#include <G4LogicalVolumeStore.hh>
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

G4Material* DetectorConstruction::GasXenon() {
  static G4Material* mat = nullptr;
  if (mat) return mat;
  const auto& cfg = Config::Get();
  // ~1.7 bar at 175 K; the density does not matter optically (n = 1.00)
  mat = new G4Material("GXe", 54., 131.29 * g / mole, 0.0155 * g / cm3, kStateGas, 175. * kelvin);
  auto* mpt = new G4MaterialPropertiesTable();
  mpt->AddProperty("RINDEX", kEnergies, Flat(cfg.Num("optics/gxe/refractive_index", 1.00)));
  mpt->AddProperty("ABSLENGTH", kEnergies, Flat(1e9 * cm));
  mat->SetMaterialPropertiesTable(mpt);
  return mat;
}

G4Material* DetectorConstruction::Silica() {
  static G4Material* mat = nullptr;
  if (mat) return mat;
  mat = new G4Material("Silica", 2.2 * g / cm3, 2);
  auto* nist = G4NistManager::Instance();
  mat->AddElement(nist->FindOrBuildElement("Si"), 1);
  mat->AddElement(nist->FindOrBuildElement("O"), 2);
  auto* mpt = new G4MaterialPropertiesTable();
  mpt->AddProperty("RINDEX", kEnergies, Flat(Config::Get().Num("optics/pmt_window_refractive_index", 1.60)));
  mpt->AddProperty("ABSLENGTH", kEnergies, Flat(1e9 * cm));  // window transmission is folded into the QE
  mat->SetMaterialPropertiesTable(mpt);
  return mat;
}

G4Material* DetectorConstruction::StainlessSteel() {
  // opaque: optical behaviour is set by the surface (reflectivity from the config)
  static G4Material* mat = nullptr;
  if (!mat) mat = G4NistManager::Instance()->FindOrBuildMaterial("G4_STAINLESS-STEEL");
  return mat;
}

G4Material* DetectorConstruction::Ptfe() {
  // opaque (no RINDEX): optical behaviour via its surface (step 4); without a surface photons are absorbed
  static G4Material* mat = nullptr;
  if (!mat) mat = G4NistManager::Instance()->FindOrBuildMaterial("G4_TEFLON");
  return mat;
}

G4Material* DetectorConstruction::Absorber() {
  // no RINDEX: every optical photon that enters is stopped (used for the world and the PMT bodies)
  static G4Material* mat = nullptr;
  if (!mat) mat = G4NistManager::Instance()->FindOrBuildMaterial("G4_Galactic");
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

void DetectorConstruction::MakeReflector(G4LogicalVolume* lv, double reflectivity, double specular) {
  auto* surf = new G4OpticalSurface("Reflector_" + lv->GetName(), unified, ground, dielectric_metal, 0.);
  auto* mpt = new G4MaterialPropertiesTable();
  mpt->AddProperty("REFLECTIVITY", kEnergies, Flat(reflectivity));
  mpt->AddProperty("SPECULARSPIKECONSTANT", kEnergies, Flat(specular));
  mpt->AddProperty("SPECULARLOBECONSTANT", kEnergies, Flat(0.));
  mpt->AddProperty("BACKSCATTERCONSTANT", kEnergies, Flat(0.));
  surf->SetMaterialPropertiesTable(mpt);
  new G4LogicalSkinSurface("Skin_" + lv->GetName(), lv, surf);
}

void DetectorConstruction::ApplySurfaces() {
  const auto& c = Config::Get();
  if (c.Num("surfaces", 1) == 0) {
    G4cout << "optical surfaces off: PTFE and steel absorb" << G4endl;
    return;
  }
  const double rPtfe = c.Num("optics/ptfe_in_liquid/reflectivity", 0.95);
  const double fPtfe = c.Num("optics/ptfe_in_liquid/specular_fraction", 0.1);
  const double rSteel = c.Num("optics/stainless_steel_reflectivity", 0.35);
  int nBar = 0;
  for (auto* lv : *G4LogicalVolumeStore::GetInstance()) {
    const auto& n = lv->GetName();
    if (n == "PTFE") MakeReflector(lv, rPtfe, fPtfe);
    else if (n == "PTFE_gas")
      MakeReflector(lv, c.Num("optics/ptfe_in_gas/reflectivity", 0.75), c.Num("optics/ptfe_in_gas/specular_fraction", 0.15));
    else if (n == "MeshBar" || n == "MeshRing") {
      MakeReflector(lv, rSteel, 0.);  // steel: Lambertian
      nBar += n == "MeshBar";
    }
  }
  G4cout << "optical surfaces: PTFE R = " << rPtfe << " (specular " << fPtfe << "), steel R = " << rSteel
         << " Lambertian (" << nBar << " bar volumes + rings)" << G4endl;
}

G4VPhysicalVolume* DetectorConstruction::BuildTestSurface() {
  const auto& cfg = Config::Get();
  const std::string m = cfg.Str("test_surface_material", "ptfe");
  auto* worldS = new G4Box("World", 200. * mm, 200. * mm, 200. * mm);
  auto* worldL = new G4LogicalVolume(worldS, LiquidXenon(), "World");
  auto* worldP = new G4PVPlacement(nullptr, {}, worldL, "World", nullptr, false, 0, true);
  auto* slabL = new G4LogicalVolume(new G4Box("Slab", 150. * mm, 150. * mm, 5. * mm), m == "steel" ? StainlessSteel() : Ptfe(),
                                    "Slab");
  new G4PVPlacement(nullptr, G4ThreeVector(0, 0, -5. * mm), slabL, "Slab", worldL, false, 0, true);
  if (m == "steel") MakeReflector(slabL, cfg.Num("optics/stainless_steel_reflectivity", 0.35), 0.);
  else MakeReflector(slabL, cfg.Num("optics/ptfe_in_liquid/reflectivity", 0.95),
                     cfg.Num("optics/ptfe_in_liquid/specular_fraction", 0.1));
  return worldP;
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

G4VPhysicalVolume* DetectorConstruction::BuildTestInterface() {
  const double half = 200. * mm;
  auto* worldS = new G4Box("World", half, half, half);
  auto* worldL = new G4LogicalVolume(worldS, GasXenon(), "World");
  auto* worldP = new G4PVPlacement(nullptr, {}, worldL, "World", nullptr, false, 0, true);
  auto* liqS = new G4Box("Liquid", half, half, 0.5 * half);
  auto* liqL = new G4LogicalVolume(liqS, LiquidXenon(), "Liquid");
  new G4PVPlacement(nullptr, G4ThreeVector(0, 0, -0.5 * half), liqL, "Liquid", worldL, false, 0, true);
  return worldP;
}

G4VPhysicalVolume* DetectorConstruction::Construct() {
  const auto mode = Config::Get().Str("geometry_mode", "xams");
  if (mode == "test_box") return BuildTestBox();
  if (mode == "test_interface") return BuildTestInterface();
  if (mode == "test_mesh") return BuildTestMesh();
  if (mode == "test_surface") return BuildTestSurface();
  if (mode == "xams") {
    auto* w = BuildXams();
    ApplySurfaces();
    return w;
  }
  G4Exception("DetectorConstruction", "GEOM001", FatalException,
              ("geometry_mode '" + mode + "' not implemented yet (XAMS geometry: step 3)").c_str());
  return nullptr;
}
