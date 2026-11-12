// Host test: the real ESP-side Sync() talking to the real RP2040 updater
// (rp_sim.py) over pipes.
#include "coglet_rp2040_sync.h"

#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>

using namespace CogletRp2040;

class PipeLink : public Link {
public:
    PipeLink(const std::string& fs, const std::string& mode) {
        int to_child[2], from_child[2];
        pipe(to_child);
        pipe(from_child);
        pid_ = fork();
        if (pid_ == 0) {
            dup2(to_child[0], 0);
            dup2(from_child[1], 1);
            close(to_child[1]);
            close(from_child[0]);
            execlp("python3", "python3", "-I", SIM_PATH, fs.c_str(), mode.c_str(), (char*)nullptr);
            _exit(127);
        }
        close(to_child[0]);
        close(from_child[1]);
        out_ = to_child[1];
        in_ = from_child[0];
    }
    ~PipeLink() override {
        SendLine("upd:quit");
        close(out_);
        int st;
        waitpid(pid_, &st, 0);
    }
    void SendLine(const std::string& line) override {
        std::string s = line + "\r\n";
        write(out_, s.data(), s.size());
        if (line.compare(0, 6, "upd:d:") == 0) chunks++;
        // normal state lines from the main loop are mixed in on the real link
        if (++sent_ % 37 == 0) { const char* noise = "speaking\r\n"; write(out_, noise, strlen(noise)); }
    }
    bool ReadLine(std::string& line, int timeout_ms) override {
        auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
        for (;;) {
            size_t nl;
            while ((nl = buf_.find('\n')) != std::string::npos) {
                std::string c = buf_.substr(0, nl);
                buf_.erase(0, nl + 1);
                if (c.compare(0, 4, "upd:") == 0) { line = c; return true; }
            }
            int left = (int)std::chrono::duration_cast<std::chrono::milliseconds>(deadline - std::chrono::steady_clock::now()).count();
            if (left <= 0) return false;
            pollfd p{in_, POLLIN, 0};
            if (poll(&p, 1, left) > 0) {
                char tmp[512];
                ssize_t n = read(in_, tmp, sizeof(tmp));
                if (n > 0) buf_.append(tmp, n); else return false;
            }
        }
    }
    void Log(const std::string& m) override { logs += m + "\n"; }
    std::string logs;
    int chunks = 0;
private:
    pid_t pid_;
    int out_, in_;
    int sent_ = 0;
    std::string buf_;
};

static std::string ReadFile(const std::string& p) {
    std::ifstream f(p, std::ios::binary);
    std::stringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

static bool FsMatchesBundle(const std::string& fs) {
    for (size_t i = 0; i < kBundleFileCount; ++i) {
        const auto& b = kBundleFiles[i];
        std::string got = ReadFile(fs + "/" + b.name);
        if (got.size() != b.size || memcmp(got.data(), b.data, b.size) != 0) {
            printf("   mismatch: %s\n", b.name);
            return false;
        }
    }
    std::string id = ReadFile(fs + "/coglet_bundle.txt");
    return id == kBundleId;
}

int main(int argc, char** argv) {
    const std::string root = argv[1];
    int fails = 0;
    auto run = [&](const char* label, const std::string& fs, const char* mode, SyncResult want,
                   bool expect_fs_ok) {
        system(("mkdir -p '" + fs + "'").c_str());
        auto t0 = std::chrono::steady_clock::now();
        SyncResult got;
        int chunks;
        std::string logs;
        {
            PipeLink link(fs, mode);
            got = Sync(link, kBundleId, kBundleFiles, kBundleFileCount);
            chunks = link.chunks;
            logs = link.logs;
        }
        double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        bool fs_ok = FsMatchesBundle(fs);
        bool ok = got == want && fs_ok == expect_fs_ok;
        printf("%-34s result=%-12s chunks=%-4d files_ok=%d  %.1fs  %s\n", label, ToString(got), chunks,
               fs_ok, secs, ok ? "OK" : "FAIL");
        if (!ok) printf("%s", logs.c_str());
        fails += !ok;
    };
    // 1. RP2040 with the updater but an older program -> full update
    std::string fs1 = root + "/fresh";
    run("fresh RP2040 (bundle none)", fs1, "normal", SyncResult::Updated, true);
    // 2. same RP2040 again -> nothing sent
    run("second boot (same bundle)", fs1, "normal", SyncResult::UpToDate, true);
    // 3. old RP2040 program without updater
    run("RP2040 without updater", root + "/old", "no_updater", SyncResult::NoUpdater, false);
    // 4. one ack lost on the wire -> retransmit, duplicate detected
    run("lost ack", root + "/lost", "lose_ack", SyncResult::Updated, true);
    // 5. power cut in the middle of the commit -> boot finishes the commit
    std::string fs5 = root + "/cut";
    run("power cut during commit", fs5, "power_cut", SyncResult::Failed, true);
    run("  next boot after the power cut", fs5, "normal", SyncResult::UpToDate, true);
    // 6. a staged update must not leave .new files behind
    int leftovers = system(("ls '" + root + "'/*/*.new >/dev/null 2>&1").c_str()) == 0;
    printf("%-34s %s\n", "no .new files left behind", leftovers ? "FAIL" : "OK");
    fails += leftovers;
    printf("FAILURES: %d\n", fails);
    return fails ? 1 : 0;
}
