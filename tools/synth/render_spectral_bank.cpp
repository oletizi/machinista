// Offline audit uses the exact synth and native insert DSP, without audio hardware.
#include "audio/synth.hpp"
#include "audio/native_effects.hpp"
#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <vector>
struct Event {int note=60,velocity=0,status=0,data1=0,data2=0;unsigned frame=0,channel=0;};
using Synth=maschine::NativeSynth;using FX=maschine::NativeEffect;
void u16(std::ostream&o,unsigned n){o.put(n&255);o.put((n>>8)&255);}void u32(std::ostream&o,unsigned n){u16(o,n);u16(o,n>>16);}
int main(int argc,char**argv){
 if(argc<3)return 2;const bool solo=std::string(argv[2])=="solo",stress=std::string(argv[2])=="stress";const unsigned rate=argc>3?std::stoul(argv[3]):44100;
 const double seconds=solo?2.5:5.;std::filesystem::create_directories(argv[1]);Synth::Params p;std::string name;bool mono;
 while(std::cin>>std::quoted(name)>>mono){
  for(float&v:p)if(!(std::cin>>v))return 3;std::array<std::string,4>paths;for(auto&path:paths)if(!(std::cin>>std::quoted(path)))return 4;
  unsigned fx_count;if(!(std::cin>>fx_count)||fx_count>3)return 5;std::vector<std::unique_ptr<FX>> fx;std::vector<FX::Params> params;
  for(unsigned j=0;j<fx_count;++j){unsigned k;std::cin>>k;if(k!=FX::CHORUS&&k!=FX::DELAY&&k!=FX::REVERB)return 6;auto values=FX::defaults(k);for(float&v:values)if(!(std::cin>>v))return 7;fx.push_back(std::make_unique<FX>(k,float(rate)));params.push_back(values);}
  Synth synth(rate);for(unsigned o=0;o<4;++o)if(!paths[o].empty())synth.set_wave(o,paths[o]);
  std::array<float,256> l{},r{};std::vector<int> notes=solo?std::vector<int>{60}:mono?std::vector<int>{48}:(stress?std::vector<int>{36,43,48,55,60,64,67,72}:std::vector<int>{48,55,60,64});
  const unsigned total=unsigned(rate*seconds),start=rate/10,end=start+(solo?rate*14/10:rate*22/10);std::vector<int16_t> pcm;pcm.reserve(total*2);
  double peak=0,sum=0,max_ms=0,max_cpu_ms=0;unsigned overruns=0,cpu_overruns=0,clipped=0,blocks=0;
  for(unsigned frame=0;frame<total;frame+=256){unsigned frames=std::min(256u,total-frame);Event events[16];unsigned count=0;
   for(auto when:{start,end})if(when>=frame&&when<frame+frames)for(int note:notes)events[count++]={note,when==start?(stress?127:100):0,0,0,0,when-frame,0};
   auto began=std::chrono::steady_clock::now();auto cpu_began=std::clock();synth.process(l.data(),r.data(),events,count,p,120,false,frames);
   for(unsigned j=0;j<fx.size();++j)fx[j]->process(l.data(),r.data(),params[j],false,120,frames);
   const double cpu_ms=1000.0*(std::clock()-cpu_began)/CLOCKS_PER_SEC;max_cpu_ms=std::max(max_cpu_ms,cpu_ms);if(cpu_ms>256000./rate)++cpu_overruns;
   const double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-began).count();max_ms=std::max(max_ms,ms);if(ms>256000./rate)++overruns;++blocks;
   for(unsigned i=0;i<frames;++i)for(float value:{l[i],r[i]}){if(!std::isfinite(value))return 8;peak=std::max(peak,double(std::abs(value)));sum+=value*value;clipped+=std::abs(value)>=1;pcm.push_back(int16_t(std::lround(std::clamp(value,-.99996f,.99996f)*32767)));}
  }
  std::string stem=name;for(char&c:stem)if(c==' ')c='-';std::string file=std::string(argv[1])+"/"+stem+"-"+std::to_string(rate)+".wav";
  std::ofstream out(file,std::ios::binary);out.write("RIFF",4);u32(out,36+pcm.size()*2);out.write("WAVEfmt ",8);u32(out,16);u16(out,1);u16(out,2);u32(out,rate);u32(out,rate*4);u16(out,4);u16(out,16);out.write("data",4);u32(out,pcm.size()*2);out.write(reinterpret_cast<char*>(pcm.data()),pcm.size()*2);
  std::cout<<"{\"name\":"<<std::quoted(name)<<",\"rate\":"<<rate<<",\"peak\":"<<peak<<",\"rms\":"<<std::sqrt(sum/(2*total))<<",\"clipped\":"<<clipped<<",\"max_ms\":"<<max_ms<<",\"max_cpu_ms\":"<<max_cpu_ms<<",\"cpu_overruns\":"<<cpu_overruns<<",\"blocks\":"<<blocks<<",\"overruns\":"<<overruns<<"}"<<std::endl;
 }
}
