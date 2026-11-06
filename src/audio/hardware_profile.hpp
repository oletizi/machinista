#pragma once
#include <cstddef>
#include <cstdlib>
#include <fstream>
#include <string>
#include <stdexcept>
namespace maschine {
struct HardwareProfile {
 bool lv2=true,synth=true;unsigned sampler_voices=64;std::size_t sample_memory=512u*1024u*1024u;
};
inline const HardwareProfile& hardware_profile(){
 static const HardwareProfile value=[] {
  std::string id;const char* env=std::getenv("MACHINISTA_HARDWARE_PROFILE");
  if(env)id=env;else {std::ifstream f("/etc/machinista/hardware-profile");if(f)std::getline(f,id);else id="standard";}
  if(id=="standard")return HardwareProfile{};
  if(id=="pi3b-sampler")return HardwareProfile{false,false,16,192u*1024u*1024u};
  throw std::runtime_error("Unknown Machinista hardware profile");
 }();return value;
}
}
