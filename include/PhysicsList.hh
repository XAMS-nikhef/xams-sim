// Optical physics only: optical photons are generated directly (no scintillation / Cherenkov, no other particles).
#pragma once

#include <G4VModularPhysicsList.hh>

class PhysicsList : public G4VModularPhysicsList {
 public:
  PhysicsList();
  void ConstructParticle() override;
  void SetCuts() override {}
};
