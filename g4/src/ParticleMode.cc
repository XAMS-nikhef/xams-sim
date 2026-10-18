#include "ParticleMode.hh"

#include <G4DecayPhysics.hh>
#include <G4EmStandardPhysics_option4.hh>
#include <G4Event.hh>
#include <G4EventManager.hh>
#include <G4Gamma.hh>
#include <G4HadronicParameters.hh>
#include <G4IonTable.hh>
#include <G4ParticleGun.hh>
#include <G4ParticleTable.hh>
#include <G4PhysicalConstants.hh>
#include <G4RadioactiveDecayPhysics.hh>
#include <G4Step.hh>
#include <G4SystemOfUnits.hh>
#include <G4Track.hh>
#include <G4VProcess.hh>
#include <Randomize.hh>

#include <cmath>
#include <iomanip>
#include <nlohmann/json.hpp>

#include "Config.hh"

namespace {
// per-event bookkeeping (sequential run manager)
struct EventBuffer {
  std::vector<DepositRecord> deposits;
  std::map<int32_t, int16_t> trackParticle;  // track id -> particle code
  double edepL = 0., edepG = 0.;
  G4ThreeVector vertex;
};
EventBuffer& Buf() {
  static EventBuffer b;
  return b;
}
bool IsRadioactiveDecay(const G4VProcess* p) {
  if (!p) return false;
  const auto& n = p->GetProcessName();
  return n == "RadioactiveDecay" || n == "Radioactivation" || n == "RadioactiveDecayBase";
}
}  // namespace

// ------------------------------------------------------------------------------------------------ output
DepositOutput& DepositOutput::Get() {
  static DepositOutput o;
  return o;
}

void DepositOutput::Open(const std::string& path) {
  fPath = path;
  fStem = path.size() > 4 && path.substr(path.size() - 4) == ".bin" ? path.substr(0, path.size() - 4) : path;
  fOut.open(fPath, std::ios::binary);
  fEvents.open(fStem + ".events.bin", std::ios::binary);
  Code("particle", "none");
  Code("process", "primary");
}

int16_t DepositOutput::Code(const std::string& table, const std::string& name) {
  auto& idx = fIndex[table];
  auto it = idx.find(name);
  if (it != idx.end()) return it->second;
  auto& t = fTables[table];
  const auto c = static_cast<int16_t>(t.size());
  t.push_back(name);
  idx[name] = c;
  return c;
}

void DepositOutput::WriteEvent(const EventRecord& e, const std::vector<DepositRecord>& d) {
  if (!d.empty()) fOut.write(reinterpret_cast<const char*>(d.data()), sizeof(DepositRecord) * d.size());
  fEvents.write(reinterpret_cast<const char*>(&e), sizeof(EventRecord));
  ++fNEvents;
  fNDeposits += static_cast<long>(d.size());
  if (e.edep_lxe > 0) ++fNWithLxe;
}

void DepositOutput::Close() {
  if (!fOut.is_open()) return;
  fOut.close();
  fEvents.close();
  nlohmann::json h;
  h["format"] = "xamsg4 particle mode v1";
  h["files"] = {{"deposits", fPath}, {"events", fStem + ".events.bin"}};
  h["units"] = {{"length", "mm"}, {"time", "ns"}, {"energy", "keV"}};
  h["deposit_dtype"] = nlohmann::json::array(
      {{"event", "<i4"}, {"x", "<f4"}, {"y", "<f4"}, {"z", "<f4"}, {"t", "<f8"}, {"edep", "<f4"}, {"particle", "<i2"},
       {"parent_particle", "<i2"}, {"track", "<i4"}, {"parent", "<i4"}, {"creaproc", "<i2"}, {"edproc", "<i2"},
       {"volume", "<i2"}});
  h["event_dtype"] = nlohmann::json::array({{"event", "<i4"}, {"x_pri", "<f4"}, {"y_pri", "<f4"}, {"z_pri", "<f4"},
                                            {"n_deposits", "<i4"}, {"edep_lxe", "<f4"}, {"edep_gxe", "<f4"}});
  h["deposit_record_bytes"] = sizeof(DepositRecord);
  h["event_record_bytes"] = sizeof(EventRecord);
  h["codes"] = fTables;
  h["info"] = fInfo;
  h["counts"] = {{"events", fNEvents}, {"deposits", fNDeposits}, {"events_with_lxe_deposit", fNWithLxe}};
  std::ofstream(fStem + ".json") << std::setw(1) << h << "\n";
}

// ------------------------------------------------------------------------------------------------ physics
ParticlePhysicsList::ParticlePhysicsList() {
  SetVerboseLevel(0);
  RegisterPhysics(new G4EmStandardPhysics_option4());  // accurate low-energy EM (photoabsorption, Compton, electrons)
  RegisterPhysics(new G4DecayPhysics());
  RegisterPhysics(new G4RadioactiveDecayPhysics());
  // Geant4 >= 11.2 does not decay nuclides with half-lives above a threshold (default 1 year): raise it (Cs-137: 30 y)
  G4HadronicParameters::Instance()->SetTimeThresholdForRadioactiveDecay(1.0e+60 * year);
}

void ParticlePhysicsList::SetCuts() {
  // production cut: secondaries (delta rays, bremsstrahlung) below the cut are not produced; their energy is deposited
  // locally. 0.1 mm in LXe is ~70 keV for electrons — fine-grained enough for clustering at mm resolution.
  SetDefaultCutValue(Config::Get().Num("particle/production_cut_mm", 0.1) * mm);
}

// ------------------------------------------------------------------------------------------------ source
ParticleGenerator::ParticleGenerator() : fGun(std::make_unique<G4ParticleGun>(1)) {
  const auto& c = Config::Get();
  const std::string type = c.Str("source/type", "isotope");
  fIsotope = type == "isotope";
  if (!fIsotope) {
    fGun->SetParticleDefinition(G4Gamma::Definition());
    fGun->SetParticleEnergy(c.Num("source/energy_keV", 661.657) * keV);
  }
  const auto& j = c.J();
  G4ThreeVector pos;
  if (j.contains("source") && j["source"].contains("position_mm"))
    pos = G4ThreeVector(j["source"]["position_mm"][0].get<double>(), j["source"]["position_mm"][1].get<double>(),
                        j["source"]["position_mm"][2].get<double>()) * mm;
  fGun->SetParticlePosition(pos);
  fCone = c.Str("source/direction", "isotropic") == "cone";
  fCosMin = std::cos(c.Num("source/half_angle_deg", 180.) * deg);
  fZTarget = c.Num("source/z_target_mm", -25.9) * mm;
}

ParticleGenerator::~ParticleGenerator() = default;

void ParticleGenerator::GeneratePrimaries(G4Event* event) {
  if (fIsotope && !fIonSet) {
    // ions exist only after the physics is built, so look the ion up at the first event
    const auto& c = Config::Get();
    auto* ion = G4IonTable::GetIonTable()->GetIon(static_cast<int>(c.Num("source/Z", 55)),
                                                  static_cast<int>(c.Num("source/A", 137)), 0. * keV);
    fGun->SetParticleDefinition(ion);
    fGun->SetParticleCharge(0. * eplus);
    fGun->SetParticleEnergy(0.);  // at rest: decays in place
    fIonSet = true;
  }
  if (!fIsotope) {
    G4ThreeVector axis = (fCone ? G4ThreeVector(0, 0, fZTarget) - fGun->GetParticlePosition() : G4ThreeVector(0, 0, 1)).unit();
    const double cmin = fCone ? fCosMin : -1.;
    const double ct = cmin + (1. - cmin) * G4UniformRand(), st = std::sqrt(1. - ct * ct), ph = twopi * G4UniformRand();
    G4ThreeVector d(st * std::cos(ph), st * std::sin(ph), ct);
    d.rotateUz(axis);
    fGun->SetParticleMomentumDirection(d);
  }
  Buf().vertex = fGun->GetParticlePosition();
  fGun->GeneratePrimaryVertex(event);
}

// ------------------------------------------------------------------------------------------------ actions
G4ClassificationOfNewTrack ParticleStacking::ClassifyNewTrack(const G4Track* track) {
  const auto& n = track->GetDefinition()->GetParticleName();
  if (n == "anti_nu_e" || n == "nu_e" || n == "opticalphoton") return fKill;
  // decay products start at time 0: the Cs-137 (30 y) and Ba-137m (2.55 min) decay times are irrelevant here and would
  // destroy the ns precision of the double time
  if (IsRadioactiveDecay(track->GetCreatorProcess())) const_cast<G4Track*>(track)->SetGlobalTime(0.);
  return fUrgent;
}

void ParticleTracking::PreUserTrackingAction(const G4Track* track) {
  Buf().trackParticle[track->GetTrackID()] =
      DepositOutput::Get().Code("particle", track->GetDefinition()->GetParticleName());
}

void ParticleStepping::UserSteppingAction(const G4Step* step) {
  const double e = step->GetTotalEnergyDeposit();
  if (e <= 0.) return;
  const auto* pre = step->GetPreStepPoint();
  const auto& mat = pre->GetMaterial()->GetName();
  const bool lxe = mat == "LXe", gxe = mat == "GXe";
  if (!lxe && !gxe) return;
  auto& b = Buf();
  auto& out = DepositOutput::Get();
  const auto* track = step->GetTrack();
  const auto* post = step->GetPostStepPoint();
  const G4ThreeVector p = 0.5 * (pre->GetPosition() + post->GetPosition());
  DepositRecord r{};
  r.event = G4EventManager::GetEventManager()->GetConstCurrentEvent()->GetEventID();
  r.x = static_cast<float>(p.x() / mm);
  r.y = static_cast<float>(p.y() / mm);
  r.z = static_cast<float>(p.z() / mm);
  r.t = post->GetGlobalTime() / ns;
  r.edep = static_cast<float>(e / keV);
  r.track = track->GetTrackID();
  r.parent = track->GetParentID();
  auto it = b.trackParticle.find(r.track);
  r.particle = it != b.trackParticle.end() ? it->second : out.Code("particle", track->GetDefinition()->GetParticleName());
  auto ip = b.trackParticle.find(r.parent);
  r.parent_particle = ip != b.trackParticle.end() ? ip->second : out.Code("particle", "none");
  const auto* cp = track->GetCreatorProcess();
  r.creaproc = out.Code("process", cp ? cp->GetProcessName() : "primary");
  const auto* sp = post->GetProcessDefinedStep();
  r.edproc = out.Code("process", sp ? sp->GetProcessName() : "unknown");
  r.volume = out.Code("volume", pre->GetPhysicalVolume()->GetName());
  b.deposits.push_back(r);
  (lxe ? b.edepL : b.edepG) += e / keV;
}

void ParticleEvent::BeginOfEventAction(const G4Event*) {
  auto& b = Buf();
  b.deposits.clear();
  b.trackParticle.clear();
  b.edepL = b.edepG = 0.;
}

void ParticleEvent::EndOfEventAction(const G4Event* event) {
  auto& b = Buf();
  EventRecord e{};
  e.event = event->GetEventID();
  e.x_pri = static_cast<float>(b.vertex.x() / mm);
  e.y_pri = static_cast<float>(b.vertex.y() / mm);
  e.z_pri = static_cast<float>(b.vertex.z() / mm);
  e.n_deposits = static_cast<int32_t>(b.deposits.size());
  e.edep_lxe = static_cast<float>(b.edepL);
  e.edep_gxe = static_cast<float>(b.edepG);
  DepositOutput::Get().WriteEvent(e, b.deposits);
}

void ParticleActionInitialization::Build() const {
  SetUserAction(new ParticleGenerator());
  SetUserAction(new ParticleStacking());
  SetUserAction(new ParticleTracking());
  SetUserAction(new ParticleStepping());
  SetUserAction(new ParticleEvent());
}
