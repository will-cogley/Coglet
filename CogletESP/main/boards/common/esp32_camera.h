#pragma once
#include "sdkconfig.h"
#include <cstdint>

#ifndef CONFIG_IDF_TARGET_ESP32
#include <lvgl.h>
#include <thread>
#include <memory>
#include <vector>

#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

#include "camera.h"
#include "jpg/image_to_jpeg.h"
#include "esp_video_init.h"

struct JpegChunk {
    uint8_t* data;
    size_t len;
};

class Esp32Camera : public Camera {
private:
    struct FrameBuffer {
        uint8_t *data = nullptr;
        size_t len = 0;
        uint16_t width = 0;
        uint16_t height = 0;
        v4l2_pix_fmt_t format = 0;
    } frame_;
    v4l2_pix_fmt_t sensor_format_ = 0;
#ifdef CONFIG_XIAOZHI_ENABLE_ROTATE_CAMERA_IMAGE
    uint16_t sensor_width_ = 0;
    uint16_t sensor_height_ = 0;
#endif  // CONFIG_XIAOZHI_ENABLE_ROTATE_CAMERA_IMAGE
    int video_fd_ = -1;
    bool streaming_on_ = false;
    bool video_initialized_ = false;
    struct MmapBuffer { void *start = nullptr; size_t length = 0; };
    std::vector<MmapBuffer> mmap_buffers_;
    std::string explain_url_;
    std::string explain_token_;
    std::thread encoder_thread_;

    bool SensorPrivateIoctl(uint32_t command, void* data, size_t size, bool write);
    bool ReadSensorRegister(uint16_t reg, uint8_t& value);
    bool WriteSensorRegister(uint16_t reg, uint8_t value);
#ifdef CONFIG_BOARD_TYPE_BREAD_COMPACT_WIFI_CAM
    bool ApplyCogletGc0308VendorProfile();
#endif

public:
    Esp32Camera(const esp_video_init_config_t& config);
    ~Esp32Camera() override;

    virtual void SetExplainUrl(const std::string& url, const std::string& token);
    virtual bool Capture();
    // 翻转控制函数
    virtual bool SetHMirror(bool enabled) override;
    virtual bool SetVFlip(bool enabled) override;

    // Restore the GC0308 internal ISP to a controlled automatic baseline:
    // AEC + AWB + AGC enabled, normal color effect, factory WB seed gains.
    bool SetGc0308FactoryAuto();

    bool IsInitialized() const { return video_initialized_ && video_fd_ >= 0; }
    virtual std::string Explain(const std::string& question);
};

#endif // ndef CONFIG_IDF_TARGET_ESP32