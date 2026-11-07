#!/usr/bin/env python3
"""Coglet "Music" folder builder.

Runs automatically from main/CMakeLists.txt on every `idf.py build` (it only
does real work when a file in the Music folder changed). For every audio file
in the Music folder it:

  1. transcodes the song to the format Coglet plays (Ogg/Opus, mono, 24 kHz,
     60 ms frames) with ffmpeg, trimmed to --max-seconds with a fade-out;
  2. analyses it: tempo, beat times, per-beat accent strength, section energy,
     bar starts, and picks a dance preset ("energetic" or "calm");
  3. writes one C++ source with every song + its beat map, which the firmware
     compiles in (see main/coglet_music.h).

Only the Python standard library is used; the one external tool is ffmpeg
(with libopus). If ffmpeg is missing, an empty song table is generated and the
build continues with a warning.

Force a preset with the file name:  "My Song.calm.mp3", "Drop.energetic.wav".

Usage (normally called by CMake):
  python build_music.py --src <Music dir> --out <build dir>
                        [--ffmpeg ffmpeg] [--max-seconds 60] [--bitrate 32]
                        [--max-kb 1500]
"""
import argparse
import array
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys

ANALYSIS_VERSION = 6          # bump to invalidate cached analysis
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma", ".aiff", ".aif",
              ".mp4", ".mov", ".m4v", ".webm", ".mkv"}   # video files: the audio track is used
SR = 11025                    # analysis sample rate
HOP = 256                     # analysis hop (23.2 ms)
FPS = SR / HOP
PRESETS = ("calm", "energetic")


def log(msg):
    print("[coglet-music] " + msg, flush=True)


def warn(msg):
    # "warning:" makes the line stand out in the ESP-IDF / Ninja build log.
    print("[coglet-music] warning: " + msg, flush=True)


# ============================================================ ffmpeg
def find_ffmpeg(hint):
    for cand in (hint, "ffmpeg", "ffmpeg.exe"):
        if not cand:
            continue
        if os.path.isfile(cand):
            return cand
        found = shutil.which(cand)
        if found:
            return found
    return None


def run(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip()[-600:])
    return proc.stdout


# Analysis bands (Hz). Band 0 is the "lows" (kick / bass) band.
BANDS = ((0, 150), (150, 400), (400, 1000), (1000, 2500), (2500, 5400))


def decode_analysis_pcm(ffmpeg, path, max_seconds):
    """Mono 11 kHz PCM, split by ffmpeg into len(BANDS) interleaved band channels."""
    fmt = "aformat=sample_fmts=flt:sample_rates={sr}:channel_layouts=mono".format(sr=SR)
    nb = len(BANDS)
    labels = "".join("[s{}]".format(i) for i in range(nb))
    graph = ["[0:a]aresample={sr},{fmt},asplit={n}{labels}".format(sr=SR, fmt=fmt, n=nb, labels=labels)]
    for i, (lo, hi) in enumerate(BANDS):
        chain = []
        if lo > 0:
            chain += ["highpass=f={}".format(lo), "highpass=f={}".format(lo)]
        if hi < SR / 2 - 200:
            chain += ["lowpass=f={}".format(hi), "lowpass=f={}".format(hi)]
        graph.append("[s{i}]{c},{fmt}[b{i}]".format(i=i, c=",".join(chain), fmt=fmt))
    graph.append("{}amerge=inputs={},aformat=sample_fmts=s16[out]".format(
        "".join("[b{}]".format(i) for i in range(nb)), nb))
    raw = run([ffmpeg, "-v", "error", "-nostdin", "-i", path, "-t", str(max_seconds),
               "-filter_complex", ";".join(graph), "-map", "[out]",
               "-f", "s16le", "-acodec", "pcm_s16le", "-"])
    pcm = array.array("h")
    pcm.frombytes(raw[: len(raw) - len(raw) % (2 * nb)])
    if sys.byteorder == "big":
        pcm.byteswap()
    return [pcm[i::nb] for i in range(nb)]


def transcode(ffmpeg, path, dst, seconds, trimmed, bitrate):
    fade = 2.5 if trimmed else 0.3
    fade_start = max(0.0, seconds - fade)
    af = ("highpass=f=110,afade=t=out:st={:.3f}:d={:.3f},"
          "loudnorm=I=-14:TP=-1.5:LRA=11").format(fade_start, fade)
    run([ffmpeg, "-v", "error", "-nostdin", "-y", "-i", path, "-t", "{:.3f}".format(seconds),
         "-vn", "-af", af, "-ac", "1", "-ar", "24000",
         "-c:a", "libopus", "-b:a", "{}k".format(bitrate), "-frame_duration", "60",
         "-application", "audio", "-f", "ogg", dst])


def check_ogg(data):
    """Make sure the file matches what AudioService::PlaySound() expects."""
    pos = 0
    head = None
    packets = 0
    bad_frames = 0
    while pos + 27 <= len(data):
        if data[pos:pos + 4] != b"OggS":
            raise RuntimeError("broken Ogg page at byte {}".format(pos))
        nseg = data[pos + 26]
        segs = data[pos + 27:pos + 27 + nseg]
        body = pos + 27 + nseg
        cur = b""
        for s in segs:
            cur += data[body:body + s]
            body += s
            if s < 255:
                if cur.startswith(b"OpusHead"):
                    head = cur
                elif not cur.startswith(b"OpusTags") and cur:
                    packets += 1
                    config = cur[0] >> 3
                    # 60 ms = CELT/SILK config with 2x... TOC code 3 or a
                    # single 60 ms SILK/hybrid frame; accept anything that
                    # decodes to 60 ms in total.
                    if _toc_duration_ms(cur) != 60:
                        bad_frames += 1
                    del config
                cur = b""
        pos = body
    if head is None:
        raise RuntimeError("no OpusHead")
    channels = head[9]
    rate = struct.unpack("<I", head[12:16])[0]
    if channels != 1 or rate not in (8000, 12000, 16000, 24000, 48000):
        raise RuntimeError("unexpected OpusHead channels={} rate={}".format(channels, rate))
    if bad_frames > 2:
        raise RuntimeError("{} packets are not 60 ms".format(bad_frames))
    return packets


def _toc_duration_ms(pkt):
    toc = pkt[0]
    config = toc >> 3
    if config < 12:                      # SILK: 10/20/40/60
        frame = (10, 20, 40, 60)[config & 3]
    elif config < 16:                    # Hybrid: 10/20
        frame = (10, 20)[config & 1]
    else:                                # CELT: 2.5/5/10/20
        frame = (2.5, 5, 10, 20)[config & 3]
    code = toc & 3
    if code == 0:
        n = 1
    elif code in (1, 2):
        n = 2
    else:
        n = (pkt[1] & 0x3F) if len(pkt) > 1 else 1
    return int(round(frame * n))


# ============================================================ analysis
def percentile(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]


def frame_energy(x):
    """Mean square per hop, in dB."""
    out = []
    n = len(x) // HOP
    for i in range(n):
        seg = x[i * HOP:(i + 1) * HOP]
        ms = sum(v * v for v in seg) / HOP
        out.append(10.0 * math.log10(ms + 1.0))
    return out


def onset_env(db):
    """Positive change in level vs. the max of the two previous frames."""
    o = [0.0, 0.0]
    for i in range(2, len(db)):
        o.append(max(0.0, db[i] - max(db[i - 1], db[i - 2])))
    return o


def normalise(v, p=95):
    ref = percentile(v, p) or 1.0
    return [min(3.0, x / ref) for x in v]


def moving_avg(v, half):
    out = []
    acc = 0.0
    q = []
    n = len(v)
    pre = [0.0]
    for x in v:
        pre.append(pre[-1] + x)
    for i in range(n):
        a = max(0, i - half)
        b = min(n, i + half + 1)
        out.append((pre[b] - pre[a]) / (b - a))
    del acc, q
    return out


def track_beats(o, period, tightness=400.0):
    """Dynamic-programming beat tracker (Ellis 2007)."""
    n = len(o)
    score = list(o)
    back = [-1] * n
    p = period
    lo = int(round(p * 0.5))
    hi = int(round(p * 2.0))
    for i in range(n):
        best = None
        for j in range(max(0, i - hi), i - lo + 1):
            if j < 0:
                continue
            d = (i - j) / p
            s = score[j] - tightness * (math.log(d)) ** 2
            if best is None or s > best[0]:
                best = (s, j)
        if best is not None and best[0] > 0:
            score[i] = o[i] + best[0]
            back[i] = best[1]
    # best end point in the last period
    tail = range(max(0, n - int(p * 1.5)), n)
    i = max(tail, key=lambda k: score[k])
    beats = []
    while i >= 0:
        beats.append(i)
        i = back[i]
    beats.reverse()
    # extend backwards / forwards at the tracked period if the tracker
    # started late or stopped early
    while beats and beats[0] - p > 0:
        beats.insert(0, int(round(beats[0] - p)))
    while beats and beats[-1] + p < n - 1:
        beats.append(int(round(beats[-1] + p)))
    return beats


def tempo_candidates(o):
    """Autocorrelation peaks (beat periods in frames) between 55 and 190 BPM."""
    lo_lag = int(FPS * 60.0 / 190.0)
    hi_lag = int(FPS * 60.0 / 55.0) + 2
    n = len(o)
    ac = {}
    for lag in range(lo_lag - 1, hi_lag + 2):
        ac[lag] = sum(o[i] * o[i + lag] for i in range(n - lag)) / max(1, n - lag)
    peaks = [lag for lag in range(lo_lag, hi_lag + 1) if ac[lag] >= ac[lag - 1] and ac[lag] >= ac[lag + 1]]
    peaks.sort(key=lambda k: ac[k], reverse=True)
    out = []
    for lag in peaks[:3]:
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
        den = y0 - 2 * y1 + y2
        shift = 0.5 * (y0 - y2) / den if den < 0 else 0.0
        out.append(lag + max(-0.5, min(0.5, shift)))
    return out


def tempo_prior(bpm):
    return math.exp(-0.5 * (math.log2(bpm / 110.0) / 1.0) ** 2)


def choose_tempo(o, forced_bpm=None):
    """Pick the beat period whose tracked beats land on the strongest onsets.

    Candidates are the autocorrelation peaks plus their double / half. A slower
    candidate only wins when its beats are clearly stronger (the "felt" pulse,
    e.g. a slow piano ballad with running 8th notes, or half-time trap).
    """
    n = len(o)
    ac_cache = {}

    def ac(lag):
        lag = int(round(lag))
        if lag >= n - 10:
            return 0.0
        if lag not in ac_cache:
            ac_cache[lag] = max(
                sum(o[i] * o[i + k] for i in range(n - k)) / (n - k) for k in (lag - 1, lag, lag + 1))
        return ac_cache[lag]

    cands = set()
    if forced_bpm:
        cands.add(round(60.0 * FPS / forced_bpm, 2))
    else:
        for p in tempo_candidates(o):
            for m in (0.5, 1.0, 2.0, 2.0 / 3.0, 1.5):
                q = p * m
                bpm = 60.0 * FPS / q
                if 55.0 <= bpm <= 190.0:
                    cands.add(round(q, 2))
    best = None
    for q in sorted(cands):
        beats = track_beats(o, q)
        if len(beats) < 4:
            continue
        mean_at = sum(max(o[max(0, b - 1):b + 2]) for b in beats) / len(beats)
        # A real beat also lines up with 2-beat, bar and 2-bar repetitions.
        comb = ac(2 * q) + ac(4 * q) + ac(8 * q)
        score = mean_at * comb * tempo_prior(60.0 * FPS / q) ** 1.5
        if best is None or score > best[0]:
            best = (score, q, beats)
    return best[1], best[2]


def analyse(bands, duration_s, forced_preset=None, forced_bpm=None):
    dbs = [frame_energy(b) for b in bands]
    onsets = [normalise(onset_env(d)) for d in dbs]
    weights = (1.3, 1.0, 0.9, 0.8, 0.7)
    combo = [sum(w * v for w, v in zip(weights, col)) for col in zip(*onsets)]
    base = moving_avg(combo, 12)
    o = [max(0.0, a - b) for a, b in zip(combo, base)]
    o_lo = onsets[0]
    o_hi = onsets[-1]
    db_full = [10.0 * math.log10(sum(10 ** (d / 10.0) for d in col) + 1.0) for col in zip(*dbs)]

    period, beats = choose_tempo(o, forced_bpm)
    bpm = 60.0 * FPS / period

    # ---- per-beat accent, section energy, bars
    def local_max(env, i, w=2):
        return max(env[max(0, i - w):min(len(env), i + w + 1)] or [0.0])

    acc = [local_max(o, b) for b in beats]
    acc_ref = percentile(acc, 90) or 1.0
    lo_at = [local_max(o_lo, b) for b in beats]
    hi_at = [local_max(o_hi, b) for b in beats]

    smooth = moving_avg(db_full, int(FPS))          # ~2 s window
    e_at = [smooth[min(len(smooth) - 1, b)] for b in beats]
    e_lo, e_hi = percentile(e_at, 10), percentile(e_at, 95)
    span = max(3.0, e_hi - e_lo)

    # ---- preset (a best guess; override with ".calm" / ".energetic" in the file name)
    secs = max(1.0, duration_s)
    kick_rate = sum(1 for v in lo_at if v > 0.6) / secs
    hat_rate = sum(1 for v in o_hi if v > 0.5) / secs
    punch = sum(abs(db_full[i] - db_full[i - 1]) for i in range(1, len(db_full))) / max(1, len(db_full) - 1)
    auto = "energetic" if (bpm >= 88.0 and punch >= 0.95) else "calm"
    preset = forced_preset or auto

    # Calm songs dance on the slow, felt pulse: halve fast tempos, keeping the
    # half of the beats with the stronger low end.
    keep = list(range(len(beats)))
    felt_bpm = bpm
    if preset == "calm" and bpm > 95.0:
        even = sum(lo_at[0::2]) + sum(acc[0::2])
        odd = sum(lo_at[1::2]) + sum(acc[1::2])
        half = 0 if even >= odd else 1
        keep = [i for i in keep if i % 2 == half]
        felt_bpm = bpm / 2.0

    # Bar starts among the beats we keep: the phase (of 4) with the strongest lows.
    k_phase = max(range(4), key=lambda k: sum(lo_at[keep[j]] for j in range(k, len(keep), 4)))
    out = []
    for j, i in enumerate(keep):
        t_ms = int(round(beats[i] * 1000.0 / FPS))
        if t_ms > duration_s * 1000 - 150:
            break
        strength = int(round(9 * min(1.0, acc[i] / acc_ref)))
        energy = int(round(9 * min(1.0, max(0.0, (e_at[i] - e_lo) / span))))
        flags = 1 if (j - k_phase) % 4 == 0 else 0
        out.append((t_ms, strength, energy, flags))

    info = {
        "bpm": round(bpm, 1),
        "felt_bpm": round(felt_bpm, 1),
        "preset": preset,
        "auto_preset": auto,
        "punch": round(punch, 2),
        "kick_rate": round(kick_rate, 2),
        "hat_rate": round(hat_rate, 2),
        "dynamic_db": round(span, 1),
    }
    return out, info


# ============================================================ songs
def parse_name(filename):
    """'Night Rain.calm.68bpm.mp3' -> ('Night Rain', 'calm', 68.0, '.mp3').

    Optional tags after the title, in any order: calm | energetic | <N>bpm.
    """
    stem, ext = os.path.splitext(filename)
    forced = None
    bpm = None
    while "." in stem:
        head, tag = stem.rsplit(".", 1)
        t = tag.strip().lower()
        if t in PRESETS:
            forced = t
        elif t.endswith("bpm") and t[:-3].replace(".", "", 1).isdigit() and 40 <= float(t[:-3]) <= 220:
            bpm = float(t[:-3])
        else:
            break
        stem = head
    return stem.strip(), forced, bpm, ext.lower()


def sha1_file(path, extra):
    h = hashlib.sha1()
    h.update(extra.encode())
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def process(ffmpeg, path, name, forced, forced_bpm, cache_dir, max_seconds, bitrate):
    key = sha1_file(path, "v{}|{}|{}|{}|{}".format(ANALYSIS_VERSION, max_seconds, bitrate, forced, forced_bpm))
    ogg_path = os.path.join(cache_dir, key + ".ogg")
    meta_path = os.path.join(cache_dir, key + ".json")
    if os.path.isfile(ogg_path) and os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        meta["cached"] = True
        meta["key"] = key
        return ogg_path, meta

    bands = decode_analysis_pcm(ffmpeg, path, max_seconds + 1)
    total = len(bands[0]) / float(SR)
    seconds = min(total, float(max_seconds))
    if seconds < 3.0:
        raise RuntimeError("too short ({:.1f} s)".format(seconds))
    trimmed = total > max_seconds + 0.5
    n = int(seconds * SR)
    beats, info = analyse([b[:n] for b in bands], seconds, forced, forced_bpm)

    tmp = ogg_path + ".tmp.ogg"
    transcode(ffmpeg, path, tmp, seconds, trimmed, bitrate)
    with open(tmp, "rb") as f:
        packets = check_ogg(f.read())
    os.replace(tmp, ogg_path)

    meta = dict(info)
    meta.update({"name": name, "duration_ms": int(seconds * 1000), "beats": beats,
                 "packets": packets, "trimmed": trimmed})
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    meta["cached"] = False
    meta["key"] = key
    return ogg_path, meta


# ============================================================ C++ output
def c_string(s):
    out = []
    for b in s.encode("utf-8"):
        if 32 <= b < 127 and chr(b) not in '"\\?':
            out.append(chr(b))
        else:
            out.append("\\{:03o}".format(b))
    return '"' + "".join(out) + '"'


def c_bytes(data, width=64):
    lines = []
    for i in range(0, len(data), width):
        lines.append('    "' + "".join("\\x{:02x}".format(b) for b in data[i:i + width]) + '"')
    return "\n".join(lines) if lines else '    ""'


def write_source(path, songs):
    parts = [
        "// GENERATED by tools/coglet_music/build_music.py from the Music folder.",
        "// Do not edit and do not commit: it is rebuilt on every build.",
        '#include "coglet_music.h"',
        "",
        "namespace {",
    ]
    for i, (meta, ogg) in enumerate(songs):
        parts.append("// {} -- {} BPM, {}, {} beats".format(
            meta["name"].replace("\n", " "), meta["felt_bpm"], meta["preset"], len(meta["beats"])))
        parts.append("const char kOgg{}[] =\n{};".format(i, c_bytes(ogg)))
        beats = ",".join("{{{},{},{},{}}}".format(*b) for b in meta["beats"])
        parts.append("const CogletMusic::Beat kBeats{}[] = {{{}}};".format(i, beats or "{0,0,0,0}"))
    if songs:
        parts.append("const CogletMusic::Song kTable[] = {")
        for i, (meta, ogg) in enumerate(songs):
            parts.append(
                "    {{{name}, CogletMusic::Preset::{preset}, {bpm}, {dur}, "
                "reinterpret_cast<const uint8_t*>(kOgg{i}), {size}, kBeats{i}, {nb}}},".format(
                    name=c_string(meta["name"]),
                    preset="Energetic" if meta["preset"] == "energetic" else "Calm",
                    bpm=int(round(meta["felt_bpm"])),
                    dur=meta["duration_ms"], i=i, size=len(ogg), nb=len(meta["beats"])))
        parts.append("};")
    parts.append("}  // namespace")
    parts.append("")
    parts.append("namespace CogletMusic {")
    if songs:
        parts.append("const Song* const kSongs = kTable;")
        parts.append("const size_t kSongCount = sizeof(kTable) / sizeof(kTable[0]);")
    else:
        parts.append("const Song* const kSongs = nullptr;")
        parts.append("const size_t kSongCount = 0;")
    parts.append("}  // namespace CogletMusic")
    data = "\n".join(parts) + "\n"
    # Only touch the file when it changed: the build runs this script every
    # time and Ninja then skips recompiling an unchanged source ("restat").
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == data:
                return False
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)
    return True


# ============================================================ main
def main(argv=None):
    # Song names may contain characters the Windows console code page cannot
    # print; never let logging break the build.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--max-seconds", type=int, default=60)
    ap.add_argument("--bitrate", type=int, default=32)
    ap.add_argument("--max-kb", type=int, default=1500)
    ap.add_argument("--stamp", help="file to touch when done (for CMake)")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    cache_dir = os.path.join(args.out, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    out_cc = os.path.join(args.out, "coglet_music_data.cc")

    files = []
    if os.path.isdir(args.src):
        for fn in sorted(os.listdir(args.src), key=lambda s: s.lower()):
            name, forced, forced_bpm, ext = parse_name(fn)
            if ext in AUDIO_EXTS and not fn.startswith("."):
                files.append((fn, name, forced, forced_bpm))

    songs = []
    if files:
        ffmpeg = find_ffmpeg(args.ffmpeg)
        if not ffmpeg:
            warn("ffmpeg not found, {} song(s) in {} were skipped. Install ffmpeg (with libopus) "
                 "and add it to PATH, or set the path in menuconfig -> NMRobotics Coglet Dance."
                 .format(len(files), args.src))
        else:
            total = 0
            names = set()
            for fn, name, forced, forced_bpm in files:
                if name.lower() in names:
                    warn("skipping {}: another song is already called '{}'".format(fn, name))
                    continue
                try:
                    ogg_path, meta = process(ffmpeg, os.path.join(args.src, fn), name, forced, forced_bpm,
                                             cache_dir, args.max_seconds, args.bitrate)
                except Exception as exc:          # one bad file must not break the build
                    warn("skipping {}: {}".format(fn, exc))
                    continue
                with open(ogg_path, "rb") as f:
                    ogg = f.read()
                if (total + len(ogg)) / 1024.0 > args.max_kb:
                    warn("skipping {}: the Music budget of {} KB would be exceeded "
                         "(raise it in menuconfig, or shorten the songs)".format(fn, args.max_kb))
                    continue
                total += len(ogg)
                names.add(name.lower())
                songs.append((meta, ogg))
                log("{:<28} {:>5.1f} s  {:>5.1f} BPM  {:<9} {:>3} beats  {:>4} KB{}{}".format(
                    name[:28], meta["duration_ms"] / 1000.0, meta["felt_bpm"], meta["preset"],
                    len(meta["beats"]), len(ogg) // 1024,
                    "  (trimmed)" if meta["trimmed"] else "",
                    "  (cached)" if meta["cached"] else ""))
            log("{} song(s), {} KB of flash".format(len(songs), total // 1024))
    else:
        log("no songs in {}".format(args.src))

    # Drop cached conversions of songs that were removed or changed.
    used = {meta["key"] for meta, _ in songs}
    for fn in os.listdir(cache_dir):
        if os.path.splitext(fn)[0].split(".")[0] not in used:
            try:
                os.remove(os.path.join(cache_dir, fn))
            except OSError:
                pass

    write_source(out_cc, songs)
    if args.stamp:
        with open(args.stamp, "w") as f:
            f.write("ok\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
