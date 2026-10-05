// Model v1 of the XAMS TPC (geometry.yaml via config.json), and the single-mesh test geometry.
//
// Layout (z = 0 at the gate, z up): a liquid-xenon region below the liquid surface and a gas-xenon region above it,
// both inside an absorbing world (no refractive index: photons leaving the xenon are stopped). In them: five etched
// meshes as stainless-steel bars with their rings, the PTFE cylinder between the cathode ring and the gate ring
// (entirely in the liquid), two R12699 PMTs (silica window, photocathode behind it, absorbing body; the top one in
// four sectors I-IV) and the two SiPMs. Steel and PTFE get their optical surfaces in step 4; until then they absorb.
#include <G4Box.hh>
#include <G4Exception.hh>
#include <G4LogicalVolume.hh>
#include <G4PVPlacement.hh>
#include <G4SubtractionSolid.hh>
#include <G4SystemOfUnits.hh>
#include <G4Transform3D.hh>
#include <G4NistManager.hh>
#include <G4Tubs.hh>

#include <algorithm>
#include <cmath>
#include <map>
#include <vector>

#include "Config.hh"
#include "DetectorConstruction.hh"

namespace {
constexpr bool kCheck = true;  // overlap check at every placement

G4LogicalVolume* BarVolume(double length, double width, double thick, G4Material* steel) {
  // one logical volume per distinct bar length (rounded to 0.1 µm)
  static std::map<long, G4LogicalVolume*> cache;
  const long key = std::lround(length * 1e4);
  auto it = cache.find(key);
  if (it != cache.end()) return it->second;
  auto* s = new G4Box("Bar", 0.5 * length, 0.5 * width, 0.5 * thick);
  auto* lv = new G4LogicalVolume(s, steel, "MeshBar");
  cache[key] = lv;
  return lv;
}
}  // namespace

int DetectorConstruction::BuildMesh(G4LogicalVolume* mother, const std::string& name, double z, double angle_deg,
                                    double r_vis) {
  const auto& c = Config::Get();
  const double t = c.Num("mesh_common/foil_thickness_mm", 0.15) * mm;
  const double w = c.Num("mesh_common/bar_width_mm", 0.15) * mm;
  const double p = c.Num("mesh_common/pitch_mm", 2.60) * mm;

  // the layer: a thin disc of the surrounding medium that holds the bars (local axes = mesh axes)
  auto* layerS = new G4Tubs(name + "Layer", 0., r_vis, 0.5 * t, 0., 360. * deg);
  auto* layerL = new G4LogicalVolume(layerS, mother->GetMaterial(), name + "Layer");
  G4RotationMatrix rot;
  rot.rotateZ(angle_deg * deg);
  new G4PVPlacement(G4Transform3D(rot, G4ThreeVector(0, 0, z)), layerL, name + "Layer", mother, false, 0, kCheck);

  // bar centre lines at k p: two bars cross on the axis (gate drawing, posrec2_template.json: lattice phase +-0.5)
  std::vector<double> lines;
  for (int k = -200; k <= 200; ++k) {
    const double u = k * p;
    if (std::abs(u) + 0.5 * w < r_vis) lines.push_back(u);
  }
  int n = 0;
  // bars along x (full chords)
  std::vector<double> halfLen;
  for (double y : lines) {
    const double hl = std::sqrt(r_vis * r_vis - std::pow(std::abs(y) + 0.5 * w, 2)) - 1e-4 * mm;
    halfLen.push_back(hl);
    new G4PVPlacement(nullptr, G4ThreeVector(0, y, 0), BarVolume(2 * hl, w, t, StainlessSteel()), name + "Bar",
                      layerL, false, n++, false);
  }
  // bars along y: pieces between the x bars, clipped to the circle
  for (double x : lines) {
    const double cmax = std::sqrt(r_vis * r_vis - std::pow(std::abs(x) + 0.5 * w, 2)) - 1e-4 * mm;
    std::vector<std::pair<double, double>> blocked;
    for (size_t k = 0; k < lines.size(); ++k)
      if (halfLen[k] > std::abs(x) - 0.5 * w) blocked.push_back({lines[k] - 0.5 * w, lines[k] + 0.5 * w});
    double lo = -cmax;
    // BarVolume makes bars along its local x: rotate the y pieces by 90 degrees
    auto placeY = [&](double a, double b) {
      if (b - a <= 1e-3 * mm) return;
      G4RotationMatrix r90;
      r90.rotateZ(90. * deg);
      new G4PVPlacement(G4Transform3D(r90, G4ThreeVector(x, 0.5 * (a + b), 0)), BarVolume(b - a, w, t, StainlessSteel()),
                        name + "Bar", layerL, false, n++, false);
    };
    for (const auto& [b0, b1] : blocked) {
      if (b1 <= lo) continue;
      placeY(lo, std::min(b0, cmax));
      lo = std::max(lo, b1);
      if (lo >= cmax) break;
    }
    if (lo < cmax) placeY(lo, cmax);
  }
  return n;
}

void DetectorConstruction::BuildPmt(G4LogicalVolume* mother, G4VPhysicalVolume* motherP, const std::string& name,
                                    double window_z, bool facing_down, bool sectors) {
  const auto& c = Config::Get();
  const double outer = c.Num("pmt_common/outer_square_mm", 56.0) * mm;
  const double face = c.Num("pmt_common/window_face_square_mm", 54.6) * mm;
  const double cath = c.Num("pmt_common/photocathode_square_mm", 48.5) * mm;
  const double tw = c.Num("pmt_common/window_thickness_mm", 2.5) * mm;
  const double height = c.Num("pmt_common/height_mm", 14.8) * mm;
  const double qe = c.Num("pmt_common/qe_178nm", 0.33);
  const double tc = 0.1 * mm;  // photocathode layer
  const double s = facing_down ? +1. : -1.;  // direction from the window face into the PMT
  const double z0 = window_z;                 // mother-local z of the window's outer face

  // window
  auto* winS = new G4Box(name + "Window", 0.5 * face, 0.5 * face, 0.5 * tw);
  auto* winL = new G4LogicalVolume(winS, Silica(), name + "Window");
  auto* winP = new G4PVPlacement(nullptr, G4ThreeVector(0, 0, z0 + s * 0.5 * tw), winL, name + "Window", mother, false,
                                 0, kCheck);
  // photocathode(s) right behind the window
  const double zc = z0 + s * (tw + 0.5 * tc);
  if (sectors) {
    const double h = 0.25 * cath;  // sector centre offset (sector side = cath / 2)
    auto* secS = new G4Box(name + "Sector", 0.25 * cath, 0.25 * cath, 0.5 * tc);
    auto* secL = new G4LogicalVolume(secS, Photocathode(), name + "Sector");
    // sectors I (-x, +y), II (+x, +y), III (-x, -y), IV (+x, -y) = copy numbers 1-4 = channels ch1-ch4
    const double xs[4] = {-h, +h, -h, +h}, ys[4] = {+h, +h, -h, -h};
    for (int i = 0; i < 4; ++i) {
      auto* secP = new G4PVPlacement(nullptr, G4ThreeVector(xs[i], ys[i], zc), secL, name + "Sector", mother, false,
                                     i + 1, kCheck);
      MakeSensor(secL, winP, secP, qe);
    }
  } else {
    auto* cS = new G4Box(name + "Cathode", 0.5 * cath, 0.5 * cath, 0.5 * tc);
    auto* cL = new G4LogicalVolume(cS, Photocathode(), name + "Cathode");
    auto* cP = new G4PVPlacement(nullptr, G4ThreeVector(0, 0, zc), cL, name + "Cathode", mother, false, 0, kCheck);
    MakeSensor(cL, winP, cP, qe);
  }
  // absorbing body: a frame around the window + cathode layer, and the rest of the PMT behind it
  const double tf = tw + tc;
  auto* frameS = new G4SubtractionSolid(name + "Frame", new G4Box("fo", 0.5 * outer, 0.5 * outer, 0.5 * tf),
                                        new G4Box("fi", 0.5 * face, 0.5 * face, 0.5 * tf + 1 * mm));
  auto* frameL = new G4LogicalVolume(frameS, Absorber(), name + "Frame");
  new G4PVPlacement(nullptr, G4ThreeVector(0, 0, z0 + s * 0.5 * tf), frameL, name + "Frame", mother, false, 0, kCheck);
  const double tb = height - tf;
  auto* bodyS = new G4Box(name + "Body", 0.5 * outer, 0.5 * outer, 0.5 * tb);
  auto* bodyL = new G4LogicalVolume(bodyS, Absorber(), name + "Body");
  new G4PVPlacement(nullptr, G4ThreeVector(0, 0, z0 + s * (tf + 0.5 * tb)), bodyL, name + "Body", mother, false, 0,
                    kCheck);
  (void)motherP;
}

G4VPhysicalVolume* DetectorConstruction::BuildTestMesh() {
  auto* worldS = new G4Box("World", 100. * mm, 100. * mm, 100. * mm);
  auto* worldL = new G4LogicalVolume(worldS, LiquidXenon(), "World");
  auto* worldP = new G4PVPlacement(nullptr, {}, worldL, "World", nullptr, false, 0, true);
  const int n = BuildMesh(worldL, "TestMesh", 0., 0., 32. * mm);
  G4cout << "test mesh: " << n << " bar pieces" << G4endl;
  return worldP;
}

G4VPhysicalVolume* DetectorConstruction::BuildXams() {
  const auto& c = Config::Get();
  const auto& j = c.J();
  const double zl = c.Num("liquid/surface_z_mm", 4.0) * mm;
  const double rRingIn = 0.5 * c.Num("mesh_common/ring/inner_diameter_mm", 64.0) * mm;
  const double rRingOut = 0.5 * c.Num("mesh_common/ring/outer_diameter_mm", 92.6) * mm;
  const double ringHalf = 0.5 * c.Num("mesh_common/ring/thickness_mm", 1.8) * mm;

  // world (absorbing) and the two xenon regions
  const double halfXY = 60. * mm, zLo = -90. * mm, zHi = 45. * mm;
  auto* worldS = new G4Box("World", 100. * mm, 100. * mm, 120. * mm);
  auto* worldL = new G4LogicalVolume(worldS, Absorber(), "World");
  auto* worldP = new G4PVPlacement(nullptr, {}, worldL, "World", nullptr, false, 0, kCheck);

  const double liqC = 0.5 * (zLo + zl), liqH = 0.5 * (zl - zLo);
  auto* liqL = new G4LogicalVolume(new G4Box("Liquid", halfXY, halfXY, liqH), LiquidXenon(), "Liquid");
  auto* liqP = new G4PVPlacement(nullptr, G4ThreeVector(0, 0, liqC), liqL, "Liquid", worldL, false, 0, kCheck);
  const double gasC = 0.5 * (zl + zHi), gasH = 0.5 * (zHi - zl);
  auto* gasL = new G4LogicalVolume(new G4Box("Gas", halfXY, halfXY, gasH), GasXenon(), "Gas");
  auto* gasP = new G4PVPlacement(nullptr, G4ThreeVector(0, 0, gasC), gasL, "Gas", worldL, false, 0, kCheck);

  auto region = [&](double z) { return z < zl ? std::make_pair(liqL, liqC) : std::make_pair(gasL, gasC); };

  // mesh assemblies (drawing "XAMS_XAMS grid assy.pdf"): foil mid-plane at the mesh z; inside the ring bore the foil is
  // the etched mesh (bar layer), from the bore to the foil edge it lies on the ring face (foil rim); the ring body
  // (assembly thickness minus foil) is on the other side of the foil ("foil_side" up: body below, down: body above)
  const double tFoil = c.Num("mesh_common/foil_thickness_mm", 0.15) * mm;
  const double rFoil = 0.5 * c.Num("mesh_common/foil_diameter_mm", 80.0) * mm;
  const double bodyT = 2 * ringHalf - tFoil;
  auto* bodyL = new G4LogicalVolume(new G4Tubs("MeshRingBody", rRingIn, rRingOut, 0.5 * bodyT, 0., 360. * deg),
                                    StainlessSteel(), "MeshRing");
  auto* rimL = new G4LogicalVolume(new G4Tubs("MeshFoilRim", rRingIn, rFoil, 0.5 * tFoil, 0., 360. * deg),
                                   StainlessSteel(), "MeshRing");
  double zGate = 0., zCath = -51.8 * mm;
  for (const auto& m : j["meshes"]) {
    const std::string name = m["name"].get<std::string>();
    const double z = m["z_mm"].get<double>() * mm;
    const double ang = m.value("angle_to_anodes_deg", 0.0);
    const std::string side = m.value("foil_side", std::string("up"));
    const double zBody = z + (side == "up" ? -1. : 1.) * 0.5 * (tFoil + bodyT);
    const double lo = std::min(z - 0.5 * tFoil, zBody - 0.5 * bodyT), hi = std::max(z + 0.5 * tFoil, zBody + 0.5 * bodyT);
    if (lo < zl + 0.01 * mm && hi > zl - 0.01 * mm)
      G4Exception("BuildXams", "GEOM010", FatalException, ("mesh assembly " + name + " crosses the liquid surface").c_str());
    auto [mL, mC] = region(z);
    const int nb = BuildMesh(mL, name, z - mC, ang, rRingIn);
    new G4PVPlacement(nullptr, G4ThreeVector(0, 0, z - mC), rimL, name + "Rim", mL, false, 0, kCheck);
    new G4PVPlacement(nullptr, G4ThreeVector(0, 0, zBody - mC), bodyL, name + "Ring", mL, false, 0, kCheck);
    G4cout << "mesh " << name << " at z = " << z / mm << " mm (" << (z < zl ? "liquid" : "gas") << "), foil " << side
           << ", ring body " << (zBody - 0.5 * bodyT) / mm << " to " << (zBody + 0.5 * bodyT) / mm << " mm, " << nb
           << " bar pieces, " << ang << " deg" << G4endl;
    if (name == "gate") zGate = z;
    if (name == "cathode") zCath = z;
  }

  // PTFE cylinder (drawing "PTFE_cylinder.pdf"): in the bores of the gate and cathode rings, from z_top down over its
  // length (all in the liquid)
  const double rIn = 0.5 * c.Num("ptfe_cylinder/inner_diameter_mm", 62.0) * mm;
  const double wall = c.Num("ptfe_cylinder/wall_thickness_mm", 5.0) * mm;
  const double zt = c.Num("ptfe_cylinder/z_top_mm", -0.075) * mm;
  const double zb = zt - c.Num("ptfe_cylinder/length_mm", 50.85) * mm;
  if (zt > zGate - 0.5 * tFoil + 1e-6 * mm || zb < zCath + 0.5 * tFoil - 1e-6 * mm)
    G4Exception("BuildXams", "GEOM011", FatalException, "PTFE cylinder does not fit between the gate and cathode foils");
  auto* ptfeL = new G4LogicalVolume(new G4Tubs("PTFE", rIn, rIn + wall, 0.5 * (zt - zb), 0., 360. * deg), Ptfe(),
                                    "PTFE");
  new G4PVPlacement(nullptr, G4ThreeVector(0, 0, 0.5 * (zt + zb) - liqC), ptfeL, "PTFE", liqL, false, 0, kCheck);
  G4cout << "PTFE cylinder r = " << rIn / mm << "-" << (rIn + wall) / mm << " mm, z = " << zb / mm << " to "
         << zt / mm << " mm (gap to the cathode foil " << (zb - zCath - 0.5 * tFoil) / mm << " mm)" << G4endl;

  // copper field-shaping rings (drawing "XAMS_field_shaper.pdf"), around the PTFE cylinder
  if (j.contains("field_shaping_rings")) {
    const auto& f = j["field_shaping_rings"];
    const double fi = 0.5 * f["inner_diameter_mm"].get<double>() * mm, fo = 0.5 * f["outer_diameter_mm"].get<double>() * mm;
    const double ft = f["thickness_mm"].get<double>() * mm;
    auto* cuL = new G4LogicalVolume(new G4Tubs("CopperRing", fi, fo, 0.5 * ft, 0., 360. * deg),
                                    G4NistManager::Instance()->FindOrBuildMaterial("G4_Cu"), "CopperRing");
    int k = 0;
    for (const auto& zc : f["z_center_mm"]) {
      const double z = zc.get<double>() * mm;
      new G4PVPlacement(nullptr, G4ThreeVector(0, 0, z - liqC), cuL, "CopperRing", liqL, false, k++, kCheck);
      G4cout << "copper field-shaping ring " << k << ": z " << (z - 0.5 * ft) / mm << " to " << (z + 0.5 * ft) / mm
             << " mm, r " << fi / mm << "-" << fo / mm << " mm" << G4endl;
    }
  }

  // optional extra PTFE cylinders (design study; config "extra_ptfe": [{"name", "z_bottom_mm", "z_top_mm"}], same radii
  // as the main cylinder), split at the liquid surface: liquid part "PTFE", gas part "PTFE_gas"
  if (j.contains("extra_ptfe")) {
    for (const auto& x : j["extra_ptfe"]) {
      const std::string nm = x["name"].get<std::string>();
      const double b = x["z_bottom_mm"].get<double>() * mm, t = x["z_top_mm"].get<double>() * mm;
      const std::vector<std::pair<double, double>> parts = {{b, std::min(t, zl)}, {std::max(b, zl), t}};
      for (size_t k = 0; k < 2; ++k) {
        const auto [lo, hi] = parts[k];
        if (hi - lo < 0.01 * mm) continue;
        const bool gas = k == 1;
        const std::string ln = gas ? "PTFE_gas" : "PTFE";
        auto* l = new G4LogicalVolume(new G4Tubs(nm + (gas ? "_gas" : "_liq"), rIn, rIn + wall, 0.5 * (hi - lo), 0.,
                                                 360. * deg), Ptfe(), ln);
        new G4PVPlacement(nullptr, G4ThreeVector(0, 0, 0.5 * (hi + lo) - (gas ? gasC : liqC)), l, ln, gas ? gasL : liqL,
                          false, 0, kCheck);
        G4cout << "extra PTFE " << nm << (gas ? " (gas)" : " (liquid)") << ": z " << lo / mm << " to " << hi / mm << " mm"
               << G4endl;
      }
    }
  }

  // PMTs
  for (const auto& pm : j["pmts"]) {
    const std::string name = pm["name"].get<std::string>();
    const double wz = pm["window_z_mm"].get<double>() * mm;
    const bool top = name == "top";
    auto [mL, mC] = region(wz);
    BuildPmt(mL, top ? gasP : liqP, top ? "TopPMT" : "BottomPMT", wz - mC, top, top);
  }

  // SiPMs on the inside of the PTFE cylinder, looking inward (sensor ids 6, 7)
  if (j.contains("sipms") && j["sipms"].contains("azimuth_deg")) {
    const auto& sp = j["sipms"];
    const double a = sp["active_mm"][0].get<double>() * mm;
    auto* sS = new G4Box("SiPM", 0.5 * a, 0.5 * a, 0.05 * mm);
    auto* sL = new G4LogicalVolume(sS, Photocathode(), "SiPM");
    for (size_t i = 0; i < sp["azimuth_deg"].size(); ++i) {
      const double phi = sp["azimuth_deg"][i].get<double>() * deg;
      const double z = sp["z_mm"][i].get<double>() * mm;
      const double r = rIn - 0.15 * mm;
      G4RotationMatrix rot;
      rot.rotateY(90. * deg);  // thin axis (local z) -> radial
      rot.rotateZ(phi);
      auto* sP = new G4PVPlacement(G4Transform3D(rot, G4ThreeVector(r * std::cos(phi), r * std::sin(phi), z - liqC)),
                                   sL, "SiPM", liqL, false, 6 + static_cast<int>(i), kCheck);
      MakeSensor(sL, liqP, sP, c.Num("sipms/pde", 1.0));
    }
  }
  return worldP;
}
