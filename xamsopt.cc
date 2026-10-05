// XAMS optical simulation.
//   xamsopt -c run/config.json -o run/photons.bin [-s seed] [macro.mac]
// Without a macro: interactive session with visualisation.
#include <G4RunManagerFactory.hh>
#include <G4UIExecutive.hh>
#include <G4UImanager.hh>
#include <G4VisExecutive.hh>
#include <Randomize.hh>

#include <iostream>
#include <string>

#include "Config.hh"
#include "DetectorConstruction.hh"
#include "Output.hh"
#include "PhotonActions.hh"
#include "PhysicsList.hh"

int main(int argc, char** argv) {
  std::string config, out = "photons.bin", macro;
  long seed = 12345;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "-c" && i + 1 < argc) config = argv[++i];
    else if (a == "-o" && i + 1 < argc) out = argv[++i];
    else if (a == "-s" && i + 1 < argc) seed = std::stol(argv[++i]);
    else macro = a;
  }
  if (config.empty()) {
    std::cerr << "usage: xamsopt -c config.json [-o out.bin] [-s seed] [macro.mac]\n";
    return 1;
  }
  Config::Get().Load(config);
  G4Random::setTheSeed(seed);

  auto* rm = G4RunManagerFactory::CreateRunManager(G4RunManagerType::Serial);
  rm->SetUserInitialization(new DetectorConstruction());
  rm->SetUserInitialization(new PhysicsList());
  rm->SetUserInitialization(new ActionInitialization());
  Output::Get().Open(out);

  auto* ui = G4UImanager::GetUIpointer();
  if (!macro.empty()) {
    ui->ApplyCommand("/control/execute " + macro);
  } else {
    auto* session = new G4UIExecutive(argc, argv);
    auto* vis = new G4VisExecutive("quiet");
    vis->Initialize();
    ui->ApplyCommand("/run/initialize");
    session->SessionStart();
    delete session;
    delete vis;
  }
  Output::Get().Close();
  delete rm;
  return 0;
}
