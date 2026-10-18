// Run configuration: the JSON written by optical/make_config.py (geometry, optics, liquid level).
#pragma once

#include <nlohmann/json.hpp>
#include <string>

class Config {
 public:
  static Config& Get();
  void Load(const std::string& path);
  const nlohmann::json& J() const { return fJson; }
  bool Loaded() const { return fLoaded; }
  // convenience: value at a '/'-separated path, e.g. "optics/lxe/refractive_index"; default if absent
  double Num(const std::string& path, double def) const;
  std::string Str(const std::string& path, const std::string& def) const;

 private:
  Config() = default;
  const nlohmann::json* Find(const std::string& path) const;
  nlohmann::json fJson;
  bool fLoaded = false;
};
