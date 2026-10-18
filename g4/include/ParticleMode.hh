// Particle mode of xamsg4 (xams-sim plan S2): radioactive sources / gammas through the full XAMS geometry, every energy
// deposit in xenon (liquid and gas) written as a fixed-size binary record.
//
//   xamsg4 -m particle -c config.json -o run/x/deposits.bin [-s seed] macro.mac
//
// Output (read in Python with xamssim.g4io):
//   <stem>.bin         one DepositRecord per Geant4 step with energy deposit in LXe / GXe
//   <stem>.events.bin  one EventRecord per event (also events without deposits)
//   <stem>.json        header: record layouts, units, code -> name tables (particle, process, volume), config, seed,
//                      source, counts
// Source (config "source", written by xamssim/g4run.py from config/sources/<name>.yaml):
//   type "isotope": an ion (Z, A) at rest at position_mm, decayed by Geant4 radioactive decay (Cs-137 -> Ba-137m ->
//                   662 keV); decay products get time 0 (no 30-year decay times in the records)
//   type "gamma":   one gamma of energy_keV from position_mm
//   direction "isotropic" (default) or "cone": within half_angle_deg around the direction to the TPC centre (0, 0, z_target_mm)
#pragma once

#include <G4UserEventAction.hh>
#include <G4UserStackingAction.hh>
#include <G4UserSteppingAction.hh>
#include <G4UserTrackingAction.hh>
#include <G4VModularPhysicsList.hh>
#include <G4VUserActionInitialization.hh>
#include <G4VUserPrimaryGeneratorAction.hh>

#include <cstdint>
#include <fstream>
#include <map>
#include <memory>
#include <string>
#include <vector>

class G4ParticleGun;

#pragma pack(push, 1)
struct DepositRecord {
  int32_t event;
  float x, y, z;            // mm (mid-point of the step)
  double t;                 // ns (post-step global time; decay products start at 0)
  float edep;               // keV
  int16_t particle;         // code -> name in header "codes.particle"
  int16_t parent_particle;  // code of the parent's particle ("none" for primaries)
  int32_t track, parent;    // Geant4 track ids (parent 0 for primaries)
  int16_t creaproc;         // process that created the track (code; "primary" for primaries)
  int16_t edproc;           // process that limited the step (code)
  int16_t volume;           // pre-step physical volume (code)
};
struct EventRecord {
  int32_t event;
  float x_pri, y_pri, z_pri;  // mm, primary vertex
  int32_t n_deposits;         // records of this event in <stem>.bin
  float edep_lxe, edep_gxe;   // keV, total per event
};
#pragma pack(pop)

class DepositOutput {
 public:
  static DepositOutput& Get();
  void Open(const std::string& path);
  int16_t Code(const std::string& table, const std::string& name);
  void WriteEvent(const EventRecord& e, const std::vector<DepositRecord>& d);
  void SetInfo(const std::string& key, const std::string& value) { fInfo[key] = value; }
  void Close();
  bool IsOpen() const { return fOut.is_open(); }

 private:
  DepositOutput() = default;
  std::string fPath, fStem;
  std::ofstream fOut, fEvents;
  std::map<std::string, std::vector<std::string>> fTables;
  std::map<std::string, std::map<std::string, int16_t>> fIndex;
  std::map<std::string, std::string> fInfo;
  long fNEvents = 0, fNDeposits = 0, fNWithLxe = 0;
};

class ParticlePhysicsList : public G4VModularPhysicsList {
 public:
  ParticlePhysicsList();
  void SetCuts() override;
};

class ParticleGenerator : public G4VUserPrimaryGeneratorAction {
 public:
  ParticleGenerator();
  ~ParticleGenerator() override;
  void GeneratePrimaries(G4Event* event) override;

 private:
  std::unique_ptr<G4ParticleGun> fGun;
  bool fIsotope = true, fCone = false, fIonSet = false;  // the gun starts as a geantino: the ion is set at the first event
  double fCosMin = -1.;
  double fZTarget = 0.;
};

class ParticleStacking : public G4UserStackingAction {
 public:
  G4ClassificationOfNewTrack ClassifyNewTrack(const G4Track* track) override;
};

class ParticleTracking : public G4UserTrackingAction {
 public:
  void PreUserTrackingAction(const G4Track* track) override;
};

class ParticleStepping : public G4UserSteppingAction {
 public:
  void UserSteppingAction(const G4Step* step) override;
};

class ParticleEvent : public G4UserEventAction {
 public:
  void BeginOfEventAction(const G4Event* event) override;
  void EndOfEventAction(const G4Event* event) override;
};

class ParticleActionInitialization : public G4VUserActionInitialization {
 public:
  void Build() const override;
};
