#ifndef _SOFTWARE_AEC_REFERENCE_H
#define _SOFTWARE_AEC_REFERENCE_H

// Software AEC reference ("digital loopback") for boards whose speaker path
// has no hardware reference channel, e.g. Coglet: SPH0645 mic on one I2S port,
// MAX98357A amplifier on another.
//
// The I2S TX DMA "on_sent" callback sees the exact PCM block that was just
// clocked out to the amplifier (before the driver auto-clears it). The RX DMA
// "on_recv" callback sees every microphone block. Both callbacks record an
// esp_timer timestamp, so every speaker sample and every microphone sample gets
// a time on one common clock. Pull() then returns microphone frames together
// with the speaker signal that was playing at the same moment, resampled to the
// microphone rate. That pair is exactly the "MR" input that esp-sr AFE AEC
// expects.
//
// Why timestamps instead of a plain FIFO: the speaker and mic run on two
// I2S peripherals whose fractional clock dividers are not exactly identical,
// and DMA blocks are occasionally dropped while nobody reads. A FIFO offset
// would slowly drift or jump; a per-block timestamp (smoothed by a tiny PLL)
// cannot accumulate error.
//
// Threading model:
//   PushRefFromIsr / PushMicFromIsr : ISR context only (integer, no locks).
//   Pull / GetStats                  : one consumer task only.
//
// This file has no ESP-IDF dependency so it can be unit-tested on a host.

#include <atomic>
#include <cstddef>
#include <cstdint>

#if defined(ESP_PLATFORM)
#include <esp_attr.h>
#define SOFTWARE_AEC_REF_ISR_ATTR IRAM_ATTR
#else
#define SOFTWARE_AEC_REF_ISR_ATTR
#endif

class SoftwareAecReference {
public:
    struct Config {
        int mic_rate_hz = 16000;
        int ref_rate_hz = 24000;
        // Reference offset. The reference sample paired with a mic sample
        // captured at time t is the speaker sample played at (t - ref_delay_us).
        // 0 means "same instant". Larger values make the reference arrive later
        // relative to the echo; AEC needs the reference no later than the echo,
        // so keep this <= the real acoustic delay (a few ms).
        int ref_delay_us = 0;
        // How long Pull() may wait for the speaker DMA to report the reference
        // block that covers the newest microphone frame.
        int max_ref_wait_us = 30000;
    };

    enum class PullResult {
        kOk,       // frames written to mic_out / ref_out
        kNeedMic,  // not enough microphone frames captured yet
        kNeedRef,  // mic ready, reference for that time not reported yet
    };

    struct Stats {
        uint32_t mic_overruns = 0;      // consumer too slow, oldest mic blocks dropped
        uint32_t ref_overruns = 0;      // consumer too slow, raw ref blocks dropped
        uint32_t mic_resyncs = 0;       // mic timestamp PLL re-locked (gap / start)
        uint32_t ref_resyncs = 0;       // ref timestamp PLL re-locked (gap / start)
        uint32_t ref_missing_frames = 0;// frames with no reference coverage (zeros)
        uint32_t ref_late_frames = 0;   // frames output after waiting max_ref_wait_us
        uint32_t mic_torn_blocks = 0;   // a block was overwritten while copying
        int32_t last_offset_us = 0;     // newest ref t_end - newest mic t_end
        uint16_t ref_peak = 0;          // |ref| peak since previous GetStats()
    };

    using AllocFn = void* (*)(size_t bytes, bool isr_access);
    using FreeFn = void (*)(void* ptr);

    static constexpr int kMaxBlockFrames = 256;  // XiaoZhi DMA blocks are 240 frames
    static constexpr int kMicBlocks = 8;         // 8 x 15 ms = 120 ms of mic history
    static constexpr int kRefRawBlocks = 32;     // 32 x 10 ms = 320 ms raw speaker history
    static constexpr int kRefRingSamples = 16384;// processed speaker samples (~680 ms @24k)
    static constexpr int kRefAnchors = 96;       // block timing anchors for processed ring

    SoftwareAecReference() = default;
    ~SoftwareAecReference();
    SoftwareAecReference(const SoftwareAecReference&) = delete;
    SoftwareAecReference& operator=(const SoftwareAecReference&) = delete;

    bool Init(const Config& config, AllocFn alloc, FreeFn free_fn);
    bool initialized() const { return initialized_; }
    void SetRefDelayUs(int delay_us) { config_.ref_delay_us = delay_us; }
    const Config& config() const { return config_; }

    // ISR side (definitions are placed in IRAM on ESP targets).
    // samples: TX DMA words (32-bit, PCM in the upper 16 bits), mono.
    void PushRefFromIsr(const int32_t* samples, size_t frames, int64_t t_end_us);
    // words: RX DMA words (32-bit). stride = words per frame, channel = slot to keep.
    void PushMicFromIsr(const int32_t* words, size_t frames, int stride, int channel,
                        int64_t t_end_us);

    // Returns `frames` raw 32-bit mic words and the time-aligned 16-bit
    // reference at mic rate. Never blocks; the caller waits and retries on
    // kNeedMic / kNeedRef.
    PullResult Pull(int frames, int32_t* mic_out, int16_t* ref_out, int64_t now_us);

    // Snapshot of counters; resets ref_peak.
    Stats GetStats();

private:
    struct MicBlock {
        int64_t t_end_us;
        uint16_t frames;
        int32_t samples[kMaxBlockFrames];
    };
    struct RefRawBlock {
        int64_t t_end_us;
        uint16_t frames;
        int16_t samples[kMaxBlockFrames];
    };
    struct Anchor {
        int64_t end_index;   // absolute processed index one past the block's last sample
        double t_last_us;    // time of the block's last sample (after FIR delay)
        uint16_t frames;
    };
    // Timestamp tracker for one DMA stream. ISR latency only ever makes a raw
    // timestamp late, so the estimate follows the lower envelope of the raw
    // timestamps (early raw values are trusted, late ones only nudge it), and
    // the real sample period is measured over the whole locked interval so
    // clock drift leaves no steady-state lag. Re-locks on real gaps.
    struct BlockClock {
        bool locked = false;
        double t_end_us = 0;
        double period_us = 0;        // measured sample period
        double samples_since_lock = 0;
        double base_t_us = 0;        // settled estimate where period measurement starts
        double base_samples = -1;    // samples_since_lock at base (-1: not yet)
        // Returns true when the tracker had to re-lock (timing discontinuity).
        bool Update(int64_t raw_t_end_us, int frames, double nominal_period_us);
        // Blocks that were captured but skipped by the consumer: keep the
        // timeline continuous instead of re-locking.
        void Skip(int blocks, int frames_per_block);
    };

    void ProcessNewRefBlocks();
    void TrackMicClock(uint32_t write_seq);
    bool FindRefIndex(double t_us, double* abs_index);
    int16_t RefSample(int64_t abs_index, bool* valid) const;
    double NewestRefTimeUs() const;

    Config config_;
    bool initialized_ = false;
    FreeFn free_fn_ = nullptr;

    double mic_period_us_ = 62.5;
    double ref_period_us_ = 41.6667;
    double ref_step_ = 1.5;            // ref samples per mic sample
    double fir_delay_us_ = 0;

    // ISR-written rings (internal RAM).
    MicBlock* mic_blocks_ = nullptr;
    RefRawBlock* ref_raw_ = nullptr;
    std::atomic<uint32_t> mic_write_seq_{0};
    std::atomic<uint32_t> ref_write_seq_{0};

    // Consumer state.
    uint32_t mic_read_seq_ = 0;
    int mic_read_off_ = 0;
    uint32_t mic_clock_seq_ = 0;
    double mic_t_end_[kMicBlocks] = {};
    BlockClock mic_clock_;
    int last_mic_frames_ = 240;

    uint32_t ref_read_seq_ = 0;
    BlockClock ref_clock_;
    int last_ref_frames_ = 240;
    int16_t* ref_ring_ = nullptr;
    int64_t ref_total_ = 0;            // processed samples written
    Anchor anchors_[kRefAnchors] = {};
    uint32_t anchor_count_ = 0;        // total anchors written
    uint32_t anchor_cursor_ = 0;

    static constexpr int kMaxTaps = 31;
    float fir_coeffs_[kMaxTaps] = {};
    float fir_hist_[kMaxTaps] = {};
    int fir_taps_ = 1;
    int fir_pos_ = 0;

    Stats stats_;
};

#endif  // _SOFTWARE_AEC_REFERENCE_H
