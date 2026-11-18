# Coglet 设备端 AEC（软件参考 / 数字回采）

## 它做了什么

Coglet 的麦克风（SPH0645）和功放（MAX98357A）分别挂在两组独立的 I2S 上，没有硬件回采通道，所以官方的设备端 AEC 原本开不了。

本方案在 ESP32-S3 上本地运行，**不依赖服务端 AEC**：

1. 喇叭 I2S 的 TX DMA 每发完一块 PCM（10 ms），`on_sent` 回调都能拿到这块数据。这时驱动还没清零，所以拿到的就是真正送进功放的那一块。
2. 麦克风 I2S 的 RX DMA 每收完一块（15 ms），`on_recv` 回调同样拿到数据。
3. 两个回调都用 `esp_timer` 打时间戳。`SoftwareAecReference` 用一个“下包络 + 实测采样周期”的时钟跟踪器平滑时间戳，再给每个麦克风样本配上**同一时刻**正在播放的喇叭样本，并完成 24 kHz → 16 kHz 抗混叠重采样。
4. `Read()` 输出交织的 `[mic, ref]` 两路，也就是 esp-sr AFE AEC 需要的 `MR` 格式。
5. 开启 AEC 后，所有唤醒路径都进入 **realtime 模式**，包括开机自动唤醒，Coglet 说话时可以被打断。

关闭该选项时，编译出的固件与原版行为完全一致：原有的单声道读取路径一行没改。

## 开启方法

```
idf.py menuconfig
  Xiaozhi Assistant →
    [*] Enable Device-Side AEC
    (0)   Coglet AEC reference delay (ms)     ← 先保持 0
idf.py build flash monitor
```

注意：不要同时开启 “Server-Side AEC”，两者互斥，同时开会编译报错。

## 上机后看什么

### 1. 启动日志里应出现

```
NoAudioCodec: [AEC-REF] software loopback ENABLED: mic 16000 Hz (slot 0/2), speaker 24000 Hz ...
AfeAudioProcessor: ... feed size ...        （不应出现 "no reference channel"）
CogletAutoAwake: BOOT_LISTENING: mode=realtime
```

### 2. 每秒一行诊断

Since this line is off by default, turn on menuconfig → "Coglet: log microphone levels every second" (`CONFIG_COGLET_MIC_DIAG_LOG`) first.

```
[MIC] mode=aec-ref ... | [AEC-REF] refPeak=... offset=..us missing=.. late=.. micOvr=.. refOvr=.. resync=a/b torn=..
```

| 字段 | 正常表现 |
|---|---|
| `refPeak` | Coglet 说话时明显大于 0；静音时为 0 |
| `offset` | 稳定在几毫秒以内（这只是两路最新块的时间差，**稳定**比绝对值重要） |
| `missing` / `late` | 基本不增长；偶尔增长一点是丢中断，可以接受 |
| `micOvr` | 在唤醒词和对话切换时会增加，属正常 |
| `resync` | 启动时各 1，之后基本不变 |
| `torn` | 应始终为 0 |

### 3. 主观测试

- 让 Coglet 说一段长回答，中途正常说话打断：应能打断，而且识别出的文字正确。
- Coglet 说话时你不出声：它**不应**自己打断自己。
- 对比之前 ChatGPT 那版：重点看“偶发拾字错误”是否减少。

## 如果效果不理想：抓音频看对齐

1. menuconfig 开启 `Enable Audio Debugger`，把地址设为电脑的 `IP:8000`。
2. 在电脑上运行 `python scripts/audio_debug_server.py`，默认参数就是 16 kHz、2 声道。
3. 让 Coglet 说话，然后用 Audacity 打开生成的 WAV：**左声道是麦克风，右声道是参考信号**。
4. 放大波形看：麦克风里的回声应**略晚于**参考信号（约 0–3 ms）。
   - 回声比参考信号**更早**：把 `Coglet AEC reference delay` 调成负数（-1、-2……）。
   - 回声晚了很多（超过 10 ms）：说明时间戳有偏差，把这段录音发给我看。

## 已知限制（下一步）

- **舵机噪声**：说话时嘴、耳、脖子都在动，齿轮声不是回声，AEC 消不掉，可能造成误打断。如果出现这种情况，下一步可以在 RP2040 侧降低说话期间的舵机速度，或在 ESP 侧加门控。
- **音量与失真**：音量开得很大时，小喇叭和外壳振动产生的非线性失真 AEC 消不干净。必要时可适当降低音量，或给麦克风做物理隔振。
- AEC 模式下 AFE 的本地 VAD 是关闭的（与上游 ESP-Box 等板一致），由服务器判断语音的开始和结束。

## 相关文件

- `main/audio/codecs/software_aec_reference.{h,cc}`：时间对齐核心，不依赖 IDF，可在电脑上测试。
- `main/audio/codecs/no_audio_codec.{h,cc}`：注册 DMA 回调，提供 `EnableSoftwareAecReference()` 和 `MR` 输出。
- `main/boards/bread-compact-wifi-s3cam/compact_wifi_board_s3cam.cc`：在 `CONFIG_USE_DEVICE_AEC` 打开时启用软件参考。
- `main/audio/processors/afe_audio_processor.cc`：没有参考通道时自动回退，不开 AEC。
- `main/application.cc`：开机自动唤醒在 AEC 模式下使用 realtime。
- `main/Kconfig.projbuild`：允许 Coglet 板开启设备端 AEC，并新增延迟参数。
- `tests/host/`：电脑端仿真测试，覆盖时钟漂移 ±200 ppm、中断延迟尖峰、丢中断、读取卡顿，运行 `sh tests/host/run_software_aec_reference_test.sh`。

## Web flasher switch (Talk over Coglet)

The published firmware is built with `CONFIG_USE_DEVICE_AEC=y` and
`CONFIG_COGLET_AEC_DEFAULT_OFF=y`: AEC is compiled in but stays off until the
web flasher's Settings turn on **Talk over Coglet** (settings key `aec=on`).
The choice is read once at boot (`CogletSettings::DeviceAec()`); when it is
off, the software reference is not started and the AFE runs with VAD, exactly
as without AEC. If the reference can't be allocated, Coglet logs
`Device AEC unavailable on this boot` and falls back to the normal listening
mode. Leave `COGLET_AEC_DEFAULT_OFF` unset in menuconfig to have AEC on by
default (the web switch still works both ways).

