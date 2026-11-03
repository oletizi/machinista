#pragma once
#include <alsa/asoundlib.h>
#include <algorithm>

inline bool valid_playback_buffer(unsigned frames) {
    return frames==0 || frames==128 || frames==256 || frames==512 || frames==1024 || frames==2048 || frames==4096;
}

// Buffer choice changes ALSA queue size; DSP / LV2 blocks remain 256 frames.
inline int configure_playback(snd_pcm_t* pcm, unsigned rate, unsigned frames, unsigned channels=2) {
    if (!channels || channels>64 || !valid_playback_buffer(frames)) return -EINVAL;
    if (!frames) return snd_pcm_set_params(pcm, SND_PCM_FORMAT_S16_LE,
        SND_PCM_ACCESS_RW_INTERLEAVED, channels, rate, 1, 20000);
    snd_pcm_hw_params_t* hw; snd_pcm_hw_params_alloca(&hw);
    int error = snd_pcm_hw_params_any(pcm, hw);
    if (error >= 0) error = snd_pcm_hw_params_set_access(pcm, hw, SND_PCM_ACCESS_RW_INTERLEAVED);
    if (error >= 0) error = snd_pcm_hw_params_set_format(pcm, hw, SND_PCM_FORMAT_S16_LE);
    if (error >= 0) error = snd_pcm_hw_params_set_channels(pcm, hw, channels);
    if (error >= 0) error = snd_pcm_hw_params_set_rate_resample(pcm, hw, 1);
    unsigned actual_rate = rate;
    if (error >= 0) error = snd_pcm_hw_params_set_rate_near(pcm, hw, &actual_rate, nullptr);
    if (error >= 0 && actual_rate != rate) return -EINVAL;
    // Keep at least two requested hardware periods even below the DSP block.
    // ALSA negotiates the nearest supported sizes; report those actual values.
    snd_pcm_uframes_t period = std::min(256u,frames/2), buffer = frames;
    if (error >= 0) error = snd_pcm_hw_params_set_period_size_near(pcm, hw, &period, nullptr);
    if (error >= 0) error = snd_pcm_hw_params_set_buffer_size_near(pcm, hw, &buffer);
    if (error >= 0) error = snd_pcm_hw_params(pcm, hw);
    if (error < 0) return error;
    error = snd_pcm_get_params(pcm, &buffer, &period);
    if (error < 0) return error;
    snd_pcm_sw_params_t* sw; snd_pcm_sw_params_alloca(&sw);
    error = snd_pcm_sw_params_current(pcm, sw);
    if (error >= 0) error = snd_pcm_sw_params_set_start_threshold(pcm, sw, buffer > period ? buffer-period : 1);
    if (error >= 0) error = snd_pcm_sw_params_set_avail_min(pcm, sw, period);
    if (error >= 0) error = snd_pcm_sw_params(pcm, sw);
    return error < 0 ? error : snd_pcm_prepare(pcm);
}
