#include "no_audio_codec.h"

#include <esp_log.h>
#include <esp_timer.h>
#include <cmath>
#include <cstring>

#define TAG "NoAudioCodec"

namespace {
// SPH0645 is a two-slot Philips-I2S device. On ESP32-S3, receive both
// 32-bit slots and explicitly extract the selected microphone channel.
bool g_standard_rx_stereo = false;
int g_standard_rx_channel_index = 0;  // 0 = WS low/left, 1 = WS high/right

uint32_t Magnitude32(int32_t value) {
    return value >= 0
        ? static_cast<uint32_t>(value)
        : static_cast<uint32_t>(-static_cast<int64_t>(value));
}
}  // namespace

NoAudioCodec::~NoAudioCodec() {
    if (rx_handle_ != nullptr) {
        ESP_ERROR_CHECK(i2s_channel_disable(rx_handle_));
    }
    if (tx_handle_ != nullptr) {
        ESP_ERROR_CHECK(i2s_channel_disable(tx_handle_));
    }
}

NoAudioCodecDuplex::NoAudioCodecDuplex(int input_sample_rate, int output_sample_rate, gpio_num_t bclk, gpio_num_t ws, gpio_num_t dout, gpio_num_t din) {
    duplex_ = true;
    input_sample_rate_ = input_sample_rate;
    output_sample_rate_ = output_sample_rate;

    g_standard_rx_stereo = false;
    g_standard_rx_channel_index = 0;

    i2s_chan_config_t chan_cfg = {
        .id = I2S_NUM_0,
        .role = I2S_ROLE_MASTER,
        .dma_desc_num = AUDIO_CODEC_DMA_DESC_NUM,
        .dma_frame_num = AUDIO_CODEC_DMA_FRAME_NUM,
        .auto_clear_after_cb = true,
        .auto_clear_before_cb = false,
        .intr_priority = 0,
    };
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx_handle_, &rx_handle_));

    i2s_std_config_t std_cfg = {
        .clk_cfg = {
            .sample_rate_hz = (uint32_t)output_sample_rate_,
            .clk_src = I2S_CLK_SRC_DEFAULT,
            .mclk_multiple = I2S_MCLK_MULTIPLE_256,
			#ifdef   I2S_HW_VERSION_2
				.ext_clk_freq_hz = 0,
			#endif

        },
        .slot_cfg = {
            .data_bit_width = I2S_DATA_BIT_WIDTH_32BIT,
            .slot_bit_width = I2S_SLOT_BIT_WIDTH_AUTO,
            .slot_mode = I2S_SLOT_MODE_MONO,
            .slot_mask = I2S_STD_SLOT_LEFT,
            .ws_width = I2S_DATA_BIT_WIDTH_32BIT,
            .ws_pol = false,
            .bit_shift = true,
            #ifdef   I2S_HW_VERSION_2
                .left_align = true,
                .big_endian = false,
                .bit_order_lsb = false
            #endif

        },
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = bclk,
            .ws = ws,
            .dout = dout,
            .din = din,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false
            }
        }
    };
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_handle_, &std_cfg));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_handle_, &std_cfg));
    ESP_LOGI(TAG, "Duplex channels created");
}


NoAudioCodecSimplex::NoAudioCodecSimplex(int input_sample_rate, int output_sample_rate, gpio_num_t spk_bclk, gpio_num_t spk_ws, gpio_num_t spk_dout, gpio_num_t mic_sck, gpio_num_t mic_ws, gpio_num_t mic_din) {
    duplex_ = false;
    input_sample_rate_ = input_sample_rate;
    output_sample_rate_ = output_sample_rate;

    // SELECT is tied low on the Coglet SPH0645 module, so its valid data is
    // in the WS-low (left) slot.
    g_standard_rx_stereo = true;
    g_standard_rx_channel_index = 0;

    // Create a new channel for speaker
    i2s_chan_config_t chan_cfg = {
        .id = (i2s_port_t)0,
        .role = I2S_ROLE_MASTER,
        .dma_desc_num = AUDIO_CODEC_DMA_DESC_NUM,
        .dma_frame_num = AUDIO_CODEC_DMA_FRAME_NUM,
        .auto_clear_after_cb = true,
        .auto_clear_before_cb = false,
        .intr_priority = 0,
    };
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx_handle_, nullptr));

    i2s_std_config_t std_cfg = {
        .clk_cfg = {
            .sample_rate_hz = (uint32_t)output_sample_rate_,
            .clk_src = I2S_CLK_SRC_DEFAULT,
            .mclk_multiple = I2S_MCLK_MULTIPLE_256,
			#ifdef   I2S_HW_VERSION_2
				.ext_clk_freq_hz = 0,
			#endif

        },
        .slot_cfg = {
            .data_bit_width = I2S_DATA_BIT_WIDTH_32BIT,
            .slot_bit_width = I2S_SLOT_BIT_WIDTH_AUTO,
            .slot_mode = I2S_SLOT_MODE_MONO,
            .slot_mask = I2S_STD_SLOT_LEFT,
            .ws_width = I2S_DATA_BIT_WIDTH_32BIT,
            .ws_pol = false,
            .bit_shift = true,
            #ifdef   I2S_HW_VERSION_2
                .left_align = true,
                .big_endian = false,
                .bit_order_lsb = false
            #endif

        },
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = spk_bclk,
            .ws = spk_ws,
            .dout = spk_dout,
            .din = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false
            }
        }
    };
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_handle_, &std_cfg));

    // Create a new channel for MIC
    chan_cfg.id = (i2s_port_t)1;
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, nullptr, &rx_handle_));
    std_cfg.clk_cfg.sample_rate_hz = (uint32_t)input_sample_rate_;
    // SPH0645 requires standard Philips I2S with two 32-bit slots:
    // BCLK = sample_rate * 64. Receive both slots, then Read() extracts left.
    std_cfg.slot_cfg.slot_mode = I2S_SLOT_MODE_STEREO;
    std_cfg.slot_cfg.slot_mask = I2S_STD_SLOT_BOTH;
    std_cfg.gpio_cfg.bclk = mic_sck;
    std_cfg.gpio_cfg.ws = mic_ws;
    std_cfg.gpio_cfg.dout = I2S_GPIO_UNUSED;
    std_cfg.gpio_cfg.din = mic_din;
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_handle_, &std_cfg));
    ESP_LOGI(TAG,
             "Simplex channels created; MIC RX Philips-I2S stereo/BOTH, "
             "extract=LEFT, Fs=%d Hz, expected BCLK=%d Hz",
             input_sample_rate_, input_sample_rate_ * 64);
}

NoAudioCodecSimplex::NoAudioCodecSimplex(int input_sample_rate, int output_sample_rate, gpio_num_t spk_bclk, gpio_num_t spk_ws, gpio_num_t spk_dout, i2s_std_slot_mask_t spk_slot_mask, gpio_num_t mic_sck, gpio_num_t mic_ws, gpio_num_t mic_din, i2s_std_slot_mask_t mic_slot_mask){
    duplex_ = false;
    input_sample_rate_ = input_sample_rate;
    output_sample_rate_ = output_sample_rate;

    g_standard_rx_stereo = true;
    g_standard_rx_channel_index =
        (mic_slot_mask == I2S_STD_SLOT_RIGHT) ? 1 : 0;

    // Create a new channel for speaker
    i2s_chan_config_t chan_cfg = {
        .id = (i2s_port_t)0,
        .role = I2S_ROLE_MASTER,
        .dma_desc_num = AUDIO_CODEC_DMA_DESC_NUM,
        .dma_frame_num = AUDIO_CODEC_DMA_FRAME_NUM,
        .auto_clear_after_cb = true,
        .auto_clear_before_cb = false,
        .intr_priority = 0,
    };
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx_handle_, nullptr));

    i2s_std_config_t std_cfg = {
        .clk_cfg = {
            .sample_rate_hz = (uint32_t)output_sample_rate_,
            .clk_src = I2S_CLK_SRC_DEFAULT,
            .mclk_multiple = I2S_MCLK_MULTIPLE_256,
			#ifdef   I2S_HW_VERSION_2
				.ext_clk_freq_hz = 0,
			#endif

        },
        .slot_cfg = {
            .data_bit_width = I2S_DATA_BIT_WIDTH_32BIT,
            .slot_bit_width = I2S_SLOT_BIT_WIDTH_AUTO,
            .slot_mode = I2S_SLOT_MODE_MONO,
            .slot_mask = spk_slot_mask,
            .ws_width = I2S_DATA_BIT_WIDTH_32BIT,
            .ws_pol = false,
            .bit_shift = true,
            #ifdef   I2S_HW_VERSION_2
                .left_align = true,
                .big_endian = false,
                .bit_order_lsb = false
            #endif

        },
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = spk_bclk,
            .ws = spk_ws,
            .dout = spk_dout,
            .din = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false
            }
        }
    };
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_handle_, &std_cfg));

    // Create a new channel for MIC
    chan_cfg.id = (i2s_port_t)1;
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, nullptr, &rx_handle_));
    std_cfg.clk_cfg.sample_rate_hz = (uint32_t)input_sample_rate_;
    // Receive the complete two-slot frame. mic_slot_mask only selects which
    // slot Read() returns to the mono audio pipeline.
    std_cfg.slot_cfg.slot_mode = I2S_SLOT_MODE_STEREO;
    std_cfg.slot_cfg.slot_mask = I2S_STD_SLOT_BOTH;
    std_cfg.gpio_cfg.bclk = mic_sck;
    std_cfg.gpio_cfg.ws = mic_ws;
    std_cfg.gpio_cfg.dout = I2S_GPIO_UNUSED;
    std_cfg.gpio_cfg.din = mic_din;
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_handle_, &std_cfg));
    ESP_LOGI(TAG,
             "Simplex channels created; MIC RX Philips-I2S stereo/BOTH, "
             "extract=%s, Fs=%d Hz, expected BCLK=%d Hz",
             g_standard_rx_channel_index == 0 ? "LEFT" : "RIGHT",
             input_sample_rate_, input_sample_rate_ * 64);
}

int NoAudioCodec::Write(const int16_t* data, int samples) {
    std::lock_guard<std::mutex> lock(data_if_mutex_);
    std::vector<int32_t> buffer(samples);

    // output_volume_: 0-100
    // volume_factor_: 0-65536
    int32_t volume_factor = pow(double(output_volume_) / 100.0, 2) * 65536;
    for (int i = 0; i < samples; i++) {
        int64_t temp = int64_t(data[i]) * volume_factor; // 使用 int64_t 进行乘法运算
        if (temp > INT32_MAX) {
            buffer[i] = INT32_MAX;
        } else if (temp < INT32_MIN) {
            buffer[i] = INT32_MIN;
        } else {
            buffer[i] = static_cast<int32_t>(temp);
        }
    }

    size_t bytes_written;
    ESP_ERROR_CHECK(i2s_channel_write(tx_handle_, buffer.data(), samples * sizeof(int32_t), &bytes_written, portMAX_DELAY));
    return bytes_written / sizeof(int32_t);
}

int NoAudioCodec::Read(int16_t* dest, int samples) {
    if (dest == nullptr || samples <= 0) {
        return 0;
    }

    // Stereo RX returns interleaved frames: LEFT, RIGHT, LEFT, RIGHT...
    const int words_requested = g_standard_rx_stereo ? samples * 2 : samples;
    std::vector<int32_t> bit32_buffer(words_requested);

    size_t bytes_read = 0;
    esp_err_t err = i2s_channel_read(
        rx_handle_,
        bit32_buffer.data(),
        words_requested * sizeof(int32_t),
        &bytes_read,
        portMAX_DELAY
    );

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Read failed: %s", esp_err_to_name(err));
        return 0;
    }

    const int words_read = bytes_read / sizeof(int32_t);
    const int output_samples = g_standard_rx_stereo
        ? words_read / 2
        : words_read;

    if (output_samples <= 0) {
        return 0;
    }

    /*
     * SPH0645 can have a substantial fixed DC offset. The datasheet explicitly
     * recommends removing it with a DC-blocking/high-pass filter. Applying the
     * XiaoZhi project's >>12 scaling before removing this offset can drive every
     * output sample into INT16 clipping, which is exactly what the diagnostic
     * log showed (clip=512/512).
     *
     * Estimate the DC component in the original 32-bit I2S domain, subtract it,
     * and only then convert to 16-bit PCM. 1/4096 at 16 kHz gives a very slow
     * tracker (roughly 0.6 Hz corner), so normal speech is preserved.
     */
    constexpr int kMicPcmRightShift = 12;
    constexpr int kDcTrackingShift = 12;  // alpha = 1 / 4096

    static bool dc_initialized = false;
    static int64_t dc_estimate = 0;

    uint32_t raw_left_peak = 0;
    uint32_t raw_right_peak = 0;
    uint64_t ac_abs_sum = 0;
    uint32_t ac_peak = 0;
    uint64_t pcm_abs_sum = 0;
    uint32_t pcm_peak = 0;
    int clipped_samples = 0;

    for (int i = 0; i < output_samples; ++i) {
        int32_t raw_sample;

        if (g_standard_rx_stereo) {
            const int32_t raw_left = bit32_buffer[i * 2];
            const int32_t raw_right = bit32_buffer[i * 2 + 1];

            const uint32_t left_abs = Magnitude32(raw_left);
            const uint32_t right_abs = Magnitude32(raw_right);
            if (left_abs > raw_left_peak) {
                raw_left_peak = left_abs;
            }
            if (right_abs > raw_right_peak) {
                raw_right_peak = right_abs;
            }

            raw_sample = g_standard_rx_channel_index == 0
                ? raw_left
                : raw_right;
        } else {
            raw_sample = bit32_buffer[i];
            const uint32_t selected_abs = Magnitude32(raw_sample);
            if (selected_abs > raw_left_peak) {
                raw_left_peak = selected_abs;
            }
        }

        if (!dc_initialized) {
            dc_estimate = raw_sample;
            dc_initialized = true;
        }

        // Slow DC tracker. int64_t prevents overflow in the subtraction.
        dc_estimate += (static_cast<int64_t>(raw_sample) - dc_estimate)
            >> kDcTrackingShift;

        int64_t centered64 = static_cast<int64_t>(raw_sample) - dc_estimate;
        if (centered64 > INT32_MAX) {
            centered64 = INT32_MAX;
        } else if (centered64 < INT32_MIN) {
            centered64 = INT32_MIN;
        }
        const int32_t centered = static_cast<int32_t>(centered64);

        const uint32_t centered_abs = Magnitude32(centered);
        ac_abs_sum += centered_abs;
        if (centered_abs > ac_peak) {
            ac_peak = centered_abs;
        }

        // Preserve the original XiaoZhi scaling, but apply it to AC audio only.
        const int32_t value = centered >> kMicPcmRightShift;
        const uint32_t value_abs = Magnitude32(value);
        pcm_abs_sum += value_abs;
        if (value_abs > pcm_peak) {
            pcm_peak = value_abs;
        }

        if (value > INT16_MAX) {
            dest[i] = INT16_MAX;
            ++clipped_samples;
        } else if (value < INT16_MIN) {
            dest[i] = INT16_MIN;
            ++clipped_samples;
        } else {
            dest[i] = static_cast<int16_t>(value);
        }
    }

    // One diagnostic line per second.
    static int64_t last_log_us = 0;
    const int64_t now_us = esp_timer_get_time();
    if (now_us - last_log_us >= 1000000) {
        last_log_us = now_us;

        const uint32_t ac_average =
            static_cast<uint32_t>(ac_abs_sum / output_samples);
        const uint32_t pcm_average =
            static_cast<uint32_t>(pcm_abs_sum / output_samples);

        ESP_LOGW(
            TAG,
            "[MIC] mode=%s extract=%s shift=%d "
            "rawL=%u rawR=%u dc=%d acAvg=%u acPeak=%u "
            "pcmAvg=%u pcmPeak=%u clip=%d/%d",
            g_standard_rx_stereo ? "stereo" : "mono",
            g_standard_rx_channel_index == 0 ? "LEFT" : "RIGHT",
            kMicPcmRightShift,
            static_cast<unsigned>(raw_left_peak),
            static_cast<unsigned>(raw_right_peak),
            static_cast<int>(dc_estimate),
            static_cast<unsigned>(ac_average),
            static_cast<unsigned>(ac_peak),
            static_cast<unsigned>(pcm_average),
            static_cast<unsigned>(pcm_peak),
            clipped_samples,
            output_samples
        );
    }

    return output_samples;
}

// Delegating constructor: calls the main constructor with default slot mask
NoAudioCodecSimplexPdm::NoAudioCodecSimplexPdm(int input_sample_rate, int output_sample_rate, gpio_num_t spk_bclk, gpio_num_t spk_ws, gpio_num_t spk_dout, gpio_num_t mic_sck, gpio_num_t mic_din) 
    : NoAudioCodecSimplexPdm(input_sample_rate, output_sample_rate, spk_bclk, spk_ws, spk_dout, I2S_STD_SLOT_LEFT, mic_sck, mic_din) {
    // All initialization is handled by the delegated constructor
}

NoAudioCodecSimplexPdm::NoAudioCodecSimplexPdm(int input_sample_rate, int output_sample_rate, gpio_num_t spk_bclk, gpio_num_t spk_ws, gpio_num_t spk_dout, i2s_std_slot_mask_t spk_slot_mask, gpio_num_t mic_sck, gpio_num_t mic_din) {
    duplex_ = false;
    input_sample_rate_ = input_sample_rate;
    output_sample_rate_ = output_sample_rate;

    g_standard_rx_stereo = false;
    g_standard_rx_channel_index = 0;

    // Create a new channel for speaker
    i2s_chan_config_t tx_chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG((i2s_port_t)1, I2S_ROLE_MASTER);
    tx_chan_cfg.dma_desc_num = AUDIO_CODEC_DMA_DESC_NUM;
    tx_chan_cfg.dma_frame_num = AUDIO_CODEC_DMA_FRAME_NUM;
    tx_chan_cfg.auto_clear_after_cb = true;
    tx_chan_cfg.auto_clear_before_cb = false;
    tx_chan_cfg.intr_priority = 0;
    ESP_ERROR_CHECK(i2s_new_channel(&tx_chan_cfg, &tx_handle_, NULL));


    i2s_std_config_t tx_std_cfg = {
        .clk_cfg = {
            .sample_rate_hz = (uint32_t)output_sample_rate_,
            .clk_src = I2S_CLK_SRC_DEFAULT,
            .mclk_multiple = I2S_MCLK_MULTIPLE_256,
			#ifdef   I2S_HW_VERSION_2
				.ext_clk_freq_hz = 0,
			#endif

        },
        .slot_cfg = {
            .data_bit_width = I2S_DATA_BIT_WIDTH_32BIT,
            .slot_bit_width = I2S_SLOT_BIT_WIDTH_AUTO,
            .slot_mode = I2S_SLOT_MODE_MONO,
            .slot_mask = spk_slot_mask,
            .ws_width = I2S_DATA_BIT_WIDTH_32BIT,
            .ws_pol = false,
            .bit_shift = true,
            #ifdef   I2S_HW_VERSION_2
                .left_align = true,
                .big_endian = false,
                .bit_order_lsb = false
            #endif

        },
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = spk_bclk,
            .ws = spk_ws,
            .dout = spk_dout,
            .din = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv   = false,
            },
        },
    };
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_handle_, &tx_std_cfg));
#if SOC_I2S_SUPPORTS_PDM_RX
    // Create a new channel for MIC in PDM mode
    i2s_chan_config_t rx_chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG((i2s_port_t)0, I2S_ROLE_MASTER);
    ESP_ERROR_CHECK(i2s_new_channel(&rx_chan_cfg, NULL, &rx_handle_));
    i2s_pdm_rx_config_t pdm_rx_cfg = {
        .clk_cfg = I2S_PDM_RX_CLK_DEFAULT_CONFIG((uint32_t)input_sample_rate_),
        /* The data bit-width of PDM mode is fixed to 16 */
        .slot_cfg = I2S_PDM_RX_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .clk = mic_sck,
            .din = mic_din,

            .invert_flags = {
                .clk_inv = false,
            },
        },
    };
    ESP_ERROR_CHECK(i2s_channel_init_pdm_rx_mode(rx_handle_, &pdm_rx_cfg));
#else
    ESP_LOGE(TAG, "PDM is not supported");
#endif
    ESP_LOGI(TAG, "Simplex channels created");
}

int NoAudioCodecSimplexPdm::Read(int16_t* dest, int samples) {
    size_t bytes_read;

    // PDM 解调后的数据位宽为 16 位，直接读取到目标缓冲区
    if (i2s_channel_read(rx_handle_, dest, samples * sizeof(int16_t), &bytes_read, portMAX_DELAY) != ESP_OK) {
        ESP_LOGE(TAG, "Read Failed!");
        return 0;
    }

    samples = bytes_read / sizeof(int16_t);
    if (input_gain_ > 0) {
        int gain_factor = (int)input_gain_;
        for (int i = 0; i < samples; i++) {
            int32_t amplified = dest[i] * gain_factor;
            dest[i] = (amplified > INT16_MAX) ? INT16_MAX : (amplified < -INT16_MAX) ? -INT16_MAX : (int16_t)amplified;
        }
    }
    return samples;
}
