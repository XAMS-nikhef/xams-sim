#include "PhotonActions.hh"

#include <G4EventManager.hh>
#include <G4OpBoundaryProcess.hh>
#include <G4OpticalPhoton.hh>
#include <G4ProcessManager.hh>
#include <G4Step.hh>
#include <G4Track.hh>
#include <G4VPhysicalVolume.hh>
#include <G4VProcess.hh>

#include "PrimaryGeneratorAction.hh"

PhotonRecord& TrackingAction::Current() {
  static PhotonRecord rec{};
  return rec;
}

void TrackingAction::PreUserTrackingAction(const G4Track* track) {
  auto& r = Current();
  r = PhotonRecord{};
  r.event = G4EventManager::GetEventManager()->GetConstCurrentEvent()->GetEventID();
  const auto& p = track->GetPosition();
  r.x0 = static_cast<float>(p.x());
  r.y0 = static_cast<float>(p.y());
  r.z0 = static_cast<float>(p.z());
  r.sensor = -1;
  r.volume = -1;
  r.end_code = kUnknown;
}

void TrackingAction::PostUserTrackingAction(const G4Track* track) {
  auto& r = Current();
  const auto& p = track->GetPosition();
  r.x1 = static_cast<float>(p.x());
  r.y1 = static_cast<float>(p.y());
  r.z1 = static_cast<float>(p.z());
  Output::Get().Write(r);
}

G4OpBoundaryProcess* SteppingAction::Boundary() {
  if (fBoundary) return fBoundary;
  auto* pm = G4OpticalPhoton::Definition()->GetProcessManager();
  auto* list = pm->GetProcessList();
  for (size_t i = 0; i < list->size(); ++i) {
    if ((*list)[i]->GetProcessName() == "OpBoundary") {
      fBoundary = dynamic_cast<G4OpBoundaryProcess*>((*list)[i]);
      break;
    }
  }
  return fBoundary;
}

void SteppingAction::UserSteppingAction(const G4Step* step) {
  auto& r = TrackingAction::Current();
  const auto* post = step->GetPostStepPoint();
  const auto* pre = step->GetPreStepPoint();

  // left the world
  if (!post->GetPhysicalVolume()) {
    r.end_code = kEscaped;
    return;
  }
  const auto* proc = post->GetProcessDefinedStep();
  if (proc && proc->GetProcessName() == "OpAbsorption") {
    r.end_code = kBulkAbsorbed;
    r.volume = Output::Get().VolumeIndex(pre->GetPhysicalVolume()->GetName());
    return;
  }
  if (post->GetStepStatus() != fGeomBoundary || !Boundary()) return;

  switch (Boundary()->GetStatus()) {
    case Detection:
      r.end_code = kDetected;
      r.sensor = static_cast<int16_t>(post->GetPhysicalVolume()->GetCopyNo());
      r.volume = Output::Get().VolumeIndex(post->GetPhysicalVolume()->GetName());
      break;
    case NoRINDEX:  // entered a material without refractive index (world, steel / PTFE without surface, PMT body)
    case Absorption:
      r.end_code = kSurfaceAbsorbed;
      r.volume = Output::Get().VolumeIndex(post->GetPhysicalVolume()->GetName());
      break;
    case FresnelReflection:
    case TotalInternalReflection:
    case LambertianReflection:
    case LobeReflection:
    case SpikeReflection:
    case BackScattering:
      ++r.n_refl;
      break;
    default:
      break;
  }
}

void ActionInitialization::Build() const {
  SetUserAction(new PrimaryGeneratorAction());
  SetUserAction(new TrackingAction());
  SetUserAction(new SteppingAction());
}
