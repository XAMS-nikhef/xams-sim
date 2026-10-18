#include "Config.hh"

#include <G4Exception.hh>

#include <fstream>
#include <sstream>
#include <stdexcept>

Config& Config::Get() {
  static Config instance;
  return instance;
}

void Config::Load(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open config " + path);
  in >> fJson;
  fLoaded = true;
}

const nlohmann::json* Config::Find(const std::string& path) const {
  const nlohmann::json* node = &fJson;
  std::stringstream ss(path);
  std::string key;
  while (std::getline(ss, key, '/')) {
    if (node->is_object() && node->contains(key)) {
      node = &(*node)[key];
    } else if (node->is_array() && !key.empty() && std::isdigit(static_cast<unsigned char>(key[0]))) {
      size_t i = std::stoul(key);
      if (i >= node->size()) return nullptr;
      node = &(*node)[i];
    } else {
      return nullptr;
    }
  }
  return node;
}

double Config::Num(const std::string& path, double def) const {
  const auto* n = Find(path);
  return (n && n->is_number()) ? n->get<double>() : def;
}

double Config::Req(const std::string& path) const {
  const auto* n = Find(path);
  if (!n || !n->is_number())
    G4Exception("Config::Req", "CONF010", FatalException,
                ("required config value '" + path + "' missing (geometry.yaml / materials.yaml / state)").c_str());
  return n->get<double>();
}

std::string Config::Str(const std::string& path, const std::string& def) const {
  const auto* n = Find(path);
  return (n && n->is_string()) ? n->get<std::string>() : def;
}
