// One 178 nm optical photon per event, isotropic, random linear polarisation.
// Source shapes (macro commands /xamsopt/source/...):
//   point     at /xamsopt/source/position
//   cylinder  uniform in a cylinder of radius rmax between zmin and zmax (S1: liquid; S2: gas gap), centred on x = y = 0
//   beam      from /xamsopt/source/position in the fixed /xamsopt/source/direction (tests)
#pragma once

#include <G4ThreeVector.hh>
#include <G4VUserPrimaryGeneratorAction.hh>
#include <memory>

class G4GenericMessenger;
class G4ParticleGun;

class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction {
 public:
  PrimaryGeneratorAction();
  ~PrimaryGeneratorAction() override;
  void GeneratePrimaries(G4Event* event) override;

 private:
  G4ThreeVector SamplePosition() const;
  std::unique_ptr<G4ParticleGun> fGun;
  std::unique_ptr<G4GenericMessenger> fMessenger;
  G4String fShape = "point";
  G4ThreeVector fPosition;
  G4ThreeVector fDirection{0., 0., 1.};
  G4double fRmax = 0.;
  G4double fZmin = 0.;
  G4double fZmax = 0.;
};
