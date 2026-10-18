#include "PhysicsList.hh"

#include <G4Electron.hh>
#include <G4Gamma.hh>
#include <G4OpticalParameters.hh>
#include <G4OpticalPhysics.hh>
#include <G4Positron.hh>
#include <G4Proton.hh>

PhysicsList::PhysicsList() {
  RegisterPhysics(new G4OpticalPhysics());
  auto* p = G4OpticalParameters::Instance();
  p->SetProcessActivation("Scintillation", false);
  p->SetProcessActivation("Cerenkov", false);
  p->SetProcessActivation("OpWLS", false);
  p->SetProcessActivation("OpWLS2", false);
  p->SetProcessActivation("OpMieHG", false);
  p->SetBoundaryInvokeSD(false);
}

void PhysicsList::ConstructParticle() {
  // G4OpticalPhysics looks up these particles (scintillation bookkeeping) even though only optical photons are tracked
  G4VModularPhysicsList::ConstructParticle();
  G4Electron::Definition();
  G4Positron::Definition();
  G4Gamma::Definition();
  G4Proton::Definition();
}
