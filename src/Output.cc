#include "Output.hh"

#include <nlohmann/json.hpp>
#include <stdexcept>

Output& Output::Get() {
  static Output instance;
  return instance;
}

void Output::Open(const std::string& path) {
  Close();
  fPath = path;
  fOut.open(path, std::ios::binary | std::ios::trunc);
  if (!fOut) throw std::runtime_error("cannot open output " + path);
}

void Output::Write(const PhotonRecord& r) {
  if (fOut) fOut.write(reinterpret_cast<const char*>(&r), sizeof(r));
}

int16_t Output::VolumeIndex(const std::string& name) {
  auto it = fVolumes.find(name);
  if (it != fVolumes.end()) return it->second;
  auto idx = static_cast<int16_t>(fVolumes.size());
  fVolumes[name] = idx;
  return idx;
}

void Output::Close() {
  if (!fOut.is_open()) return;
  fOut.close();
  nlohmann::json vols = nlohmann::json::object();
  for (const auto& [name, idx] : fVolumes) vols[std::to_string(idx)] = name;
  std::ofstream side(fPath + ".volumes.json");
  side << vols.dump(1) << "\n";
}
