// Model v1 of the XAMS TPC (geometry.yaml via config.json), and the single-mesh test geometry.
//
// Layout (z = 0 at the gate, z up): a liquid-xenon region below the liquid surface and a gas-xenon region above it,
// both inside an absorbing world (no refractive index: photons leaving the xenon are stopped); since geometry v4 the
// liquid fills a PTFE bucket up to its weir and the gas fills a closed stainless-steel vessel around it. In them: five etched
// meshes as stainless-steel bars with their rings, the PTFE cylinder between the cathode ring and the gate ring
// (entirely in the liquid), two R12699 PMTs (silica window, photocathode behind it, absorbing body; the top one in
// four sectors I-IV) and the two SiPMs. Steel and PTFE get their optical surfaces in step 4; until then they absorb.
#include <G4Box.hh>
#include <G4Exception.hh>
#include <G4LogicalVolume.hh>
#include <G4IntersectionSolid.hh>
#include <G4PVPlacement.hh>
#include <G4SubtractionSolid.hh>
#include <G4SystemOfUnits.hh>
#include <G4Transform3D.hh>
#include <G4NistManager.hh>
#include <G4Orb.hh>
#include <G4Tubs.hh>

#include <algorithm>
#include <cmath>
#include <map>
#include <set>
#include <vector>

#include "Config.hh"
#include "DetectorConstruction.hh"

namespace {
constexpr bool kCheck = true;  // overlap check at every placement

}  // namespace

int DetectorConstruction::BuildMesh(G4LogicalVolume* mother, const std::string& name, double z, double angle_deg,
                                    double r_vis) {
  // drawing "XAMS_XAMS grid.pdf": a steel foil (thickness t) with square holes etched only at the cells of the hole
  // pattern (config mesh_common/holes: (i, j) -> centre ((i + 1/2) p, (j + 1/2) p) in the mesh frame; two bars cross
  // on the axis); the rest of the foil is solid. Built from steel pieces in a thin disc of the surrounding medium
  // (radius r_vis): the bars (x bars as full chords, y bars in pieces between them) and a solid square in every cell
  // that is not etched (clipped at r_vis). The holes are then real openings (also in the viewer).
  // Without a hole list (test geometries) every cell fully inside r_vis is a hole.
  const auto& c = Config::Get();
  const double t = c.Req("mesh_common/foil_thickness_mm") * mm;
  const double w = c.Req("mesh_common/bar_width_mm") * mm;
  const double p = c.Req("mesh_common/pitch_mm") * mm;
  const double h = p - w;  // hole / cell side
  const double eps = 1e-4 * mm;

  auto* layerL = new G4LogicalVolume(new G4Tubs(name + "Layer", 0., r_vis, 0.5 * t, 0., 360. * deg),
                                     mother->GetMaterial(), name + "Layer");
  G4RotationMatrix rot;
  rot.rotateZ(angle_deg * deg);
  // physical name "<mesh>Hole": a photon inside the layer but not in steel is in an (etched) opening
  new G4PVPlacement(G4Transform3D(rot, G4ThreeVector(0, 0, z)), layerL, name + "Hole", mother, false, 0, kCheck);

  std::set<std::pair<int, int>> holes;
  const auto& j = c.J();
  const bool haveList = j.contains("mesh_common") && j["mesh_common"].contains("holes");
  if (haveList)
    for (const auto& ij : j["mesh_common"]["holes"]) holes.insert({ij[0].get<int>(), ij[1].get<int>()});

  auto steelLV = [&](G4VSolid* s) { return new G4LogicalVolume(s, StainlessSteel(), "MeshFoil"); };
  static std::map<long, G4LogicalVolume*> barCache;  // one volume per distinct bar length
  auto barLV = [&](double len) {
    const long key = std::lround(len * 1e4);
    if (!barCache.count(key)) barCache[key] = steelLV(new G4Box("MeshBarS", 0.5 * len, 0.5 * w, 0.5 * t));
    return barCache[key];
  };

  // bar centre lines at k p
  std::vector<double> lines;
  for (int k = -200; k <= 200; ++k)
    if (std::abs(k * p) + 0.5 * w < r_vis) lines.push_back(k * p);
  int nPieces = 0;
  std::vector<double> halfLen;
  for (double y : lines) {  // bars along x (full chords)
    const double hl = std::sqrt(r_vis * r_vis - std::pow(std::abs(y) + 0.5 * w, 2)) - eps;
    halfLen.push_back(hl);
    new G4PVPlacement(nullptr, G4ThreeVector(0, y, 0), barLV(2 * hl), name + "Foil", layerL, false, nPieces++, false);
  }
  G4RotationMatrix r90;
  r90.rotateZ(90. * deg);
  for (double x : lines) {  // bars along y: pieces between the x bars, clipped to the circle
    const double cmax = std::sqrt(r_vis * r_vis - std::pow(std::abs(x) + 0.5 * w, 2)) - eps;
    double lo = -cmax;
    auto placeY = [&](double a, double b) {
      if (b - a <= 1e-3 * mm) return;
      new G4PVPlacement(G4Transform3D(r90, G4ThreeVector(x, 0.5 * (a + b), 0)), barLV(b - a), name + "Foil", layerL,
                        false, nPieces++, false);
    };
    for (size_t k = 0; k < lines.size(); ++k) {
      if (halfLen[k] <= std::abs(x) - 0.5 * w) continue;
      const double b0 = lines[k] - 0.5 * w, b1 = lines[k] + 0.5 * w;
      if (b1 <= lo) continue;
      placeY(lo, std::min(b0, cmax));
      lo = std::max(lo, b1);
      if (lo >= cmax) break;
    }
    if (lo < cmax) placeY(lo, cmax);
  }

  // cells: etched (open) or solid fill
  static G4LogicalVolume* fullCell = nullptr;
  if (!fullCell) fullCell = steelLV(new G4Box("MeshCellS", 0.5 * h, 0.5 * h, 0.5 * t));
  auto* disc = new G4Tubs(name + "CellClip", 0., r_vis - eps, t, 0., 360. * deg);
  const int nc = static_cast<int>(r_vis / p) + 1;
  int nHoles = 0;
  for (int a = -nc - 1; a <= nc; ++a) {
    for (int b = -nc - 1; b <= nc; ++b) {
      const double cx = (a + 0.5) * p, cy = (b + 0.5) * p;
      const double rFar = std::hypot(std::abs(cx) + 0.5 * h, std::abs(cy) + 0.5 * h);
      const double rNear = std::hypot(std::max(std::abs(cx) - 0.5 * h, 0.), std::max(std::abs(cy) - 0.5 * h, 0.));
      if (rNear >= r_vis - eps) continue;  // cell outside the disc
      const bool open = haveList ? holes.count({a, b}) > 0 : rFar < r_vis;
      if (open) {
        if (rFar >= r_vis)
          G4Exception("BuildMesh", "GEOM020", FatalException, ("etched hole outside the foil disc of " + name).c_str());
        ++nHoles;
        continue;
      }
      G4LogicalVolume* lv = fullCell;
      if (rFar >= r_vis - eps)
        lv = steelLV(new G4IntersectionSolid("MeshCellClipped", new G4Box("MeshCellB", 0.5 * h, 0.5 * h, 0.5 * t), disc,
                                             nullptr, G4ThreeVector(-cx, -cy, 0)));
      new G4PVPlacement(nullptr, G4ThreeVector(cx, cy, 0), lv, name + "Foil", layerL, false, nPieces++, false);
    }
  }
  if (haveList && nHoles != static_cast<int>(holes.size()))
    G4Exception("BuildMesh", "GEOM021", FatalException, ("not all listed holes placed in " + name).c_str());
  return nHoles;
}

void DetectorConstruction::BuildPmt(G4LogicalVolume* mother, G4VPhysicalVolume* motherP, const std::string& name,
                                    double window_z, bool facing_down, bool sectors) {
  const auto& c = Config::Get();
  const double outer = c.Req("pmt_common/outer_square_mm") * mm;
  const double face = c.Req("pmt_common/window_face_square_mm") * mm;
  const double cath = c.Req("pmt_common/photocathode_square_mm") * mm;
  const double tw = c.Req("pmt_common/window_thickness_mm") * mm;
  const double height = c.Req("pmt_common/height_mm") * mm;
  const double qe = c.Req("pmt_common/qe_178nm");
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
    // optional insensitive cross between the four sectors (config pmt_common.top_dead_cross_mm, strip width w):
    // sector side (cath - w) / 2; the strips absorb (photons reaching them are lost)
    const double w = c.Num("pmt_common/top_dead_cross_mm", 0.0) * mm;
    const double a = 0.5 * (cath - w);
    const double h = 0.5 * w + 0.5 * a;  // sector centre offset
    if (w > 0) {
      auto* xL = new G4LogicalVolume(new G4Box(name + "DeadCrossX", 0.5 * cath, 0.5 * w, 0.5 * tc), DeadCrossMaterial(),
                                     name + "DeadCross");
      new G4PVPlacement(nullptr, G4ThreeVector(0, 0, zc), xL, name + "DeadCross", mother, false, 0, kCheck);
      auto* yL = new G4LogicalVolume(new G4Box(name + "DeadCrossY", 0.5 * w, 0.5 * a, 0.5 * tc), DeadCrossMaterial(),
                                     name + "DeadCross");
      for (int k = 0; k < 2; ++k)
        new G4PVPlacement(nullptr, G4ThreeVector(0, (k ? -1. : 1.) * h, zc), yL, name + "DeadCross", mother, false, k + 1,
                          kCheck);
      G4cout << name << ": insensitive cross " << w / mm << " mm between the sectors" << G4endl;
    }
    auto* secS = new G4Box(name + "Sector", 0.5 * a, 0.5 * a, 0.5 * tc);
    auto* secL = new G4LogicalVolume(secS, Photocathode(), name + "Sector");
    // sectors I-IV = copy numbers 1-4 = channels ch1-ch4, at the quadrants of config pmts[top].sector_quadrant
    // (data frame: I (+x, +y), II (-x, +y), III (+x, -y), IV (-x, -y))
    const nlohmann::json* quad = nullptr;
    for (const auto& pm : c.J()["pmts"])
      if (pm.value("name", "") == "top" && pm.contains("sector_quadrant")) quad = &pm["sector_quadrant"];
    if (!quad)
      G4Exception("BuildPmt", "GEOM050", FatalException, "pmts[top].sector_quadrant missing in the config");
    double xs[4], ys[4];
    const char* sec[4] = {"I", "II", "III", "IV"};
    for (int i = 0; i < 4; ++i) {
      xs[i] = (*quad)[sec[i]][0].get<double>() * h;
      ys[i] = (*quad)[sec[i]][1].get<double>() * h;
    }
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
  auto* frameL = new G4LogicalVolume(frameS, PmtBodyMaterial(), name + "Frame");
  new G4PVPlacement(nullptr, G4ThreeVector(0, 0, z0 + s * 0.5 * tf), frameL, name + "Frame", mother, false, 0, kCheck);
  const double tb = height - tf;
  auto* bodyS = new G4Box(name + "Body", 0.5 * outer, 0.5 * outer, 0.5 * tb);
  auto* bodyL = new G4LogicalVolume(bodyS, PmtBodyMaterial(), name + "Body");
  new G4PVPlacement(nullptr, G4ThreeVector(0, 0, z0 + s * (tf + 0.5 * tb)), bodyL, name + "Body", mother, false, 0,
                    kCheck);
  (void)motherP;
}

G4VPhysicalVolume* DetectorConstruction::BuildTestMesh() {
  auto* worldS = new G4Box("World", 100. * mm, 100. * mm, 100. * mm);
  auto* worldL = new G4LogicalVolume(worldS, LiquidXenon(), "World");
  auto* worldP = new G4PVPlacement(nullptr, {}, worldL, "World", nullptr, false, 0, true);
  const int n = BuildMesh(worldL, "TestMesh", 0., 0., 36. * mm);
  G4cout << "test mesh: " << n << " holes" << G4endl;
  return worldP;
}

G4VPhysicalVolume* DetectorConstruction::BuildXams() {
  const auto& c = Config::Get();
  const auto& j = c.J();
  const double zl = c.Req("liquid/surface_z_mm") * mm;
  const double rRingIn = 0.5 * c.Req("mesh_common/ring/inner_diameter_mm") * mm;
  const double rRingOut = 0.5 * c.Req("mesh_common/ring/outer_diameter_mm") * mm;
  const double ringHalf = 0.5 * c.Req("mesh_common/ring/thickness_mm") * mm;

  // world (absorbing) and the two xenon regions
  // world half sizes: config world_half_mm (default 160 x 160 x 260 mm: both cryostat vessels; particle mode: larger
  // if the source needs it)
  const double wx = c.Num("world_half_mm/0", 160.) * mm, wy = c.Num("world_half_mm/1", 160.) * mm,
               wz = c.Num("world_half_mm/2", 260.) * mm;
  // envelopes of the vessels (for the source capsule): inner vessel, outer vessel and its vacuum
  double vesselTop = 0., vesselBot = 0., vesselR = 0., outerTop = 0., outerBot = 0., outerR = 0.;
  double tubeR = 0., tubeTop = 0., tubeBot = 0., ringT = 0.;  // inner vessel: tube outer radius / ends, flange ring
  double oTubeR = 0., oTubeTop = 0., oTubeBot = 0., oRingT = 0.;  // the same for the outer vessel
  double vacuumR = -1., vacuumC = 0., vacuumHalf = 0.;
  G4LogicalVolume* vacuumL = nullptr;
  auto* worldS = new G4Box("World", wx, wy, wz);
  auto* worldL = new G4LogicalVolume(worldS, Absorber(), "World");
  auto* worldP = new G4PVPlacement(nullptr, {}, worldL, "World", nullptr, false, 0, kCheck);

  G4LogicalVolume *liqL, *gasL;
  G4VPhysicalVolume *liqP, *gasP;
  double liqC, gasC;
  if (j.contains("ptfe_bucket") && j.contains("cryostat_vessel")) {
    // surroundings (drawings "PTFE_bucket.pdf", "Inner_cryostat_vessel.pdf"): a closed steel vessel filled with gas
    // ("Gas"); in it the PTFE bucket ("Bucket"), whose weir sets the liquid level (rim = surface + weir depth), filled
    // with liquid up to the surface ("Liquid", a daughter of "Gas" inside the bucket cavity)
    const auto& b = j["ptfe_bucket"];
    const auto& v = j["cryostat_vessel"];
    const double bIn = 0.5 * b["inner_diameter_mm"].get<double>() * mm, bOut = 0.5 * b["outer_diameter_mm"].get<double>() * mm;
    const double bH = b["height_mm"].get<double>() * mm, bBot = b["bottom_thickness_mm"].get<double>() * mm;
    const double zRim = zl + b["weir_below_rim_mm"].get<double>() * mm, zBucket = zRim - bH;
    // inner vessel (gas): tube + at each end a flange ring around the tube and a blind flange closing it
    // (XAMS_cryostat.pdf, simplified); centred on cryostat_vessel/center_z_mm (XAMS in the middle of the vessel)
    const double vIn = 0.5 * v["inner_diameter_mm"].get<double>() * mm, vOut = 0.5 * v["outer_diameter_mm"].get<double>() * mm;
    const double vH = v["height_mm"].get<double>() * mm;  // gas cavity between the blind flanges
    const double vF = 0.5 * c.Req("cryostat_vessel/flange/outer_diameter_mm") * mm;
    const double vR = c.Req("cryostat_vessel/flange/ring_thickness_mm") * mm;
    const double vB = c.Req("cryostat_vessel/flange/blind_thickness_mm") * mm;
    const double vC = c.Req("cryostat_vessel/center_z_mm") * mm;
    if (zBucket < vC - 0.5 * vH || zRim > vC + 0.5 * vH)
      G4Exception("BuildXams", "GEOM031", FatalException, "the PTFE bucket does not fit in the inner vessel");
    vesselTop = vC + 0.5 * vH + vB;
    vesselBot = vC - 0.5 * vH - vB;
    vesselR = vF;
    tubeR = vOut;
    tubeTop = vC + 0.5 * vH;
    tubeBot = vC - 0.5 * vH;
    ringT = vR;

    // outer vessel (vacuum inside), placed around the inner one with cryostat_outer/inner_vessel_offset_mm; the inner
    // vessel is then a daughter of the vacuum, otherwise of the world
    G4LogicalVolume* vesMother = worldL;
    double mz = 0.;
    if (j.contains("cryostat_outer")) {
      const auto& o = j["cryostat_outer"];
      const double oIn = 0.5 * o["inner_diameter_mm"].get<double>() * mm, oOut = 0.5 * o["outer_diameter_mm"].get<double>() * mm;
      const double oH = o["height_mm"].get<double>() * mm;
      const double oF = 0.5 * c.Req("cryostat_outer/flange/outer_diameter_mm") * mm;
      const double oR = c.Req("cryostat_outer/flange/ring_thickness_mm") * mm;
      const double oB = c.Req("cryostat_outer/flange/blind_thickness_mm") * mm;
      const double oC = vC - c.Req("cryostat_outer/inner_vessel_offset_mm") * mm;
      if (oF > wx || oF > wy || oC + 0.5 * oH + oB > wz || oC - 0.5 * oH - oB < -wz)
        G4Exception("BuildXams", "GEOM032", FatalException, "the outer vessel does not fit in the world (world_half_mm)");
      if (vF > oIn || vesselTop > oC + 0.5 * oH || vesselBot < oC - 0.5 * oH)
        G4Exception("BuildXams", "GEOM033", FatalException, "the inner vessel does not fit in the outer vessel");
      auto* oTubeL = new G4LogicalVolume(new G4Tubs("OuterVessel", oIn, oOut, 0.5 * oH, 0., 360. * deg), StainlessSteel(), "OuterVessel");
      new G4PVPlacement(nullptr, G4ThreeVector(0, 0, oC), oTubeL, "OuterVessel", worldL, false, 0, kCheck);
      auto* oRingL = new G4LogicalVolume(new G4Tubs("OuterFlangeRing", oOut, oF, 0.5 * oR, 0., 360. * deg), StainlessSteel(), "OuterFlange");
      auto* oBlindL = new G4LogicalVolume(new G4Tubs("OuterFlangeBlind", 0., oF, 0.5 * oB, 0., 360. * deg), StainlessSteel(), "OuterFlange");
      for (int k = 0; k < 2; ++k) {
        const double sgn = k ? -1. : 1.;
        new G4PVPlacement(nullptr, G4ThreeVector(0, 0, oC + sgn * (0.5 * oH - 0.5 * oR)), oRingL, "OuterFlange", worldL, false, k, kCheck);
        new G4PVPlacement(nullptr, G4ThreeVector(0, 0, oC + sgn * (0.5 * oH + 0.5 * oB)), oBlindL, "OuterFlange", worldL, false, 2 + k, kCheck);
      }
      vacuumL = new G4LogicalVolume(new G4Tubs("Vacuum", 0., oIn, 0.5 * oH, 0., 360. * deg), Absorber(), "Vacuum");
      new G4PVPlacement(nullptr, G4ThreeVector(0, 0, oC), vacuumL, "Vacuum", worldL, false, 0, kCheck);
      vacuumR = oIn;
      vacuumC = oC;
      vacuumHalf = 0.5 * oH;
      outerR = oF;
      outerTop = oC + 0.5 * oH + oB;
      outerBot = oC - 0.5 * oH - oB;
      oTubeR = oOut;
      oTubeTop = oC + 0.5 * oH;
      oTubeBot = oC - 0.5 * oH;
      oRingT = oR;
      vesMother = vacuumL;
      mz = oC;
      G4cout << "outer vessel r " << oIn / mm << "-" << oOut / mm << " mm (flanges r " << oF / mm << "), z " << outerBot / mm
             << " to " << outerTop / mm << " mm, vacuum inside" << G4endl;
    }
    auto* vesselL = new G4LogicalVolume(new G4Tubs("Vessel", vIn, vOut, 0.5 * vH, 0., 360. * deg), StainlessSteel(), "Vessel");
    new G4PVPlacement(nullptr, G4ThreeVector(0, 0, vC - mz), vesselL, "Vessel", vesMother, false, 0, kCheck);
    auto* vRingL = new G4LogicalVolume(new G4Tubs("VesselFlangeRing", vOut, vF, 0.5 * vR, 0., 360. * deg), StainlessSteel(), "VesselFlange");
    auto* vBlindL = new G4LogicalVolume(new G4Tubs("VesselFlangeBlind", 0., vF, 0.5 * vB, 0., 360. * deg), StainlessSteel(), "VesselFlange");
    for (int k = 0; k < 2; ++k) {
      const double sgn = k ? -1. : 1.;
      new G4PVPlacement(nullptr, G4ThreeVector(0, 0, vC - mz + sgn * (0.5 * vH - 0.5 * vR)), vRingL, "VesselFlange", vesMother, false, k, kCheck);
      new G4PVPlacement(nullptr, G4ThreeVector(0, 0, vC - mz + sgn * (0.5 * vH + 0.5 * vB)), vBlindL, "VesselFlange", vesMother, false, 2 + k, kCheck);
    }
    gasC = vC;
    gasL = new G4LogicalVolume(new G4Tubs("Gas", 0., vIn, 0.5 * vH, 0., 360. * deg), GasXenon(), "Gas");
    gasP = new G4PVPlacement(nullptr, G4ThreeVector(0, 0, gasC - mz), gasL, "Gas", vesMother, false, 0, kCheck);

    const double bC = zBucket + 0.5 * bH;
    auto* bucketS = new G4SubtractionSolid("Bucket", new G4Tubs("BucketO", 0., bOut, 0.5 * bH, 0., 360. * deg),
                                           new G4Tubs("BucketI", 0., bIn, 0.5 * (bH - bBot) + 1. * mm, 0., 360. * deg),
                                           nullptr, G4ThreeVector(0, 0, 0.5 * bBot + 1. * mm));
    auto* bucketL = new G4LogicalVolume(bucketS, Ptfe(), "Bucket");
    new G4PVPlacement(nullptr, G4ThreeVector(0, 0, bC - gasC), bucketL, "Bucket", gasL, false, 0, kCheck);

    const double zLo = zBucket + bBot;
    liqC = 0.5 * (zLo + zl);
    liqL = new G4LogicalVolume(new G4Tubs("Liquid", 0., bIn, 0.5 * (zl - zLo), 0., 360. * deg), LiquidXenon(), "Liquid");
    liqP = new G4PVPlacement(nullptr, G4ThreeVector(0, 0, liqC - gasC), liqL, "Liquid", gasL, false, 0, kCheck);
    G4cout << "PTFE bucket r " << bIn / mm << "-" << bOut / mm << " mm, z " << zBucket / mm << " to " << zRim / mm
           << " mm (rim " << (zRim - zl) / mm << " mm above the liquid), liquid from z " << zLo / mm
           << " mm; inner vessel r " << vIn / mm << "-" << vOut / mm << " mm (flanges r " << vF / mm << "), z "
           << vesselBot / mm << " to " << vesselTop / mm << " mm, gas cavity centre z " << vC / mm << " mm" << G4endl;
  } else {
    // geometry v1-v3: liquid and gas boxes in the absorbing world
    const double halfXY = 60. * mm, zLo = -90. * mm, zHi = 45. * mm;
    liqC = 0.5 * (zLo + zl);
    liqL = new G4LogicalVolume(new G4Box("Liquid", halfXY, halfXY, 0.5 * (zl - zLo)), LiquidXenon(), "Liquid");
    liqP = new G4PVPlacement(nullptr, G4ThreeVector(0, 0, liqC), liqL, "Liquid", worldL, false, 0, kCheck);
    gasC = 0.5 * (zl + zHi);
    gasL = new G4LogicalVolume(new G4Box("Gas", halfXY, halfXY, 0.5 * (zHi - zl)), GasXenon(), "Gas");
    gasP = new G4PVPlacement(nullptr, G4ThreeVector(0, 0, gasC), gasL, "Gas", worldL, false, 0, kCheck);
  }

  auto region = [&](double z) { return z < zl ? std::make_pair(liqL, liqC) : std::make_pair(gasL, gasC); };

  // mesh assemblies (drawing "XAMS_XAMS grid assy.pdf"): foil mid-plane at the mesh z; inside the ring bore the foil is
  // the etched mesh (bar layer), from the bore to the foil edge it lies on the ring face (foil rim); the ring body
  // (assembly thickness minus foil) is on the other side of the foil ("foil_side" up: body below, down: body above)
  const double tFoil = c.Req("mesh_common/foil_thickness_mm") * mm;
  const double rFoil = 0.5 * c.Req("mesh_common/foil_diameter_mm") * mm;
  const double bodyT = 2 * ringHalf - tFoil;
  auto* bodyL = new G4LogicalVolume(new G4Tubs("MeshRingBody", rRingIn, rRingOut, 0.5 * bodyT, 0., 360. * deg),
                                    StainlessSteel(), "MeshRing");
  auto* rimL = new G4LogicalVolume(new G4Tubs("MeshFoilRim", rRingIn, rFoil, 0.5 * tFoil, 0., 360. * deg),
                                   StainlessSteel(), "MeshRing");
  double zGate = 0., zCath = -51.8 * mm;
  std::map<std::string, std::pair<double, double>> assembly;  // z extent of each mesh assembly (foil + ring body)
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
           << " holes, " << ang << " deg" << G4endl;
    if (name == "gate") zGate = z;
    if (name == "cathode") zCath = z;
    assembly[name] = {lo, hi};
  }

  // PTFE cylinder (drawing "PTFE_cylinder.pdf"): in the bores of the gate and cathode rings, from z_top down over its
  // length (all in the liquid)
  const double rIn = 0.5 * c.Req("ptfe_cylinder/inner_diameter_mm") * mm;
  const double wall = c.Req("ptfe_cylinder/wall_thickness_mm") * mm;
  const double zt = c.Req("ptfe_cylinder/z_top_mm") * mm;
  const double zb = zt - c.Req("ptfe_cylinder/length_mm") * mm;
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
                                    G4NistManager::Instance()->FindOrBuildMaterial(
                                        Config::Get().Str("materials/copper/geant4/nist", "G4_Cu")),
                                    "CopperRing");
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

  // PTFE holders of the PMTs (config "pmt_ptfe"; drawings "PTFE_between_TS_PMT.pdf", "PTFE_between_BS_PMT.pdf"): a plate
  // from the screen-ring assembly to the PMT window face with a square opening in front of the photocathode, and a
  // block around the PMT (square slot = PMT outline) from the window face to the back of the PMT; out to the mesh-ring
  // outer radius. Logical name PTFE_gas (top, in the gas) / PTFE (bottom, in the liquid) for the surfaces.
  if (j.contains("pmt_ptfe")) {
    const auto& h = j["pmt_ptfe"];
    const double rO = 0.5 * h["outer_diameter_mm"].get<double>() * mm;
    const double ap = h["aperture_square_mm"].get<double>() * mm;
    const double height = c.Req("pmt_common/height_mm") * mm;
    for (const auto& pm : j["pmts"]) {
      const std::string name = pm["name"].get<std::string>();
      const bool top = name == "top";
      const double wz = pm["window_z_mm"].get<double>() * mm;
      const auto& sl = h["slot_square_mm"];
      const double slot = (sl.is_object() ? sl[name] : sl).get<double>() * mm;
      const auto [alo, ahi] = assembly.at(top ? "top_screen" : "bottom_screen");
      const double pLo = top ? ahi : wz, pHi = top ? wz : alo;     // plate
      const double bLo = top ? wz : wz - height, bHi = top ? wz + height : wz;  // block around the PMT
      if (pHi - pLo < 0.01 * mm)
        G4Exception("BuildXams", "GEOM040", FatalException, ("no room for the PTFE plate in front of the " + name + " PMT").c_str());
      const std::string ln = top ? "PTFE_gas" : "PTFE";
      auto [mL, mC] = region(wz);
      auto place = [&](const std::string& part, double lo, double hi, double square) {
        const double hz = 0.5 * (hi - lo);
        auto* sol = new G4SubtractionSolid("PTFE_" + name + "_" + part, new G4Tubs("o", 0., rO, hz, 0., 360. * deg),
                                           new G4Box("i", 0.5 * square, 0.5 * square, hz + 1. * mm));
        new G4PVPlacement(nullptr, G4ThreeVector(0, 0, 0.5 * (lo + hi) - mC), new G4LogicalVolume(sol, Ptfe(), ln),
                          "PTFE_" + name + "_" + part, mL, false, 0, kCheck);
        G4cout << "PTFE " << name << " PMT " << part << ": z " << lo / mm << " to " << hi / mm << " mm, r < " << rO / mm
               << " mm, square opening " << square / mm << " mm" << G4endl;
      };
      place("plate", pLo, pHi, ap);
      place("surround", bLo, bHi, slot);
    }
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
  // particle mode: a small capsule around an external source (stops the decay recoil and the betas, as the real source
  // holder does); config source/capsule {material, radius_mm}, default stainless steel, 1 mm. Outside the cryostat or in
  // the vacuum between the vessels.
  if (c.Particle() && j.contains("source") && j["source"].contains("position_mm")) {
    const auto& sp = j["source"]["position_mm"];
    const G4ThreeVector pos(sp[0].get<double>() * mm, sp[1].get<double>() * mm, sp[2].get<double>() * mm);
    const double rc = c.Num("source/capsule/radius_mm", 1.0) * mm;
    const std::string m = c.Str("source/capsule/material", "stainless_steel");
    G4Material* mat = m == "ptfe" ? Ptfe() : m == "copper" ? G4NistManager::Instance()->FindOrBuildMaterial("G4_Cu") : StainlessSteel();
    auto inside = [](const G4ThreeVector& q, double r, double zlo, double zhi, double pad) {
      return q.perp() < r + pad && q.z() > zlo - pad && q.z() < zhi + pad;
    };
    G4LogicalVolume* capMother = nullptr;
    G4ThreeVector capPos = pos;
    if (vacuumL && inside(pos, vacuumR, vacuumC - vacuumHalf, vacuumC + vacuumHalf, -rc)) {
      // the inner vessel: its tube over the full height, the flanges (ring + blind) only in the end zones
      const bool inVessel = inside(pos, tubeR, vesselBot, vesselTop, rc) || inside(pos, vesselR, tubeTop - ringT, vesselTop, rc) ||
                            inside(pos, vesselR, vesselBot, tubeBot + ringT, rc);
      if (!inVessel) {  // in the vacuum between the vessels
        capMother = vacuumL;
        capPos = pos - G4ThreeVector(0, 0, vacuumC);
      }
    } else if (!(vacuumL ? inside(pos, oTubeR, outerBot, outerTop, rc) || inside(pos, outerR, oTubeTop - oRingT, outerTop, rc) ||
                               inside(pos, outerR, outerBot, oTubeBot + oRingT, rc)
                         : inside(pos, tubeR, vesselBot, vesselTop, rc) || inside(pos, vesselR, tubeTop - ringT, vesselTop, rc) ||
                               inside(pos, vesselR, vesselBot, tubeBot + ringT, rc)) &&
               std::abs(pos.x()) + rc < wx && std::abs(pos.y()) + rc < wy && std::abs(pos.z()) + rc < wz) {
      capMother = worldL;  // outside the cryostat
    }
    if (rc > 0. && capMother) {
      new G4PVPlacement(nullptr, capPos, new G4LogicalVolume(new G4Orb("SourceCapsule", rc), mat, "SourceCapsule"), "SourceCapsule",
                        capMother, false, 0, kCheck);
      if (capMother == vacuumL)
        G4cout << "source capsule in the vacuum between the cryostat vessels (inside the outer vessel)" << G4endl;
    if (rc > 0. && capMother == worldL) G4cout << "source capsule outside the cryostat" << G4endl;
    } else if (rc > 0.) {
      G4Exception("BuildXams", "GEOM041", JustWarning,
                  "source capsule not placed (in a vessel wall / flange or in the inner vessel, or outside the world)");
    }
  }
  return worldP;
}
