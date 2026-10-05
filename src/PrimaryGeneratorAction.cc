#include "PrimaryGeneratorAction.hh"

#include <G4Event.hh>
#include <G4GenericMessenger.hh>
#include <G4OpticalPhoton.hh>
#include <G4ParticleGun.hh>
#include <G4PhysicalConstants.hh>
#include <G4SystemOfUnits.hh>
#include <Randomize.hh>

namespace {
const G4double kPhotonEnergy = h_Planck * c_light / (178. * nm);
}

PrimaryGeneratorAction::PrimaryGeneratorAction() : fGun(std::make_unique<G4ParticleGun>(1)) {
  fGun->SetParticleDefinition(G4OpticalPhoton::Definition());
  fGun->SetParticleEnergy(kPhotonEnergy);

  fMessenger = std::make_unique<G4GenericMessenger>(this, "/xamsopt/source/", "photon source");
  fMessenger->DeclareProperty("shape", fShape, "point | cylinder");
  fMessenger->DeclarePropertyWithUnit("position", "mm", fPosition, "point source position");
  fMessenger->DeclarePropertyWithUnit("rmax", "mm", fRmax, "cylinder radius");
  fMessenger->DeclarePropertyWithUnit("zmin", "mm", fZmin, "cylinder lower z");
  fMessenger->DeclarePropertyWithUnit("zmax", "mm", fZmax, "cylinder upper z");
}

PrimaryGeneratorAction::~PrimaryGeneratorAction() = default;

G4ThreeVector PrimaryGeneratorAction::SamplePosition() const {
  if (fShape == "cylinder") {
    const G4double r = fRmax * std::sqrt(G4UniformRand());
    const G4double phi = twopi * G4UniformRand();
    return {r * std::cos(phi), r * std::sin(phi), fZmin + (fZmax - fZmin) * G4UniformRand()};
  }
  return fPosition;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event) {
  // isotropic direction
  const G4double cost = 2. * G4UniformRand() - 1.;
  const G4double sint = std::sqrt(1. - cost * cost);
  const G4double phi = twopi * G4UniformRand();
  const G4ThreeVector dir(sint * std::cos(phi), sint * std::sin(phi), cost);
  // random linear polarisation perpendicular to the direction
  const G4ThreeVector perp = dir.orthogonal().unit();
  const G4ThreeVector perp2 = dir.cross(perp).unit();
  const G4double a = twopi * G4UniformRand();
  fGun->SetParticleMomentumDirection(dir);
  fGun->SetParticlePolarization(std::cos(a) * perp + std::sin(a) * perp2);
  fGun->SetParticlePosition(SamplePosition());
  fGun->GeneratePrimaryVertex(event);
}
