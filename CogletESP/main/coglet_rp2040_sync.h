// Coglet: keep the RP2040's program in sync with the ESP32-S3 firmware.
//
// The ESP firmware carries the whole RP2040 program (CogletESP/RP2040/*.py,
// packed at build time by tools/rp2040_bundle/build_bundle.py). Shortly after
// boot the ESP asks the RP2040 for its bundle id over the existing UART link;
// if it differs, the ESP sends every file and the RP2040 (coglet_updater.py)
// stages, verifies and commits them, then restarts. Users only ever flash the
// ESP; the board's USB switch can stay on ESP.
//
// The protocol logic (Sync) is plain C++ behind the Link interface so it can
// be tested on a PC; the ESP UART link and the boot task live in
// coglet_rp2040_sync.cc.
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace CogletRp2040 {

struct BundleFile {
    const char* name;
    const uint8_t* data;
    size_t size;
    uint32_t crc32;
};

// Generated (build/coglet_rp2040/coglet_rp2040_bundle.cc).
extern const char* const kBundleId;
extern const BundleFile* const kBundleFiles;
extern const size_t kBundleFileCount;

class Link {
public:
    virtual ~Link() = default;
    // Send one protocol line (no line ending).
    virtual void SendLine(const std::string& line) = 0;
    // Next line starting with "upd:" within timeout_ms; false on timeout.
    virtual bool ReadLine(std::string& line, int timeout_ms) = 0;
    virtual void Log(const std::string& message) = 0;
};

enum class SyncResult {
    UpToDate,     // RP2040 already runs this bundle
    Updated,      // files sent and committed; the RP2040 restarts
    NoUpdater,    // no answer: RP2040 needs the one-time setup (web flasher)
    Failed,       // transfer failed; nothing was changed on the RP2040
};

const char* ToString(SyncResult result);

// Runs the whole check / transfer. Blocking; call from its own task.
SyncResult Sync(Link& link, const char* bundle_id, const BundleFile* files, size_t file_count);

#ifdef ESP_PLATFORM
// Starts the background task that syncs the RP2040 a few seconds after boot.
void StartSyncTask();
#endif

}  // namespace CogletRp2040
