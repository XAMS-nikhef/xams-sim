#include "SectionScan.hh"

#include <G4Navigator.hh>
#include <G4SystemOfUnits.hh>
#include <G4TransportationManager.hh>
#include <G4UIcommand.hh>
#include <G4UIdirectory.hh>
#include <G4UIparameter.hh>
#include <G4LogicalVolume.hh>
#include <G4Material.hh>
#include <G4VPhysicalVolume.hh>

#include <cstdint>
#include <fstream>
#include <map>
#include <nlohmann/json.hpp>
#include <sstream>
#include <vector>

SectionScan::SectionScan() {
  fDir = std::make_unique<G4UIdirectory>("/xamsg4/");
  fCmd = std::make_unique<G4UIcommand>("/xamsg4/section", this);
  fCmd->SetGuidance("Volume map of a plane: file plane(xz|yz|xy) offset umin umax vmin vmax step (mm)");
  fCmd->SetParameter(new G4UIparameter("file", 's', false));
  fCmd->SetParameter(new G4UIparameter("plane", 's', false));
  for (const char* p : {"offset", "umin", "umax", "vmin", "vmax", "step"}) fCmd->SetParameter(new G4UIparameter(p, 'd', false));
}

void SectionScan::SetNewValue(G4UIcommand* cmd, G4String args) {
  if (cmd == fCmd.get()) Scan(args);
}

void SectionScan::Scan(const std::string& args) {
  std::stringstream ss(args);
  std::string file, plane;
  double off, umin, umax, vmin, vmax, step;
  ss >> file >> plane >> off >> umin >> umax >> vmin >> vmax >> step;
  if (!ss) {
    G4cerr << "usage: /xamsg4/section file plane offset umin umax vmin vmax step   (mm)" << G4endl;
    return;
  }
  auto* nav = G4TransportationManager::GetTransportationManager()->GetNavigatorForTracking();
  const int nu = static_cast<int>((umax - umin) / step) + 1;
  const int nv = static_cast<int>((vmax - vmin) / step) + 1;
  std::vector<uint16_t> map(static_cast<size_t>(nu) * nv);
  std::map<std::string, uint16_t> names;
  std::map<std::string, std::string> materials;
  for (int iv = 0; iv < nv; ++iv) {
    const double v = vmin + iv * step;
    for (int iu = 0; iu < nu; ++iu) {
      const double u = umin + iu * step;
      G4ThreeVector p;
      if (plane == "xz") p = {u * mm, off * mm, v * mm};
      else if (plane == "yz") p = {off * mm, u * mm, v * mm};
      else p = {u * mm, v * mm, off * mm};
      const auto* pv = nav->LocateGlobalPointAndSetup(p, nullptr, false, true);
      const std::string n = pv ? pv->GetName() : "outside";
      if (pv && !materials.count(n)) materials[n] = pv->GetLogicalVolume()->GetMaterial()->GetName();
      auto it = names.find(n);
      uint16_t idx;
      if (it == names.end()) {
        idx = static_cast<uint16_t>(names.size());
        names[n] = idx;
      } else {
        idx = it->second;
      }
      map[static_cast<size_t>(iv) * nu + iu] = idx;
    }
  }
  std::ofstream(file, std::ios::binary).write(reinterpret_cast<const char*>(map.data()), map.size() * sizeof(uint16_t));
  nlohmann::json meta = {{"plane", plane}, {"offset_mm", off}, {"umin", umin}, {"umax", umax}, {"vmin", vmin},
                         {"vmax", vmax}, {"step_mm", step}, {"nu", nu}, {"nv", nv}};
  for (const auto& [n, i] : names) meta["volumes"][std::to_string(i)] = n;
  for (const auto& [n, m] : materials) meta["materials"][n] = m;
  std::ofstream(file + ".json") << meta.dump(1) << "\n";
  G4cout << "section " << plane << " written to " << file << " (" << nu << " x " << nv << ")" << G4endl;
}
