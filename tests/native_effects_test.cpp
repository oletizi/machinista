#include "audio/native_effects.hpp"
#include <array>
#include <cassert>
#include <atomic>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <new>
#include <vector>
using FX=maschine::NativeEffect;
static std::atomic<unsigned> allocations{0};
void* operator new(std::size_t n){allocations.fetch_add(1);if(void* p=std::malloc(n))return p;throw std::bad_alloc();}
void operator delete(void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}
struct Stereo {std::vector<float> l,r;};
Stereo render(FX& fx,FX::Params p,unsigned frames,float rate,bool impulse=false,float hz=440,float amplitude=.2f,bool bypass=false,float bpm=120){
 Stereo result;result.l.reserve(frames);result.r.reserve(frames);
 for(unsigned first=0;first<frames;first+=256){std::array<float,256> l{},r{};unsigned count=std::min(256u,frames-first);
  for(unsigned i=0;i<count;++i){l[i]=impulse?(first+i==0?amplitude:0):amplitude*std::sin(6.28318530718f*hz*(first+i)/rate);r[i]=l[i]*.5f;}
  unsigned before=allocations.load();fx.process(l.data(),r.data(),p,bypass,bpm,count);assert(allocations.load()==before);
  for(unsigned i=0;i<count;++i){assert(std::isfinite(l[i])&&std::isfinite(r[i]));assert(std::abs(l[i])<100);result.l.push_back(l[i]);result.r.push_back(r[i]);}
 }return result;
}
float energy(const std::vector<float>& x,unsigned first,unsigned end){float sum=0;for(unsigned i=first;i<std::min(end,unsigned(x.size()));++i)sum+=x[i]*x[i];return sum;}
void warm(FX& e,FX::Params p,float rate){render(e,p,unsigned(rate*.4f),rate,false,440,0);}
int main(){
 for(float rate:{44100.f,48000.f}){
  for(unsigned kind=0;kind<12;++kind){FX e(kind,rate);auto p=FX::defaults(kind);auto a=render(e,p,unsigned(rate*.15f),rate);(void)a;
   for(unsigned i=0;i<e.parameter_count();++i)p[i]=(i%3==0?std::numeric_limits<float>::quiet_NaN():i%3==1?1e20f:-1e20f);
   render(e,p,4096,rate);auto normal=FX::defaults(kind);warm(e,normal,rate);render(e,normal,4096,rate,false,440,.3,true);
  }
  // Neutral EQ and zero transient controls preserve the input, including stereo.
  for(unsigned kind:{unsigned(FX::EQ),unsigned(FX::TRANSIENT)}){FX e(kind,rate);auto p=FX::defaults(kind);warm(e,p,rate);auto a=render(e,p,2048,rate);
   for(unsigned i=0;i<a.l.size();++i){assert(std::abs(a.l[i]-.2f*std::sin(6.28318530718f*440*i/rate))<1e-4);assert(std::abs(a.l[i]*.5f-a.r[i])<1e-5);}}
  FX boost(FX::EQ,rate),cut(FX::EQ,rate);auto p=FX::defaults(FX::EQ);p[2]=1000;p[3]=12;p[4]=1;warm(boost,p,rate);auto up=render(boost,p,unsigned(rate),rate,false,1000,.1);p[3]=-12;warm(cut,p,rate);auto down=render(cut,p,unsigned(rate),rate,false,1000,.1);assert(energy(up.l,rate/2,rate)/energy(down.l,rate/2,rate)>200);
  FX comp(FX::COMPRESSOR,rate);p=FX::defaults(FX::COMPRESSOR);p[0]=-20;p[1]=4;p[2]=1;p[3]=80;p[4]=0;warm(comp,p,rate);auto squeezed=render(comp,p,unsigned(rate),rate,false,1000,.8);assert(energy(squeezed.l,rate/2,rate)<.04f*energy(std::vector<float>(unsigned(rate),.8),rate/2,rate));
  for(unsigned i=0;i<squeezed.l.size();++i)assert(std::abs(squeezed.l[i]*.5f-squeezed.r[i])<1e-5);
  FX limiter(FX::LIMITER,rate);p=FX::defaults(FX::LIMITER);p[0]=-3;auto limited=render(limiter,p,unsigned(rate),rate,false,997,4);for(float v:limited.l)assert(std::abs(v)<=std::pow(10.f,-3.f/20)+1e-6);
  FX timing(FX::LIMITER,rate);p=FX::defaults(FX::LIMITER);auto hit=render(timing,p,256,rate,true,0,.2);for(unsigned i=0;i<timing.latency();++i)assert(hit.l[i]==0);assert(std::abs(hit.l[timing.latency()]-.2f)<1e-6);
  FX delay(FX::DELAY,rate);p=FX::defaults(FX::DELAY);p[0]=100;p[1]=0;p[3]=.5;p[4]=1;p[7]=1;warm(delay,p,rate);auto echoes=render(delay,p,unsigned(rate*.5f),rate,true,0,1);
  auto window=[&](const std::vector<float>& v,float t){return energy(v,unsigned((t-.002f)*rate),unsigned((t+.004f)*rate));};
  assert(window(echoes.l,.1f)>.15f&&window(echoes.r,.1f)<1e-5);assert(window(echoes.r,.2f)>.02f);
  for(int type=0;type<3;++type){FX verb(FX::REVERB,rate);p=FX::defaults(FX::REVERB);p[0]=type;p[7]=1;warm(verb,p,rate);auto tail=render(verb,p,unsigned(rate*3),rate,true,0,1);assert(energy(tail.l,unsigned(.08*rate),unsigned(rate))>1e-5);assert(energy(tail.l,unsigned(rate*2),unsigned(rate*3))<energy(tail.l,unsigned(.1*rate),unsigned(rate))*.2f);}
  FX pan(FX::AUTOPAN,rate);p=FX::defaults(FX::AUTOPAN);p[1]=1;warm(pan,p,rate);
  for(unsigned b=0;b<100;++b){std::array<float,256> l,r;l.fill(1);r.fill(1);pan.process(l.data(),r.data(),p);for(unsigned i=0;i<256;++i)assert(std::abs(l[i]*l[i]+r[i]*r[i]-2)<1e-4);}
  FX trem(FX::TREMOLO,rate);p=FX::defaults(FX::TREMOLO);p[0]=2;p[1]=1;warm(trem,p,rate);float low=1,high=0;
  for(unsigned b=0;b<100;++b){std::array<float,256> l,r;l.fill(1);r.fill(1);trem.process(l.data(),r.data(),p);for(float v:l){low=std::min(low,v);high=std::max(high,v);}}assert(low<.01&&high>.99);
  FX vib(FX::VIBRATO,rate);p=FX::defaults(FX::VIBRATO);p[1]=0;warm(vib,p,rate);auto v=render(vib,p,512,rate,true,0,.5);assert(std::abs(v.l[vib.latency()]-.5)<1e-4);
  // Every advertised output parameter scales audio, including Delay's page 2.
  for(unsigned kind=0;kind<12;++kind){int port=-1;for(unsigned i=0;i<FX::specs[kind].count;++i)if(std::string_view(FX::specs[kind].ports[i].symbol)=="output")port=int(i);if(port<0)continue;
   FX one(kind,rate),two(kind,rate);auto p1=FX::defaults(kind),p2=p1;p2[port]=6;warm(one,p1,rate);warm(two,p2,rate);auto a=render(one,p1,unsigned(rate),rate),b=render(two,p2,unsigned(rate),rate);
   float difference=0;for(unsigned i=0;i<a.l.size();++i)difference=std::max(difference,std::abs(b.l[i]-a.l[i]*std::pow(10.f,.3f)));assert(difference<.001f);}
  // Bypass becomes the exact live input, without hidden effect latency.
  for(unsigned kind=0;kind<12;++kind){FX e(kind,rate);p=FX::defaults(kind);render(e,p,unsigned(rate*.2),rate,false,440,0,true);auto dry=render(e,p,1024,rate,false,440,.2,true);for(unsigned i=0;i<1024;++i)assert(std::abs(dry.l[i]-.2f*std::sin(6.28318530718f*440*i/rate))<1e-6);}
 }
 std::cout<<"12 native effects: no RT allocations; EQ response, stereo dynamics, limiter ceiling/latency, ping-pong echoes, reverb tails, modulation and bypass at 44.1/48 kHz passed\n";
}
