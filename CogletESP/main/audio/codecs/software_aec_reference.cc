#include "software_aec_reference.h"

#include <cmath>
#include <cstring>

namespace {
constexpr double kPi = 3.14159265358979323846;
// A timestamp further than this from the prediction means a real gap
// (lost DMA interrupt, channel restart), not ISR jitter: re-lock immediately.
constexpr double kRelockThresholdUs = 3000.0;
// Raw timestamp earlier than predicted: our estimate is late, correct quickly.
constexpr double kEarlyGain = 0.25;
// Raw timestamp later than predicted: probably ISR latency. Clamp the error so
// a latency spike moves the estimate by at most kLateClampUs * kLateGain.
constexpr double kLateGain = 1.0 / 32.0;
constexpr double kLateClampUs = 60.0;
// Period measurement: wait until the envelope estimate has settled, take that
// as the baseline, then measure over at least another warm-up interval.
constexpr double kPeriodSettleSamples = 240.0 * 10.0;
constexpr double kPeriodWarmupSamples = 240.0 * 30.0;
// Hardware fractional dividers are far better than this; anything outside is
// a measurement artefact.
constexpr double kMaxPeriodError = 1e-3;
// A raw timestamp that is late by (almost exactly) a whole number of blocks
// means interrupts were lost, not that time jumped.
constexpr double kLostBlockToleranceUs = 400.0;
constexpr int kMaxLostBlocks = 8;
// Inside a timing gap between two anchors (lost speaker interrupt) no valid
// reference exists. Small PLL seams between consecutive blocks are tolerated.
constexpr double kGapToleranceSamples = 4.0;

inline int16_t SaturateToInt16(float value) {
    if (value > 32767.0f) {
        return 32767;
    }
    if (value < -32768.0f) {
        return -32768;
    }
    return static_cast<int16_t>(lrintf(value));
}
}  // namespace

bool SoftwareAecReference::BlockClock::Update(int64_t raw_t_end_us, int frames,
                                              double nominal_period_us) {
    const double raw = static_cast<double>(raw_t_end_us);
    if (!locked) {
        period_us = nominal_period_us;
    }
    double predicted = t_end_us + frames * period_us;
    double error = raw - predicted;

    // Lost DMA interrupts: the hardware kept running, so the raw time is a
    // whole number of blocks later. Advance instead of re-locking.
    if (locked && error > kRelockThresholdUs) {
        const double block_us = frames * period_us;
        const double lost = std::floor(error / block_us + 0.5);
        if (lost >= 1 && lost <= kMaxLostBlocks &&
            std::fabs(error - lost * block_us) < kLostBlockToleranceUs) {
            predicted += lost * block_us;
            samples_since_lock += lost * frames;
            error = raw - predicted;
        }
    }

    if (!locked || std::fabs(error) > kRelockThresholdUs) {
        t_end_us = raw;
        samples_since_lock = 0;
        base_samples = -1;
        period_us = nominal_period_us;
        locked = true;
        return true;
    }
    double correction;
    if (error < 0) {
        correction = error * kEarlyGain;
        if (error < -kLateClampUs) {
            // The estimate was clearly late (e.g. locked on a latency spike):
            // it is not settled, so any period baseline taken so far is biased.
            base_samples = -1;
        }
    } else {
        correction = (error < kLateClampUs ? error : kLateClampUs) * kLateGain;
    }
    t_end_us = predicted + correction;
    samples_since_lock += frames;

    if (base_samples < 0) {
        if (samples_since_lock >= kPeriodSettleSamples) {
            base_samples = samples_since_lock;
            base_t_us = t_end_us;
        }
    } else if (samples_since_lock - base_samples >= kPeriodWarmupSamples) {
        const double measured = (t_end_us - base_t_us) / (samples_since_lock - base_samples);
        const double low = nominal_period_us * (1.0 - kMaxPeriodError);
        const double high = nominal_period_us * (1.0 + kMaxPeriodError);
        period_us = measured < low ? low : (measured > high ? high : measured);
    }
    return false;
}

void SoftwareAecReference::BlockClock::Skip(int blocks, int frames_per_block) {
    if (!locked || blocks <= 0) {
        return;
    }
    t_end_us += static_cast<double>(blocks) * frames_per_block * period_us;
    samples_since_lock += static_cast<double>(blocks) * frames_per_block;
}

SoftwareAecReference::~SoftwareAecReference() {
    initialized_ = false;
    if (free_fn_ != nullptr) {
        free_fn_(mic_blocks_);
        free_fn_(ref_raw_);
        free_fn_(ref_ring_);
    }
}

bool SoftwareAecReference::Init(const Config& config, AllocFn alloc, FreeFn free_fn) {
    if (initialized_ || alloc == nullptr || free_fn == nullptr ||
        config.mic_rate_hz <= 0 || config.ref_rate_hz <= 0) {
        return false;
    }
    config_ = config;
    free_fn_ = free_fn;

    mic_blocks_ = static_cast<MicBlock*>(alloc(sizeof(MicBlock) * kMicBlocks, true));
    ref_raw_ = static_cast<RefRawBlock*>(alloc(sizeof(RefRawBlock) * kRefRawBlocks, true));
    ref_ring_ = static_cast<int16_t*>(alloc(sizeof(int16_t) * kRefRingSamples, false));
    if (mic_blocks_ == nullptr || ref_raw_ == nullptr || ref_ring_ == nullptr) {
        free_fn_(mic_blocks_);
        free_fn_(ref_raw_);
        free_fn_(ref_ring_);
        mic_blocks_ = nullptr;
        ref_raw_ = nullptr;
        ref_ring_ = nullptr;
        return false;
    }
    std::memset(mic_blocks_, 0, sizeof(MicBlock) * kMicBlocks);
    std::memset(ref_raw_, 0, sizeof(RefRawBlock) * kRefRawBlocks);
    std::memset(ref_ring_, 0, sizeof(int16_t) * kRefRingSamples);

    mic_period_us_ = 1e6 / config_.mic_rate_hz;
    ref_period_us_ = 1e6 / config_.ref_rate_hz;
    ref_step_ = static_cast<double>(config_.ref_rate_hz) / config_.mic_rate_hz;

    // Anti-alias low-pass before decimating the speaker signal to mic rate.
    // Blackman-windowed sinc, cut-off at 45% of the mic rate (7.2 kHz @16k).
    if (config_.ref_rate_hz > config_.mic_rate_hz) {
        fir_taps_ = kMaxTaps;
        const double cutoff = 0.45 * config_.mic_rate_hz / config_.ref_rate_hz;
        const int middle = (fir_taps_ - 1) / 2;
        double sum = 0;
        for (int i = 0; i < fir_taps_; ++i) {
            const int n = i - middle;
            const double sinc = (n == 0) ? 2.0 * cutoff
                                         : std::sin(2.0 * kPi * cutoff * n) / (kPi * n);
            const double window = 0.42 - 0.5 * std::cos(2.0 * kPi * i / (fir_taps_ - 1)) +
                                  0.08 * std::cos(4.0 * kPi * i / (fir_taps_ - 1));
            fir_coeffs_[i] = static_cast<float>(sinc * window);
            sum += fir_coeffs_[i];
        }
        for (int i = 0; i < fir_taps_; ++i) {
            fir_coeffs_[i] = static_cast<float>(fir_coeffs_[i] / sum);
        }
        fir_delay_us_ = middle * ref_period_us_;
    } else {
        fir_taps_ = 1;
        fir_coeffs_[0] = 1.0f;
        fir_delay_us_ = 0;
    }
    std::memset(fir_hist_, 0, sizeof(fir_hist_));
    fir_pos_ = 0;

    initialized_ = true;
    return true;
}

// ---------------------------------------------------------------- ISR side

SOFTWARE_AEC_REF_ISR_ATTR void SoftwareAecReference::PushRefFromIsr(const int32_t* samples, size_t frames,
                                          int64_t t_end_us) {
    if (!initialized_ || samples == nullptr || frames == 0) {
        return;
    }
    if (frames > static_cast<size_t>(kMaxBlockFrames)) {
        frames = kMaxBlockFrames;
    }
    const uint32_t seq = ref_write_seq_.load(std::memory_order_relaxed);
    RefRawBlock& block = ref_raw_[seq % kRefRawBlocks];
    for (size_t i = 0; i < frames; ++i) {
        // NoAudioCodec::Write() places 16-bit PCM x volume in the upper bits.
        block.samples[i] = static_cast<int16_t>(samples[i] >> 16);
    }
    block.frames = static_cast<uint16_t>(frames);
    block.t_end_us = t_end_us;
    ref_write_seq_.store(seq + 1, std::memory_order_release);
}

SOFTWARE_AEC_REF_ISR_ATTR void SoftwareAecReference::PushMicFromIsr(const int32_t* words, size_t frames, int stride,
                                          int channel, int64_t t_end_us) {
    if (!initialized_ || words == nullptr || frames == 0 || stride <= 0 ||
        channel < 0 || channel >= stride) {
        return;
    }
    if (frames > static_cast<size_t>(kMaxBlockFrames)) {
        frames = kMaxBlockFrames;
    }
    const uint32_t seq = mic_write_seq_.load(std::memory_order_relaxed);
    MicBlock& block = mic_blocks_[seq % kMicBlocks];
    for (size_t i = 0; i < frames; ++i) {
        block.samples[i] = words[i * stride + channel];
    }
    block.frames = static_cast<uint16_t>(frames);
    block.t_end_us = t_end_us;
    mic_write_seq_.store(seq + 1, std::memory_order_release);
}

// --------------------------------------------------------------- task side

void SoftwareAecReference::ProcessNewRefBlocks() {
    uint32_t write_seq = ref_write_seq_.load(std::memory_order_acquire);
    bool discontinuity = false;
    if (write_seq - ref_read_seq_ > static_cast<uint32_t>(kRefRawBlocks - 1)) {
        const uint32_t target = write_seq - (kRefRawBlocks - 1);
        ref_clock_.Skip(static_cast<int>(target - ref_read_seq_), last_ref_frames_);
        ref_read_seq_ = target;
        ++stats_.ref_overruns;
        discontinuity = true;
    }

    int16_t local[kMaxBlockFrames];
    while (ref_read_seq_ != write_seq) {
        const RefRawBlock& raw = ref_raw_[ref_read_seq_ % kRefRawBlocks];
        const int64_t t_end = raw.t_end_us;
        int frames = raw.frames;
        if (frames > kMaxBlockFrames) {
            frames = kMaxBlockFrames;
        }
        std::memcpy(local, raw.samples, sizeof(int16_t) * frames);

        // Seqlock check: the ISR may have lapped this slot while we copied.
        const uint32_t latest = ref_write_seq_.load(std::memory_order_acquire);
        if (latest - ref_read_seq_ > static_cast<uint32_t>(kRefRawBlocks - 1)) {
            const uint32_t target = latest - (kRefRawBlocks - 1);
            ref_clock_.Skip(static_cast<int>(target - ref_read_seq_), last_ref_frames_);
            ref_read_seq_ = target;
            write_seq = latest;
            ++stats_.ref_overruns;
            discontinuity = true;
            continue;
        }

        last_ref_frames_ = frames;
        if (ref_clock_.Update(t_end, frames, ref_period_us_)) {
            ++stats_.ref_resyncs;
            discontinuity = true;
        }
        if (discontinuity) {
            std::memset(fir_hist_, 0, sizeof(fir_hist_));
            fir_pos_ = 0;
            discontinuity = false;
        }

        for (int i = 0; i < frames; ++i) {
            fir_hist_[fir_pos_] = local[i];
            float acc = 0;
            int index = fir_pos_;
            for (int k = 0; k < fir_taps_; ++k) {
                acc += fir_coeffs_[k] * fir_hist_[index];
                index = (index == 0) ? fir_taps_ - 1 : index - 1;
            }
            fir_pos_ = (fir_pos_ + 1 == fir_taps_) ? 0 : fir_pos_ + 1;
            ref_ring_[ref_total_ % kRefRingSamples] = SaturateToInt16(acc);
            ++ref_total_;
        }

        Anchor& anchor = anchors_[anchor_count_ % kRefAnchors];
        anchor.end_index = ref_total_;
        anchor.t_last_us = ref_clock_.t_end_us - fir_delay_us_;
        anchor.frames = static_cast<uint16_t>(frames);
        ++anchor_count_;
        ++ref_read_seq_;
    }
}

void SoftwareAecReference::TrackMicClock(uint32_t write_seq) {
    if (write_seq - mic_clock_seq_ > static_cast<uint32_t>(kMicBlocks - 1)) {
        const uint32_t target = write_seq - (kMicBlocks - 1);
        mic_clock_.Skip(static_cast<int>(target - mic_clock_seq_), last_mic_frames_);
        mic_clock_seq_ = target;
    }
    while (mic_clock_seq_ != write_seq) {
        const MicBlock& block = mic_blocks_[mic_clock_seq_ % kMicBlocks];
        const int64_t t_end = block.t_end_us;
        const int frames = block.frames;
        const uint32_t latest = mic_write_seq_.load(std::memory_order_acquire);
        if (latest - mic_clock_seq_ > static_cast<uint32_t>(kMicBlocks - 1)) {
            const uint32_t target = latest - (kMicBlocks - 1);
            mic_clock_.Skip(static_cast<int>(target - mic_clock_seq_), last_mic_frames_);
            mic_clock_seq_ = target;
            write_seq = latest;
            continue;
        }
        last_mic_frames_ = frames;
        if (mic_clock_.Update(t_end, frames, mic_period_us_)) {
            ++stats_.mic_resyncs;
        }
        mic_t_end_[mic_clock_seq_ % kMicBlocks] = mic_clock_.t_end_us;
        ++mic_clock_seq_;
    }
}

double SoftwareAecReference::NewestRefTimeUs() const {
    if (anchor_count_ == 0) {
        return -1e300;
    }
    return anchors_[(anchor_count_ - 1) % kRefAnchors].t_last_us;
}

bool SoftwareAecReference::FindRefIndex(double t_us, double* abs_index) {
    if (anchor_count_ == 0) {
        return false;
    }
    const uint32_t newest = anchor_count_ - 1;
    const uint32_t oldest = anchor_count_ > static_cast<uint32_t>(kRefAnchors)
        ? anchor_count_ - kRefAnchors : 0;
    uint32_t j = anchor_cursor_;
    if (j < oldest || j > newest) {
        j = newest;
    }

    auto first_time = [this](uint32_t seq) {
        const Anchor& a = anchors_[seq % kRefAnchors];
        return a.t_last_us - (a.frames - 1) * ref_period_us_;
    };

    // Latest anchor whose first sample is at or before t (one-sample slack).
    while (j < newest && t_us >= first_time(j + 1) - ref_period_us_) {
        ++j;
    }
    while (j > oldest && t_us < first_time(j) - ref_period_us_) {
        --j;
    }
    anchor_cursor_ = j;

    const Anchor& anchor = anchors_[j % kRefAnchors];
    if (t_us < first_time(j) - ref_period_us_) {
        return false;  // older than everything still retained
    }
    if (j < newest && t_us > anchor.t_last_us + kGapToleranceSamples * ref_period_us_) {
        return false;  // inside a gap left by a lost speaker interrupt
    }
    *abs_index = static_cast<double>(anchor.end_index - 1) -
                 (anchor.t_last_us - t_us) / ref_period_us_;
    return true;
}

int16_t SoftwareAecReference::RefSample(int64_t abs_index, bool* valid) const {
    if (abs_index < 0 || abs_index >= ref_total_ ||
        abs_index < ref_total_ - kRefRingSamples) {
        *valid = false;
        return 0;
    }
    *valid = true;
    return ref_ring_[abs_index % kRefRingSamples];
}

SoftwareAecReference::PullResult SoftwareAecReference::Pull(int frames, int32_t* mic_out,
                                                            int16_t* ref_out, int64_t now_us) {
    if (!initialized_ || frames <= 0 || mic_out == nullptr || ref_out == nullptr) {
        return PullResult::kNeedMic;
    }

    ProcessNewRefBlocks();

    const uint32_t write_seq = mic_write_seq_.load(std::memory_order_acquire);
    if (write_seq - mic_read_seq_ > static_cast<uint32_t>(kMicBlocks - 1)) {
        // Nobody read for a while (e.g. between wake word and AFE): drop the
        // oldest blocks, exactly like the I2S driver's own queue would.
        mic_read_seq_ = write_seq - (kMicBlocks - 1);
        mic_read_off_ = 0;
        ++stats_.mic_overruns;
    }
    TrackMicClock(write_seq);

    // Locate the last frame this pull needs; bail out if not captured yet.
    uint32_t seq = mic_read_seq_;
    int off = mic_read_off_;
    int remaining = frames;
    uint32_t last_seq = seq;
    int last_off = 0;
    while (remaining > 0) {
        if (seq == write_seq) {
            return PullResult::kNeedMic;
        }
        const int block_frames = mic_blocks_[seq % kMicBlocks].frames;
        const int take = block_frames - off < remaining ? block_frames - off : remaining;
        if (take > 0) {
            remaining -= take;
            if (remaining == 0) {
                last_seq = seq;
                last_off = off + take - 1;
                break;
            }
        }
        ++seq;
        off = 0;
    }

    const double delay_us = config_.ref_delay_us;
    {
        const int last_frames = mic_blocks_[last_seq % kMicBlocks].frames;
        const double t_last = mic_t_end_[last_seq % kMicBlocks] -
                              (last_frames - 1 - last_off) * mic_period_us_;
        // One extra reference sample is needed for interpolation.
        const double needed_ref = t_last - delay_us + ref_period_us_;
        if (NewestRefTimeUs() < needed_ref &&
            static_cast<double>(now_us) < needed_ref + config_.max_ref_wait_us) {
            return PullResult::kNeedRef;
        }
    }

    // Copy mic frames and build the aligned reference.
    seq = mic_read_seq_;
    off = mic_read_off_;
    remaining = frames;
    int out = 0;
    uint16_t peak = stats_.ref_peak;
    while (remaining > 0) {
        const MicBlock& block = mic_blocks_[seq % kMicBlocks];
        const int block_frames = block.frames;
        int take = block_frames - off < remaining ? block_frames - off : remaining;
        if (take > 0) {
            std::memcpy(mic_out + out, block.samples + off, sizeof(int32_t) * take);

            const double t_first = mic_t_end_[seq % kMicBlocks] -
                                   (block_frames - 1 - off) * mic_period_us_;
            double ref_pos = 0;
            if (!FindRefIndex(t_first - delay_us, &ref_pos)) {
                std::memset(ref_out + out, 0, sizeof(int16_t) * take);
                stats_.ref_missing_frames += take;
            } else {
                int64_t index = static_cast<int64_t>(std::floor(ref_pos));
                float frac = static_cast<float>(ref_pos - static_cast<double>(index));
                const float step = static_cast<float>(ref_step_);
                for (int i = 0; i < take; ++i) {
                    bool valid0 = false;
                    bool valid1 = false;
                    const int16_t s0 = RefSample(index, &valid0);
                    const int16_t s1 = RefSample(index + 1, &valid1);
                    int16_t value = 0;
                    if (!valid0) {
                        if (index >= ref_total_) {
                            ++stats_.ref_late_frames;
                        } else {
                            ++stats_.ref_missing_frames;
                        }
                    } else if (!valid1) {
                        value = s0;
                    } else {
                        value = SaturateToInt16(s0 + frac * static_cast<float>(s1 - s0));
                    }
                    ref_out[out + i] = value;
                    const uint16_t magnitude = static_cast<uint16_t>(
                        value < 0 ? -static_cast<int32_t>(value) : value);
                    if (magnitude > peak) {
                        peak = magnitude;
                    }
                    frac += step;
                    while (frac >= 1.0f) {
                        frac -= 1.0f;
                        ++index;
                    }
                }
            }
            out += take;
            remaining -= take;
            off += take;
        }
        if (off >= block_frames) {
            ++seq;
            off = 0;
        }
    }
    stats_.ref_peak = peak;

    const uint32_t latest = mic_write_seq_.load(std::memory_order_acquire);
    if (latest - mic_read_seq_ > static_cast<uint32_t>(kMicBlocks - 1)) {
        ++stats_.mic_torn_blocks;
    }
    mic_read_seq_ = seq;
    mic_read_off_ = off;
    return PullResult::kOk;
}

SoftwareAecReference::Stats SoftwareAecReference::GetStats() {
    Stats snapshot = stats_;
    if (anchor_count_ > 0 && mic_clock_.locked) {
        snapshot.last_offset_us = static_cast<int32_t>(NewestRefTimeUs() - mic_clock_.t_end_us);
    }
    stats_.ref_peak = 0;
    return snapshot;
}
