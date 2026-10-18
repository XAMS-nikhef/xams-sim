// XAMS Geant4 application (xams-sim): optical mode (default) and particle mode.
//   xamsg4 -c run/config.json -o run/photons.bin [-s seed] [-d] [-v] [macro.mac]          optical photons
//   xamsg4 -m particle -c config.json -o run/x/deposits.bin [-s seed] macro.mac           sources -> energy deposits
//     (particle mode: include/ParticleMode.hh; normally started by `xamssim g4 config/runs/<run>.yaml`)
// -d: records only for detected photons (every photon still counted in <out>.summary.json).
// Without a macro: interactive session with visualisation (Qt). -v: visualisation also in batch (offscreen images).
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
#include "ParticleMode.hh"
#include "PhotonActions.hh"
#include "PhysicsList.hh"
#include "SectionScan.hh"

int main(int argc, char** argv) {
  std::string config, out = "photons.bin", macro, mode = "optical";
  long seed = 12345;
  bool vis = false, detectedOnly = false;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "-c" && i + 1 < argc) config = argv[++i];
    else if (a == "-m" && i + 1 < argc) mode = argv[++i];
    else if (a == "-o" && i + 1 < argc) out = argv[++i];
    else if (a == "-s" && i + 1 < argc) seed = std::stol(argv[++i]);
    else if (a == "-v") vis = true;
    else if (a == "-d") detectedOnly = true;
    else macro = a;
  }
  if (config.empty()) {
    std::cerr << "usage: xamsg4 [-m optical|particle] -c config.json [-o out.bin] [-s seed] [-d] [-v] [macro.mac]\n";
    return 1;
  }
  if (mode != "optical" && mode != "particle") {
    std::cerr << "unknown mode '" << mode << "' (optical | particle)\n";
    return 1;
  }
  Config::Get().Load(config);
  Config::Get().SetMode(mode);
  G4Random::setTheSeed(seed);

  auto* rm = G4RunManagerFactory::CreateRunManager(G4RunManagerType::Serial);
  rm->SetUserInitialization(new DetectorConstruction());
  if (mode == "particle") {
    rm->SetUserInitialization(new ParticlePhysicsList());
    rm->SetUserInitialization(new ParticleActionInitialization());
    auto& o = DepositOutput::Get();
    o.Open(out);
    o.SetInfo("config", config);
    o.SetInfo("seed", std::to_string(seed));
    o.SetInfo("macro", macro);
    o.SetInfo("config_json", Config::Get().J().dump());
  } else {
    rm->SetUserInitialization(new PhysicsList());
    rm->SetUserInitialization(new ActionInitialization());
    Output::Get().Open(out, detectedOnly);
    Output::Get().SetInfo("config", config);
    Output::Get().SetInfo("seed", std::to_string(seed));
    Output::Get().SetInfo("macro", macro);
  }
  SectionScan scanner;  // /xamsg4/section

  auto* ui = G4UImanager::GetUIpointer();
  if (!macro.empty()) {
    G4VisExecutive* visExec = nullptr;
    if (vis) {
      visExec = new G4VisExecutive("quiet");
      visExec->Initialize();
    }
    ui->ApplyCommand("/control/execute " + macro);
    delete visExec;
  } else {
    auto* session = new G4UIExecutive(argc, argv);
    auto* vis = new G4VisExecutive("quiet");
    vis->Initialize();
    ui->ApplyCommand("/run/initialize");
    ui->ApplyCommand(mode == "particle" ? "/control/execute vis_particle.mac" : "/control/execute vis_interactive.mac");
    // optical viewer: the photon source of the scan it was started for (config vis_source, written by xamssim)
    const auto& cfg = Config::Get();
    if (mode == "optical" && cfg.Str("vis_source/shape", "") != "") {
      ui->ApplyCommand("/xamsg4/source/shape " + cfg.Str("vis_source/shape", "s2"));
      ui->ApplyCommand("/xamsg4/source/rmax " + std::to_string(cfg.Num("vis_source/rmax_mm", 30.)) + " mm");
    }
    session->SessionStart();
    delete session;
    delete vis;
  }
  if (mode == "particle") DepositOutput::Get().Close();
  else Output::Get().Close();
  delete rm;
  return 0;
}
