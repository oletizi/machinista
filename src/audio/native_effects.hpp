#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <ostream>
#include <string_view>
#include <vector>

namespace maschine {
// Original insert DSP. Storage is allocated by the control-thread constructor;
// the audio block performs no allocation, locking, file access or shared state.
class NativeEffect {
public:
    enum Kind {EQ,COMPRESSOR,LIMITER,TRANSIENT,REVERB,DELAY,CHORUS,FLANGER,PHASER,TREMOLO,VIBRATO,AUTOPAN};
    struct Port {const char* symbol;const char* name;float lo,hi,initial;bool logarithmic,integer;};
    struct Spec {const char* id;const char* uri;const char* name;const Port* ports;unsigned count;};
    using Params=std::array<float,32>;
#include "audio/native_effect_specs.inc"
    static int identify(std::string_view uri){for(unsigned i=0;i<specs.size();++i)if(uri==specs[i].uri)return int(i);return -1;}
    static void inventory(std::ostream& o){
        for(unsigned k=0;k<specs.size();++k){const auto& s=specs[k];if(k)o<<',';
            o<<"{\"uri\":\""<<s.uri<<"\",\"name\":\""<<s.name<<"\",\"kind\":\"EFFECT\",\"builtin\":true,\"supported\":true,\"sidechain\":false,\"bundle\":\"builtin:"<<s.id<<"\",\"binary\":\"\",\"ports\":[";
            for(unsigned i=0;i<s.count;++i){const auto& p=s.ports[i];if(i)o<<',';o<<"{\"index\":"<<i<<",\"symbol\":\""<<p.symbol<<"\",\"name\":\""<<p.name<<"\",\"min\":"<<p.lo<<",\"max\":"<<p.hi<<",\"default\":"<<p.initial<<",\"integer\":"<<(p.integer?"true":"false")<<",\"toggle\":false,\"log\":"<<(p.logarithmic?"true":"false")<<'}';}
            o<<"]}";
        }
    }
    static Params defaults(unsigned kind){Params p{};for(unsigned i=0;i<specs[kind].count;++i)p[i]=specs[kind].ports[i].initial;return p;}
private:
    static constexpr float pi=3.14159265358979323846f;
    static float finite(float x){return std::isfinite(x)?x:0;}
    static float db(float x){return std::pow(10.f,x*.05f);}
    static float zap(float x){return std::isfinite(x)&&std::abs(x)>1e-20f?x:0;}
    struct Ring {
        std::vector<float> data;unsigned pos=0;
        explicit Ring(unsigned n=8):data(std::max(8u,n),0){}
        float read(float delay)const{
            delay=std::clamp(delay,1.f,float(data.size()-2));
            // Double precision keeps a tiny negative position below size after
            // wrapping. Float rounding can otherwise produce an out-of-bounds
            // index exactly at the end of the ring during modulation.
            double x=double(pos)-double(delay);if(x<0)x+=double(data.size());
            const unsigned i=unsigned(x)%data.size(),j=(i+1)%data.size();const float f=float(x-std::floor(x));return data[i]+f*(data[j]-data[i]);
        }
        void push(float x){data[pos]=zap(x);if(++pos==data.size())pos=0;}
    };
    struct Biquad {
        std::array<float,5> c{1,0,0,0,0},target{1,0,0,0,0};std::array<float,2> z1{},z2{};
        void set(unsigned type,float rate,float hz,float gain,float q=.7071068f){
            hz=std::clamp(hz,5.f,rate*.45f);const float w=2*pi*hz/rate,cs=std::cos(w),sn=std::sin(w),A=std::pow(10.f,gain/40),alpha=sn/(2*std::max(.2f,q));
            float b0=1,b1=0,b2=0,a0=1,a1=0,a2=0;
            if(type==0){b0=1+alpha*A;b1=-2*cs;b2=1-alpha*A;a0=1+alpha/A;a1=-2*cs;a2=1-alpha/A;}
            else if(type==1||type==2){const float beta=sn*std::sqrt(2*A),ap=A+1,am=A-1;
                if(type==1){b0=A*(ap-am*cs+beta);b1=2*A*(am-ap*cs);b2=A*(ap-am*cs-beta);a0=ap+am*cs+beta;a1=-2*(am+ap*cs);a2=ap+am*cs-beta;}
                else{b0=A*(ap+am*cs+beta);b1=-2*A*(am+ap*cs);b2=A*(ap+am*cs-beta);a0=ap-am*cs+beta;a1=2*(am-ap*cs);a2=ap-am*cs-beta;}}
            else{b0=(1+cs)*.5f;b1=-(1+cs);b2=b0;a0=1+alpha;a1=-2*cs;a2=1-alpha;}
            target={b0/a0,b1/a0,b2/a0,a1/a0,a2/a0};
        }
        void step(float smooth){for(unsigned i=0;i<5;++i)c[i]+=smooth*(target[i]-c[i]);}
        float run(float x,unsigned ch){float y=c[0]*x+z1[ch];z1[ch]=zap(c[1]*x-c[3]*y+z2[ch]);z2[ch]=zap(c[2]*x-c[4]*y);return finite(y);}
    };
    unsigned kind_;float rate_,smooth_,engage_=1,output_=1,mix_=1;
    Params values_{};std::array<Biquad,5> eq_{};
    Ring l_,r_;std::array<Ring,8> room_;std::array<Ring,8> diffuser_;
    std::array<float,8> room_lp_{},room_read_delays_{};std::array<float,4> stage_weights_{0,1,0,0};std::array<float,2> tone_{},hp_last_{},hp_state_{},mod_feedback_{};
    std::array<std::array<float,12>,2> allpass_{};
    float detector_=0,reduction_=0,fast_=0,slow_=0,shape_gain_=1;
    double phase_=0,age_=0;float delay_frames_=1;
    std::vector<float> peak_values_;std::vector<uint64_t> peak_indices_;unsigned peak_head_=0,peak_tail_=0;uint64_t frame_=0;
    unsigned latency_=0;
    static float seconds(unsigned kind){return kind==DELAY?12.1f:kind==REVERB?.25f:kind==CHORUS?.07f:kind==FLANGER||kind==VIBRATO?.03f:.005f;}
    float hp(float x,unsigned ch,float coef){hp_state_[ch]=zap(coef*(hp_state_[ch]+x-hp_last_[ch]));hp_last_[ch]=x;return hp_state_[ch];}
    static float soft(float x,float drive){const float d=1+drive*4;return std::tanh(x*d)/d;}
    static float wave(double phase,int shape){phase-=std::floor(phase);if(shape==1)return float(1-4*std::abs(phase-.5));if(shape==2)return phase<.5?1.f:-1.f;return std::sin(float(2*pi*phase));}
    static float synced(float bpm,float division){constexpr float beats[]{.0625f,.125f,.25f,.5f,.75f,1,1.5f,2,3,4};return 60/std::clamp(bpm,20.f,400.f)*beats[std::clamp(int(std::round(division)),0,9)];}
public:
    NativeEffect(unsigned kind,float rate):kind_(kind),rate_(std::clamp(rate,8000.f,192000.f)),smooth_(1-std::exp(-1/(rate_*.005f))),values_(defaults(kind)),l_(unsigned(rate_*seconds(kind))+8),r_(unsigned(rate_*seconds(kind))+8){
        if(kind==REVERB)for(unsigned i=0;i<8;++i){room_[i]=Ring(unsigned(rate_*.25f)+8);diffuser_[i]=Ring(unsigned(rate_*.025f)+8);}
        latency_=kind==LIMITER?std::max(1u,unsigned(std::round(rate_*.001f))):kind==VIBRATO?unsigned(std::round(rate_*.005f)):0;
        peak_values_.resize(latency_+3);peak_indices_.resize(latency_+3);
        delay_frames_=rate_*.375f;
        mix_=kind==LIMITER?1:values_[kind==EQ?11:kind==COMPRESSOR?7:kind==TRANSIENT?5:kind==REVERB||kind==DELAY?7:kind==CHORUS?6:kind==FLANGER?5:kind==PHASER?6:kind==TREMOLO?6:kind==VIBRATO?5:6];
    }
    unsigned latency()const{return latency_;}
    unsigned parameter_count()const{return specs[kind_].count;}
    void process(float* left,float* right,const Params& raw,bool bypass=false,float bpm=120,unsigned count=256){
        Params p{};const auto& spec=specs[kind_];
        for(unsigned i=0;i<spec.count;++i){const auto& port=spec.ports[i];p[i]=std::clamp(std::isfinite(raw[i])?raw[i]:port.initial,port.lo,port.hi);if(port.integer)p[i]=std::round(p[i]);}
        if(kind_==EQ){eq_[0].set(1,rate_,p[0],p[1]);eq_[1].set(0,rate_,p[2],p[3],p[4]);eq_[2].set(0,rate_,p[5],p[6],p[7]);eq_[3].set(2,rate_,p[8],p[9]);if(p[10]>0)eq_[4].set(3,rate_,p[10],0);else eq_[4].target={1,0,0,0,0};}
        const int mi=kind_==LIMITER?-1:kind_==EQ?11:kind_==COMPRESSOR?7:kind_==TRANSIENT?5:kind_==REVERB||kind_==DELAY?7:kind_==CHORUS?6:kind_==FLANGER?5:kind_==PHASER?6:kind_==TREMOLO?6:kind_==VIBRATO?5:6;
        const float output=kind_==LIMITER?1:db(p[kind_==DELAY?10:mi+1]);
        const float comp_attack=std::exp(-1/(std::max(.1f,p[2])*rate_*.001f)),comp_release=std::exp(-1/(std::max(1.f,p[3])*rate_*.001f));
        std::array<float,8> room_delays{},room_gains{};
        if(kind_==REVERB){constexpr float lengths[]{.0297f,.0371f,.0411f,.0437f,.0531f,.0611f,.0713f,.0797f};const int type=int(p[0]);const float scale=(.45f+p[1]*.9f)*(type==0?.65f:type==1?1.25f:.8f);for(unsigned i=0;i<8;++i){room_delays[i]=lengths[i]*scale*rate_;room_gains[i]=std::pow(10.f,-3*lengths[i]*scale/p[2]);}}
        const float damping=kind_==REVERB?1-std::exp(-2*pi*std::min(p[4],rate_*.45f)/rate_):1;
        const float detector_hp=kind_==COMPRESSOR&&p[6]>0?std::exp(-2*pi*p[6]/rate_):0;
        const float rms_sense=1-std::exp(-1/(rate_*.005f));
        const float transient_fast=kind_==TRANSIENT?std::exp(-1/(p[3]*.001f*rate_)):0,transient_slow=kind_==TRANSIENT?std::exp(-1/(p[4]*.001f*rate_)):0;
        const float verb_hp=kind_==REVERB?std::exp(-2*pi*p[5]/rate_):0;
        const float color_coefficient=(kind_==DELAY||kind_==CHORUS)?1-std::exp(-2*pi*std::min(p[5],rate_*.45f)/rate_):1;
        const float release_limit=kind_==LIMITER?std::exp(-1/(p[1]*.001f*rate_)):0;
        for(unsigned n=0;n<count;++n){
            for(unsigned i=0;i<spec.count;++i)values_[i]+=smooth_*(p[i]-values_[i]);
            const auto& v=values_;const float a=std::clamp(finite(left[n]),-64.f,64.f),b=std::clamp(finite(right[n]),-64.f,64.f);float x=a,y=b,dry_a=a,dry_b=b;
            engage_+=smooth_*((bypass?0.f:1.f)-engage_);if(engage_<1e-6f)engage_=0;if(engage_>1-1e-6f)engage_=1;
            mix_+=smooth_*((mi<0?1:p[mi])-mix_);output_+=smooth_*(output-output_);
            if(kind_==EQ){for(auto& f:eq_){f.step(smooth_);x=f.run(x,0);y=f.run(y,1);}}
            else if(kind_==COMPRESSOR){
                const float kl=detector_hp?hp(a,0,detector_hp):a,kr=detector_hp?hp(b,1,detector_hp):b;
                const float energy=std::max(kl*kl,kr*kr);detector_+= rms_sense*(energy-detector_);
                const float level=10*std::log10(std::max(detector_,1e-12f)),over=level-v[0],slope=1-1/v[1],knee=v[4];
                float target=0;if(knee>0&&over>-knee*.5f&&over<knee*.5f)target=slope*(over+knee*.5f)*(over+knee*.5f)/(2*knee);else if(over>0)target=slope*over;
                const float c=target>reduction_?comp_attack:comp_release;reduction_=target+c*(reduction_-target);const float g=db(v[5]-reduction_);x=a*g;y=b*g;
            }else if(kind_==LIMITER){
                const float drive=db(v[2]),peak=std::max(std::abs(a),std::abs(b))*drive;const unsigned size=peak_values_.size();
                while(peak_head_!=peak_tail_&&peak_indices_[peak_head_]+latency_<frame_)peak_head_=(peak_head_+1)%size;
                while(peak_head_!=peak_tail_){unsigned last=(peak_tail_+size-1)%size;if(peak_values_[last]>peak)break;peak_tail_=last;}
                peak_values_[peak_tail_]=peak;peak_indices_[peak_tail_]=frame_;peak_tail_=(peak_tail_+1)%size;
                const float ceiling=db(p[0]),maximum=peak_values_[peak_head_],target=maximum>ceiling?ceiling/maximum:1;
                if(target<shape_gain_)shape_gain_=target;else shape_gain_=target+release_limit*(shape_gain_-target);
                x=l_.read(float(latency_))*drive*shape_gain_;y=r_.read(float(latency_))*drive*shape_gain_;dry_a=l_.read(float(latency_));dry_b=r_.read(float(latency_));l_.push(a);r_.push(b);++frame_;
                x=std::clamp(x,-ceiling,ceiling);y=std::clamp(y,-ceiling,ceiling);
            }else if(kind_==TRANSIENT){
                const float input=std::max(std::abs(a),std::abs(b));const float cf=transient_fast,cs=transient_slow;
                fast_=input+cf*(fast_-input);slow_=input+cs*(slow_-input);
                const float attack=std::clamp((fast_-slow_)/(slow_+.005f)*(1+v[2]*3),0.f,1.f),tail=slow_>1e-6f?1-attack:0;
                const float gain=db(v[0]*18*attack+v[1]*12*tail);shape_gain_+=smooth_*(gain-shape_gain_);x=a*shape_gain_;y=b*shape_gain_;
            }else if(kind_==REVERB){
                const float highpass=verb_hp;float in_l=hp(a,0,highpass),in_r=hp(b,1,highpass);
                const float predelay=std::max(1.f,v[3]*.001f*rate_);const float dl=l_.read(predelay),dr=r_.read(predelay);l_.push(in_l);r_.push(in_r);in_l=v[3]<.05f?in_l:dl;in_r=v[3]<.05f?in_r:dr;
                constexpr float ap[]{.0047f,.0061f,.0091f,.0127f};const float g=.15f+v[9]*.6f;
                for(unsigned j=0;j<4;++j){float d=diffuser_[j].read(ap[j]*rate_);float z=d-g*in_l;diffuser_[j].push(in_l+g*z);in_l=z;d=diffuser_[j+4].read((ap[j]+.0007f)*rate_);z=d-g*in_r;diffuser_[j+4].push(in_r+g*z);in_r=z;}
                float sum=0;for(unsigned i=0;i<8;++i){if(room_read_delays_[i]==0)room_read_delays_[i]=room_delays[i];room_read_delays_[i]+=.0005f*(room_delays[i]-room_read_delays_[i]);const float value=room_[i].read(room_read_delays_[i]);room_lp_[i]=zap(room_lp_[i]+damping*(value-room_lp_[i]));sum+=room_lp_[i];}
                for(unsigned i=0;i<8;++i){const float reflected=sum*.25f-room_lp_[i];const float input=(i%2?in_r:in_l)*.22f;room_[i].push(input+reflected*room_gains[i]);}
                x=(room_lp_[0]+room_lp_[2]-room_lp_[4]+room_lp_[6])*.4f;y=(room_lp_[1]+room_lp_[3]-room_lp_[5]+room_lp_[7])*.4f;
                const float mid=(x+y)*.5f,side=(x-y)*.5f*v[6];x=mid+side;y=mid-side;
            }else if(kind_==DELAY){
                const bool sync=p[1]>=.5f;const float target=(sync?synced(bpm,p[2]):v[0]*.001f)*rate_;
                delay_frames_+=.0008f*(std::clamp(target,1.f,float(l_.data.size()-4))-delay_frames_);
                const int mode=int(p[4]);const float flutter=(mode>=2?std::sin(float(age_*.81*2*pi))*v[9]*.0008f*rate_:0);
                x=l_.read(delay_frames_+flutter);y=r_.read(delay_frames_-flutter);
                const float c=color_coefficient;tone_[0]+=c*(x-tone_[0]);tone_[1]+=c*(y-tone_[1]);x=tone_[0];y=tone_[1];
                float fl=mode>=2?soft(x,v[8]):x,fr=mode>=2?soft(y,v[8]):y;
                const bool ping=mode==1||mode==3;const float il=ping?(a+b)*.5f:a,ir=ping?0:b;
                l_.push(il+v[3]*(ping?fr:fl));r_.push(ir+v[3]*(ping?fl:fr));
                const float mid=(x+y)*.5f,side=(x-y)*.5f*v[6];x=mid+side;y=mid-side;
            }else{
                float hz=v[0];if((kind_==TREMOLO||kind_==VIBRATO||kind_==AUTOPAN)&&p[3]>=.5f)hz=1/synced(bpm,p[4]);
                const float stereo=kind_==CHORUS?v[4]*.25f:kind_==FLANGER?v[4]/360:kind_==PHASER?v[5]/360:kind_==TREMOLO?v[5]/360:kind_==VIBRATO?v[2]/360:0;
                const float wl=wave(phase_,0),wr=wave(phase_+stereo,0);
                if(kind_==CHORUS){
                    x=y=0;for(unsigned i=0;i<3;++i){const float angle=float(i)/3;const float dl=(v[2]+v[1]*4*wave(phase_+angle,0))*.001f*rate_,dr=(v[2]+v[1]*4*wave(phase_+angle+stereo,0))*.001f*rate_;x+=l_.read(dl)/3;y+=r_.read(dr)/3;}
                    const float c=color_coefficient;tone_[0]+=c*(x-tone_[0]);tone_[1]+=c*(y-tone_[1]);x=tone_[0];y=tone_[1];l_.push(a+x*v[3]);r_.push(b+y*v[3]);
                }else if(kind_==FLANGER){x=l_.read((v[2]+v[1]*1.9f*wl)*.001f*rate_);y=r_.read((v[2]+v[1]*1.9f*wr)*.001f*rate_);l_.push(a+x*v[3]);r_.push(b+y*v[3]);}
                else if(kind_==PHASER){
                    const unsigned chosen=std::clamp(int(p[4]),0,3);for(unsigned i=0;i<4;++i)stage_weights_[i]+=smooth_*((i==chosen?1.f:0.f)-stage_weights_[i]);
                    for(unsigned ch=0;ch<2;++ch){float value=(ch?b:a)+mod_feedback_[ch]*v[3];const float f=std::clamp(v[2]*std::pow(2.f,v[1]*2.5f*(ch?wr:wl)),30.f,rate_*.4f),t=std::tan(pi*f/rate_),g=(1-t)/(1+t);
                        float taps=0;for(unsigned i=0;i<12;++i){const float z=-g*value+allpass_[ch][i];allpass_[ch][i]=zap(value+g*z);value=z;if(i==3)taps+=value*stage_weights_[0];else if(i==5)taps+=value*stage_weights_[1];else if(i==7)taps+=value*stage_weights_[2];else if(i==11)taps+=value*stage_weights_[3];}value=taps;
                        mod_feedback_[ch]=finite(value);if(ch)y=value;else x=value;}
                }else if(kind_==VIBRATO){dry_a=l_.read(float(latency_));dry_b=r_.read(float(latency_));x=l_.read(float(latency_)+v[1]*rate_*.004f*wl);y=r_.read(float(latency_)+v[1]*rate_*.004f*wr);l_.push(a);r_.push(b);}
                else if(kind_==TREMOLO){x=a*(1-v[1]+v[1]*(wave(phase_,int(p[2]))*.5f+.5f));y=b*(1-v[1]+v[1]*(wave(phase_+stereo,int(p[2]))*.5f+.5f));}
                else{const float pan=v[1]*wave(phase_+v[5],int(p[2]));x=a*std::sqrt(std::max(0.f,1-pan));y=b*std::sqrt(std::max(0.f,1+pan));}
                phase_+=hz/rate_;phase_-=std::floor(phase_);
            }
            const float normal_l=(dry_a+(finite(x)-dry_a)*mix_)*output_,normal_r=(dry_b+(finite(y)-dry_b)*mix_)*output_;
            left[n]=finite(a+(normal_l-a)*engage_);right[n]=finite(b+(normal_r-b)*engage_);age_+=1/rate_;
        }
    }
};
}
