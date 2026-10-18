#include "PrimaryGeneratorAction.hh"

#include "Config.hh"

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
  fMessenger->DeclareProperty("shape", fShape, "point | cylinder | beam | beam_disc | s1 | s2");
  fMessenger->DeclareProperty("direction", fDirection, "beam direction (beam shape only)");
  fMessenger->DeclarePropertyWithUnit("position", "mm", fPosition, "point source position");
  fMessenger->DeclarePropertyWithUnit("rmax", "mm", fRmax, "cylinder radius");
  fMessenger->DeclarePropertyWithUnit("zmin", "mm", fZmin, "cylinder lower z");
  fMessenger->DeclarePropertyWithUnit("zmax", "mm", fZmax, "cylinder upper z");
}

PrimaryGeneratorAction::~PrimaryGeneratorAction() = default;

void PrimaryGeneratorAction::SetZRangeFromConfig() {
  const auto& c = Config::Get();
  const double half = 0.5 * c.Num("mesh_common/foil_thickness_mm", 0.15) * mm + 0.01 * mm;
  double anode = 0, gate = 0, cathode = 0;
  for (const auto& m : c.J()["meshes"]) {
    const auto n = m["name"].get<std::string>();
    const double z = m["z_mm"].get<double>() * mm;
    if (n == "anode") anode = z;
    if (n == "gate") gate = z;
    if (n == "cathode") cathode = z;
  }
  if (fShape == "s2") {
    fZmin = c.Num("liquid/surface_z_mm", 4.0) * mm;
    fZmax = anode - half;
  } else {
    fZmin = cathode + half;
    fZmax = gate - half;
  }
  fZFor = fShape;
  G4cout << "source " << fShape << ": z " << fZmin / mm << " to " << fZmax / mm << " mm, r < " << fRmax / mm << " mm"
         << G4endl;
}

G4ThreeVector PrimaryGeneratorAction::SamplePosition() {
  if ((fShape == "s1" || fShape == "s2") && fZFor != fShape) SetZRangeFromConfig();
  if (fShape == "cylinder" || fShape == "s1" || fShape == "s2") {
    const G4double r = fRmax * std::sqrt(G4UniformRand());
    const G4double phi = twopi * G4UniformRand();
    return {r * std::cos(phi), r * std::sin(phi), fZmin + (fZmax - fZmin) * G4UniformRand()};
  }
  if (fShape == "beam_disc") {  // random point in a disc of radius rmax around position (in x-y)
    const G4double r = fRmax * std::sqrt(G4UniformRand());
    const G4double phi = twopi * G4UniformRand();
    return fPosition + G4ThreeVector(r * std::cos(phi), r * std::sin(phi), 0.);
  }
  return fPosition;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event) {
  // isotropic direction
  const G4double cost = 2. * G4UniformRand() - 1.;
  const G4double sint = std::sqrt(1. - cost * cost);
  const G4double phi = twopi * G4UniformRand();
  G4ThreeVector dir(sint * std::cos(phi), sint * std::sin(phi), cost);
  if (fShape == "beam" || fShape == "beam_disc") dir = fDirection.unit();
  // random linear polarisation perpendicular to the direction
  const G4ThreeVector perp = dir.orthogonal().unit();
  const G4ThreeVector perp2 = dir.cross(perp).unit();
  const G4double a = twopi * G4UniformRand();
  fGun->SetParticleMomentumDirection(dir);
  fGun->SetParticlePolarization(std::cos(a) * perp + std::sin(a) * perp2);
  fGun->SetParticlePosition(SamplePosition());
  fGun->GeneratePrimaryVertex(event);
}
