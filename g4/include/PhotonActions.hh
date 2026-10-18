// Bookkeeping per photon: TrackingAction starts / writes the record, SteppingAction follows the boundary processes.
// Sequential run manager: one record in flight at a time.
#pragma once

#include <G4UserSteppingAction.hh>
#include <G4UserTrackingAction.hh>
#include <G4VUserActionInitialization.hh>

#include "Output.hh"

class G4OpBoundaryProcess;

class TrackingAction : public G4UserTrackingAction {
 public:
  void PreUserTrackingAction(const G4Track* track) override;
  void PostUserTrackingAction(const G4Track* track) override;
  static PhotonRecord& Current();
};

class SteppingAction : public G4UserSteppingAction {
 public:
  void UserSteppingAction(const G4Step* step) override;

 private:
  G4OpBoundaryProcess* Boundary();
  G4OpBoundaryProcess* fBoundary = nullptr;
};

class ActionInitialization : public G4VUserActionInitialization {
 public:
  void Build() const override;
};
