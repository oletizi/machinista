#include "audio/hardware_profile.hpp"
#include <cassert>
#include <string>
int main(int argc,char** argv){assert(argc==2);const auto& p=maschine::hardware_profile();if(std::string(argv[1])=="pi3b-sampler"){assert(!p.lv2&&!p.synth);assert(p.sampler_voices==16);assert(p.sample_memory==192u*1024u*1024u);}else{assert(p.lv2&&p.synth);assert(p.sampler_voices==64);assert(p.sample_memory==512u*1024u*1024u);} }
