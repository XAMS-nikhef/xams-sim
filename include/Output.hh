// Per-photon output: one fixed-size binary record per photon, read in Python with tools/read_output.py.
#pragma once

#include <cstdint>
#include <fstream>
#include <map>
#include <string>

// end codes
enum EndCode : int16_t {
  kUnknown = 0,
  kDetected = 1,         // absorbed by a photocathode (QE)
  kBulkAbsorbed = 2,     // absorbed in a material (OpAbsorption)
  kSurfaceAbsorbed = 3,  // absorbed at a surface (boundary 'Absorption')
  kEscaped = 4,          // left the world
};

#pragma pack(push, 1)
struct PhotonRecord {
  int32_t event;
  float x0, y0, z0;  // origin [mm]
  float x1, y1, z1;  // end point [mm]
  int16_t end_code;  // EndCode
  int16_t sensor;    // -1 none; 0 bottom PMT; 1-4 top-PMT sectors I-IV; 6, 7 SiPMs; 10 test cathode
  int16_t volume;    // index of the volume where the photon ended (names in <file>.volumes.json)
  int16_t n_refl;    // number of reflections (Fresnel, total internal, Lambertian, lobe, spike, backscatter)
};
#pragma pack(pop)

// Every photon is counted in a tally (end code x end volume, sensor) written to <file>.summary.json at Close;
// with detected_only only detected photons get a record (production runs: the origin of each detected photon).
class Output {
 public:
  static Output& Get();
  void Open(const std::string& path, bool detected_only = false);
  void Write(const PhotonRecord& r);
  void Close();
  int16_t VolumeIndex(const std::string& name);  // stable index per volume name
  void SetInfo(const std::string& key, const std::string& value) { fInfo[key] = value; }

 private:
  Output() = default;
  std::ofstream fOut;
  std::string fPath;
  bool fDetectedOnly = false;
  long fN = 0;
  std::map<std::string, int16_t> fVolumes;
  std::map<std::pair<int16_t, int16_t>, long> fTally;  // (end code, volume) -> photons
  std::map<int16_t, long> fSensors;                    // sensor -> detected photons
  std::map<std::string, std::string> fInfo;
};
