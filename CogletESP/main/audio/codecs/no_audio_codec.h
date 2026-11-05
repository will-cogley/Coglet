#ifndef _NO_AUDIO_CODEC_H
#define _NO_AUDIO_CODEC_H

#include "audio_codec.h"

#include <driver/gpio.h>
#include <driver/i2s_pdm.h>
#include <freertos/semphr.h>
#include <memory>
#include <mutex>

class SoftwareAecReference;

class NoAudioCodec : public AudioCodec {
protected:
    std::mutex data_if_mutex_;

    virtual int Write(const int16_t* data, int samples) override;
    virtual int Read(int16_t* dest, int samples) override;

public:
    virtual ~NoAudioCodec();
};

class NoAudioCodecDuplex : public NoAudioCodec {
public:
    NoAudioCodecDuplex(int input_sample_rate, int output_sample_rate, gpio_num_t bclk, gpio_num_t ws, gpio_num_t dout, gpio_num_t din);
};

class NoAudioCodecSimplex : public NoAudioCodec {
public:
    NoAudioCodecSimplex(int input_sample_rate, int output_sample_rate, gpio_num_t spk_bclk, gpio_num_t spk_ws, gpio_num_t spk_dout, gpio_num_t mic_sck, gpio_num_t mic_ws, gpio_num_t mic_din);
    NoAudioCodecSimplex(int input_sample_rate, int output_sample_rate, gpio_num_t spk_bclk, gpio_num_t spk_ws, gpio_num_t spk_dout, i2s_std_slot_mask_t spk_slot_mask, gpio_num_t mic_sck, gpio_num_t mic_ws, gpio_num_t mic_din, i2s_std_slot_mask_t mic_slot_mask);
    virtual ~NoAudioCodecSimplex();

    // Software AEC reference (digital loopback) for boards without a hardware
    // reference path. Must be called before Start(). On success the codec
    // reports 2 input channels ("MR": mic, reference) and input_reference().
    // ref_delay_us: see SoftwareAecReference::Config::ref_delay_us.
    bool EnableSoftwareAecReference(int ref_delay_us);

protected:
    virtual int Read(int16_t* dest, int samples) override;

private:
    std::unique_ptr<SoftwareAecReference> aec_ref_;
    SemaphoreHandle_t aec_data_sem_ = nullptr;
    int aec_rx_stride_ = 2;
    int aec_rx_channel_ = 0;

    int ReadWithSoftwareReference(int16_t* dest, int samples);
    static bool OnSpeakerBlockSent(i2s_chan_handle_t handle, i2s_event_data_t* event, void* user_ctx);
    static bool OnMicBlockReceived(i2s_chan_handle_t handle, i2s_event_data_t* event, void* user_ctx);
};

class NoAudioCodecSimplexPdm : public NoAudioCodec {
public:
    NoAudioCodecSimplexPdm(int input_sample_rate, int output_sample_rate, gpio_num_t spk_bclk, gpio_num_t spk_ws, gpio_num_t spk_dout, gpio_num_t mic_sck,  gpio_num_t mic_din);
    NoAudioCodecSimplexPdm(int input_sample_rate, int output_sample_rate, gpio_num_t spk_bclk, gpio_num_t spk_ws, gpio_num_t spk_dout, i2s_std_slot_mask_t spk_slot_mask, gpio_num_t mic_sck,  gpio_num_t mic_din);
    int Read(int16_t* dest, int samples);
};

#endif // _NO_AUDIO_CODEC_H
