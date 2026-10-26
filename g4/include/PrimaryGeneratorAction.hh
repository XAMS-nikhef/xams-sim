// One 178 nm optical photon per event, isotropic, random linear polarisation.
// Source shapes (macro commands /xamsg4/source/...):
//   point     at /xamsg4/source/position
//   cylinder  uniform in a cylinder of radius rmax between zmin and zmax (S1: liquid; S2: gas gap), centred on x = y = 0
//   beam      from /xamsg4/source/position in the fixed /xamsg4/source/direction (tests)
//   beam_disc as beam, from random points in a disc of radius rmax around position (tests)
//   s2        uniform in the gas gap: liquid surface to just below the anode foil, r < rmax (z range from the config)
//   s1        uniform in the drift region: just above the cathode foil to just below the gate foil, r < rmax
//   liquid    uniform in the liquid xenon (material LXe) of the cylinder rmax, zmin..zmax, without the cylinder
//             r < exclude_r, exclude_zmin..exclude_zmax (rejection sampling with the navigator; outer-liquid light map)
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
  G4ThreeVector SamplePosition();
  void SetZRangeFromConfig();
  std::unique_ptr<G4ParticleGun> fGun;
  std::unique_ptr<G4GenericMessenger> fMessenger;
  G4String fShape = "point";
  G4ThreeVector fPosition;
  G4ThreeVector fDirection{0., 0., 1.};
  G4double fRmax = 0.;
  G4double fZmin = 0.;
  G4double fZmax = 0.;
  G4String fZFor;  // shape for which zmin / zmax were taken from the config
  G4double fExclR = 0.;     // liquid: excluded cylinder (the TPC)
  G4double fExclZmin = 0.;
  G4double fExclZmax = 0.;
};
