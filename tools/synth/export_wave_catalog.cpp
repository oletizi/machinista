// Export the exact built-in tables for offline comparison; never used at runtime.
#include "audio/synth_waves.hpp"
#include <filesystem>
#include <string>
int main(int argc,char**argv){
 if(argc==4&&std::string(argv[1])=="--prepare"){
  auto wave=maschine::SynthWave::load(argv[2]);wave->save(argv[3]);return 0;
 }
 if(argc!=2)return 2;std::filesystem::create_directories(argv[1]);
 const auto& bank=maschine::SynthFactory::get();
 for(unsigned i=0;i<bank.waves.size();++i)bank.waves[i].save(std::string(argv[1])+"/"+std::to_string(i)+".mwave");
}
