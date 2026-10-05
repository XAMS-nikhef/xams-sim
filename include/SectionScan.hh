// Geometry cross section from Geant4's own navigator: on a grid in a plane, the volume at every point.
//   /xamsopt/section <file> <plane: xz|yz|xy> <offset_mm> <u_min> <u_max> <v_min> <v_max> <step_mm>
// writes <file> (uint16 volume index per grid point, row-major in v, then u) and <file>.json (grid + volume names).
// tools/plot_section.py draws it.
#pragma once

#include <G4UImessenger.hh>
#include <memory>
#include <string>

class G4UIcommand;
class G4UIdirectory;

class SectionScan : public G4UImessenger {
 public:
  SectionScan();
  void SetNewValue(G4UIcommand* cmd, G4String args) override;
  void Scan(const std::string& args);

 private:
  std::unique_ptr<G4UIdirectory> fDir;
  std::unique_ptr<G4UIcommand> fCmd;
};
