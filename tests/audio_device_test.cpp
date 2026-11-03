#include "audio_device.h"
#include <array>
#include <iostream>
int main() {
    for(unsigned rate:{44100u,48000u})for(unsigned requested:{0u,128u,256u,512u,1024u,2048u,4096u}) {
        snd_pcm_t* pcm=nullptr;
        int result=snd_pcm_open(&pcm,"null",SND_PCM_STREAM_PLAYBACK,SND_PCM_NONBLOCK);
        if(result>=0)result=configure_playback(pcm,rate,requested);
        snd_pcm_uframes_t buffer=0,period=0;
        if(result>=0)result=snd_pcm_get_params(pcm,&buffer,&period);
        if(result>=0&&(!buffer||!period||(requested&&buffer!=requested)))result=-EINVAL;
        std::array<short,512> silence{};
        if(result>=0&&requested&&period>buffer/2)result=-EINVAL;
        unsigned offset=0;
        while(result>=0&&offset<256){
            const auto count=snd_pcm_writei(pcm,silence.data()+offset*2,std::min<snd_pcm_uframes_t>(buffer,256-offset));
            if(count<=0){result=-EIO;break;}offset+=unsigned(count);
        }
        if(pcm)snd_pcm_close(pcm);
        if(result<0){std::cerr<<"rate="<<rate<<" buffer="<<requested<<": "<<snd_strerror(result)<<'\n';return 1;}
    }
}
