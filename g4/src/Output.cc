#include "Output.hh"

#include <nlohmann/json.hpp>
#include <stdexcept>

Output& Output::Get() {
  static Output instance;
  return instance;
}

void Output::Open(const std::string& path, bool detected_only) {
  Close();
  fPath = path;
  fDetectedOnly = detected_only;
  fN = 0;
  fTally.clear();
  fSensors.clear();
  fOut.open(path, std::ios::binary | std::ios::trunc);
  if (!fOut) throw std::runtime_error("cannot open output " + path);
}

void Output::Write(const PhotonRecord& r) {
  ++fN;
  ++fTally[{r.end_code, r.volume}];
  if (r.end_code == kDetected) ++fSensors[r.sensor];
  if (fOut && (!fDetectedOnly || r.end_code == kDetected)) fOut.write(reinterpret_cast<const char*>(&r), sizeof(r));
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

  nlohmann::json sum = {{"n_photons", fN}, {"detected_only", fDetectedOnly}};
  for (const auto& [k, v] : fInfo) sum["info"][k] = v;
  nlohmann::json tally = nlohmann::json::array();
  for (const auto& [key, n] : fTally) {
    std::string vname = "none";
    for (const auto& [name, idx] : fVolumes)
      if (idx == key.second) vname = name;
    tally.push_back({{"end_code", key.first}, {"volume", vname}, {"n", n}});
  }
  sum["tally"] = tally;
  for (const auto& [s, n] : fSensors) sum["detected_by_sensor"][std::to_string(s)] = n;
  std::ofstream(fPath + ".summary.json") << sum.dump(1) << "\n";
}
