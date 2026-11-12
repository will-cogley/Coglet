// Coglet "My songs": turn an audio file into a song Coglet can dance to, in
// the browser, and manage the song library in Coglet's flash.
//
//  * analyseBands()/analyse11k(): a line-by-line port of the beat analysis in
//    tools/coglet_music/build_music.py (tests/song_library checks they agree);
//  * encodeSong(): decode, trim, level and encode to Ogg/Opus (mono, 24 kHz,
//    60 ms frames) with WebCodecs - the format AudioService::PlaySound() plays;
//  * library helpers: the flash layout described in main/coglet_music.h.
//
// Everything except decodeFile()/encodeSong() is plain JavaScript, so it also
// runs under Node for the tests.

export const SR = 11025;          // analysis sample rate
export const HOP = 256;
export const FPS = SR / HOP;
export const PLAY_RATE = 24000;   // what Coglet plays
export const MAX_NAME_BYTES = 35; // + NUL = 36

// ------------------------------------------------------------ small helpers
// Python's round(): halves go to the even neighbour.
export function pyRound(x) {
  const f = Math.floor(x);
  const d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}
function pyRound2(x) { return pyRound(x * 100) / 100; }

let crcTable = null;
export function crc32(bytes, crc = 0) {
  if (!crcTable) {
    crcTable = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) c = c & 1 ? (c >>> 1) ^ 0xedb88320 : c >>> 1;
      crcTable[i] = c >>> 0;
    }
  }
  crc = (crc ^ 0xffffffff) >>> 0;
  for (let i = 0; i < bytes.length; i++) crc = (crcTable[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8)) >>> 0;
  return (crc ^ 0xffffffff) >>> 0;
}

function percentile(values, p) {
  if (!values.length) return 0;
  const s = Array.from(values).sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.max(0, pyRound((p / 100) * (s.length - 1))))];
}

// ------------------------------------------------------------ band split
// ffmpeg's highpass/lowpass (RBJ biquads, Q = 0.707), each applied twice,
// then converted to 16-bit like the Python tool reads them.
const BANDS = [[0, 150], [150, 400], [400, 1000], [1000, 2500], [2500, 5400]];

function biquad(x, type, f, fs) {
  const w0 = (2 * Math.PI * f) / fs;
  const cos = Math.cos(w0);
  const alpha = Math.sin(w0) / (2 * 0.707);
  let b0, b1, b2;
  if (type === "low") { b0 = (1 - cos) / 2; b1 = 1 - cos; b2 = b0; }
  else { b0 = (1 + cos) / 2; b1 = -(1 + cos); b2 = b0; }
  const a0 = 1 + alpha, a1 = -2 * cos, a2 = 1 - alpha;
  b0 /= a0; b1 /= a0; b2 /= a0;
  const c1 = a1 / a0, c2 = a2 / a0;
  const y = new Float64Array(x.length);
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < x.length; i++) {
    const v = b0 * x[i] + b1 * x1 + b2 * x2 - c1 * y1 - c2 * y2;
    x2 = x1; x1 = x[i]; y2 = y1; y1 = v;
    y[i] = v;
  }
  return y;
}

export function splitBands(mono) {
  return BANDS.map(([lo, hi]) => {
    let x = mono;
    if (lo > 0) x = biquad(biquad(x, "high", lo, SR), "high", lo, SR);
    if (hi < SR / 2 - 200) x = biquad(biquad(x, "low", hi, SR), "low", hi, SR);
    const out = new Int16Array(x.length);
    for (let i = 0; i < x.length; i++) {
      out[i] = Math.max(-32768, Math.min(32767, Math.round(x[i] * 32768)));
    }
    return out;
  });
}

// ------------------------------------------------------------ analysis (port)
function frameEnergy(x) {
  const n = Math.floor(x.length / HOP);
  const out = new Array(n);
  for (let i = 0; i < n; i++) {
    let s = 0;
    for (let k = i * HOP; k < (i + 1) * HOP; k++) s += x[k] * x[k];
    out[i] = 10 * Math.log10(s / HOP + 1);
  }
  return out;
}

function onsetEnv(db) {
  const o = [0, 0];
  for (let i = 2; i < db.length; i++) o.push(Math.max(0, db[i] - Math.max(db[i - 1], db[i - 2])));
  return o;
}

function normalise(v, p = 95) {
  const ref = percentile(v, p) || 1;
  return v.map((x) => Math.min(3, x / ref));
}

function movingAvg(v, half) {
  const n = v.length;
  const pre = [0];
  for (const x of v) pre.push(pre[pre.length - 1] + x);
  const out = new Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.max(0, i - half), b = Math.min(n, i + half + 1);
    out[i] = (pre[b] - pre[a]) / (b - a);
  }
  return out;
}

function trackBeats(o, p, tightness = 400) {
  const n = o.length;
  const score = o.slice();
  const back = new Array(n).fill(-1);
  const lo = pyRound(p * 0.5), hi = pyRound(p * 2.0);
  for (let i = 0; i < n; i++) {
    let bestS = null, bestJ = -1;
    for (let j = Math.max(0, i - hi); j < i - lo + 1; j++) {
      if (j < 0) continue;
      const d = (i - j) / p;
      const s = score[j] - tightness * Math.log(d) ** 2;
      if (bestS === null || s > bestS) { bestS = s; bestJ = j; }
    }
    if (bestS !== null && bestS > 0) { score[i] = o[i] + bestS; back[i] = bestJ; }
  }
  let i = -1, best = -Infinity;
  for (let k = Math.max(0, n - Math.trunc(p * 1.5)); k < n; k++) if (score[k] > best) { best = score[k]; i = k; }
  const beats = [];
  while (i >= 0) { beats.push(i); i = back[i]; }
  beats.reverse();
  while (beats.length && beats[0] - p > 0) beats.unshift(pyRound(beats[0] - p));
  while (beats.length && beats[beats.length - 1] + p < n - 1) beats.push(pyRound(beats[beats.length - 1] + p));
  return beats;
}

function tempoCandidates(o) {
  const loLag = Math.trunc((FPS * 60) / 190);
  const hiLag = Math.trunc((FPS * 60) / 55) + 2;
  const n = o.length;
  const ac = {};
  for (let lag = loLag - 1; lag < hiLag + 2; lag++) {
    let s = 0;
    for (let i = 0; i < n - lag; i++) s += o[i] * o[i + lag];
    ac[lag] = s / Math.max(1, n - lag);
  }
  const peaks = [];
  for (let lag = loLag; lag <= hiLag; lag++) if (ac[lag] >= ac[lag - 1] && ac[lag] >= ac[lag + 1]) peaks.push(lag);
  peaks.sort((a, b) => ac[b] - ac[a]);
  return peaks.slice(0, 3).map((lag) => {
    const y0 = ac[lag - 1], y1 = ac[lag], y2 = ac[lag + 1];
    const den = y0 - 2 * y1 + y2;
    const shift = den < 0 ? (0.5 * (y0 - y2)) / den : 0;
    return lag + Math.max(-0.5, Math.min(0.5, shift));
  });
}

const tempoPrior = (bpm) => Math.exp(-0.5 * Math.log2(bpm / 110) ** 2);

function chooseTempo(o, forcedBpm) {
  const n = o.length;
  const cache = new Map();
  const ac = (lagIn) => {
    const lag = pyRound(lagIn);
    if (lag >= n - 10) return 0;
    if (!cache.has(lag)) {
      let best = -Infinity;
      for (const k of [lag - 1, lag, lag + 1]) {
        let s = 0;
        for (let i = 0; i < n - k; i++) s += o[i] * o[i + k];
        best = Math.max(best, s / (n - k));
      }
      cache.set(lag, best);
    }
    return cache.get(lag);
  };
  const cands = new Set();
  if (forcedBpm) cands.add(pyRound2((60 * FPS) / forcedBpm));
  else {
    for (const p of tempoCandidates(o)) {
      for (const m of [0.5, 1, 2, 2 / 3, 1.5]) {
        const q = p * m, bpm = (60 * FPS) / q;
        if (bpm >= 55 && bpm <= 190) cands.add(pyRound2(q));
      }
    }
  }
  let best = null;
  for (const q of Array.from(cands).sort((a, b) => a - b)) {
    const beats = trackBeats(o, q);
    if (beats.length < 4) continue;
    let mean = 0;
    for (const b of beats) mean += Math.max(...o.slice(Math.max(0, b - 1), b + 2));
    mean /= beats.length;
    const comb = ac(2 * q) + ac(4 * q) + ac(8 * q);
    const score = mean * comb * tempoPrior((60 * FPS) / q) ** 1.5;
    if (best === null || score > best[0]) best = [score, q, beats];
  }
  if (!best) throw new Error("no beat found");
  return [best[1], best[2]];
}

// bands: Int16Array per band at 11025 Hz. Returns {beats:[[t,str,energy,flags]], info}.
export function analyseBands(bands, durationS, forcedPreset = null, forcedBpm = null) {
  const dbs = bands.map(frameEnergy);
  const onsets = dbs.map((d) => normalise(onsetEnv(d)));
  const weights = [1.3, 1.0, 0.9, 0.8, 0.7];
  const nf = Math.min(...onsets.map((v) => v.length));
  const combo = [];
  for (let i = 0; i < nf; i++) {
    let s = 0;
    for (let b = 0; b < onsets.length; b++) s += weights[b] * onsets[b][i];
    combo.push(s);
  }
  const base = movingAvg(combo, 12);
  const o = combo.map((a, i) => Math.max(0, a - base[i]));
  const oLo = onsets[0], oHi = onsets[onsets.length - 1];
  const nd = Math.min(...dbs.map((d) => d.length));
  const dbFull = [];
  for (let i = 0; i < nd; i++) {
    let s = 0;
    for (const d of dbs) s += 10 ** (d[i] / 10);
    dbFull.push(10 * Math.log10(s + 1));
  }

  const [period, beats] = chooseTempo(o, forcedBpm);
  const bpm = (60 * FPS) / period;
  const localMax = (env, i, w = 2) => {
    const sl = env.slice(Math.max(0, i - w), Math.min(env.length, i + w + 1));
    return sl.length ? Math.max(...sl) : 0;
  };
  const acc = beats.map((b) => localMax(o, b));
  const accRef = percentile(acc, 90) || 1;
  const loAt = beats.map((b) => localMax(oLo, b));
  const smooth = movingAvg(dbFull, Math.trunc(FPS));
  const eAt = beats.map((b) => smooth[Math.min(smooth.length - 1, b)]);
  const eLo = percentile(eAt, 10), eHi = percentile(eAt, 95);
  const span = Math.max(3, eHi - eLo);

  let punch = 0;
  for (let i = 1; i < dbFull.length; i++) punch += Math.abs(dbFull[i] - dbFull[i - 1]);
  punch /= Math.max(1, dbFull.length - 1);
  const auto = bpm >= 88 && punch >= 0.95 ? "energetic" : "calm";
  const preset = forcedPreset || auto;

  let keep = beats.map((_, i) => i);
  let feltBpm = bpm;
  if (preset === "calm" && bpm > 95) {
    let even = 0, odd = 0;
    for (let i = 0; i < beats.length; i++) {
      if (i % 2 === 0) even += loAt[i] + acc[i]; else odd += loAt[i] + acc[i];
    }
    const half = even >= odd ? 0 : 1;
    keep = keep.filter((i) => i % 2 === half);
    feltBpm = bpm / 2;
  }
  let kPhase = 0, kBest = -Infinity;
  for (let k = 0; k < 4; k++) {
    let s = 0;
    for (let j = k; j < keep.length; j += 4) s += loAt[keep[j]];
    if (s > kBest) { kBest = s; kPhase = k; }
  }
  const out = [];
  for (let j = 0; j < keep.length; j++) {
    const i = keep[j];
    const tMs = pyRound((beats[i] * 1000) / FPS);
    if (tMs > durationS * 1000 - 150) break;
    const strength = pyRound(9 * Math.min(1, acc[i] / accRef));
    const energy = pyRound(9 * Math.min(1, Math.max(0, (eAt[i] - eLo) / span)));
    const flags = (((j - kPhase) % 4) + 4) % 4 === 0 ? 1 : 0;
    out.push([tMs, strength, energy, flags]);
  }
  return {
    beats: out,
    info: {
      bpm: Math.round(bpm * 10) / 10,
      felt_bpm: Math.round(feltBpm * 10) / 10,
      preset,
      auto_preset: auto,
      punch: Math.round(punch * 100) / 100,
    },
  };
}

export function analyse11k(mono11k, durationS, forcedPreset = null, forcedBpm = null) {
  const n = Math.floor(durationS * SR);
  const bands = splitBands(mono11k.subarray(0, Math.min(n, mono11k.length)));
  return analyseBands(bands, durationS, forcedPreset, forcedBpm);
}

// ------------------------------------------------------------ levels
// Highpass at 110 Hz (the small speaker can't play lower), fades, -14 LUFS
// loudness and a peak limiter: what ffmpeg's "highpass,afade,loudnorm" does
// for the Music folder, so both kinds of songs play equally loud.

// ITU-R BS.1770 K-weighting (pre-filter shelf + RLB highpass) for any rate.
function kWeight(x, fs) {
  const shelf = (() => {
    const f0 = 1681.974450955533, G = 3.999843853973347, Q = 0.7071752369554196;
    const K = Math.tan((Math.PI * f0) / fs), Vh = 10 ** (G / 20), Vb = Vh ** 0.4996667741545416;
    const a0 = 1 + K / Q + K * K;
    return [(Vh + (Vb * K) / Q + K * K) / a0, (2 * (K * K - Vh)) / a0, (Vh - (Vb * K) / Q + K * K) / a0,
            (2 * (K * K - 1)) / a0, (1 - K / Q + K * K) / a0];
  })();
  const rlb = (() => {
    const f0 = 38.13547087602444, Q = 0.5003270373238773, K = Math.tan((Math.PI * f0) / fs);
    const a0 = 1 + K / Q + K * K;
    return [1 / a0, -2 / a0, 1 / a0, (2 * (K * K - 1)) / a0, (1 - K / Q + K * K) / a0];
  })();
  const run = (v, [b0, b1, b2, a1, a2]) => {
    const y = new Float64Array(v.length);
    let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
    for (let i = 0; i < v.length; i++) {
      const o = b0 * v[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
      x2 = x1; x1 = v[i]; y2 = y1; y1 = o; y[i] = o;
    }
    return y;
  };
  return run(run(x, shelf), rlb);
}

// Integrated loudness (LUFS) of mono audio, gated as in BS.1770.
export function loudness(x, fs) {
  const k = kWeight(x, fs);
  const block = Math.floor(fs * 0.4), step = Math.floor(block / 4);
  const ms = [];
  for (let s = 0; s + block <= k.length; s += step) {
    let e = 0;
    for (let i = s; i < s + block; i++) e += k[i] * k[i];
    ms.push(e / block);
  }
  const lufs = (m) => -0.691 + 10 * Math.log10(m + 1e-12);
  const abs = ms.filter((m) => lufs(m) > -70);
  if (!abs.length) return -70;
  const gate = lufs(abs.reduce((a, b) => a + b, 0) / abs.length) - 10;
  const rel = abs.filter((m) => lufs(m) > gate);
  return lufs(rel.reduce((a, b) => a + b, 0) / rel.length);
}

function limit(x, gain, fs, ceilingDb) {
  const n = x.length;
  const ceiling = 10 ** (ceilingDb / 20);
  const look = Math.floor(fs * 0.005);
  const release = Math.exp(-1 / (fs * 0.12));
  const need = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.abs(x[i] * gain);
    need[i] = a > ceiling ? ceiling / a : 1;
  }
  const minAhead = new Float32Array(n);   // smallest needed gain in the look-ahead window
  const dq = [];
  let head = 0;
  for (let i = n - 1; i >= 0; i--) {
    while (dq.length > head && need[dq[dq.length - 1]] >= need[i]) dq.pop();
    dq.push(i);
    while (dq[head] > i + look) head++;
    minAhead[i] = need[dq[head]];
  }
  const out = new Float32Array(n);
  let g = 1;
  for (let i = 0; i < n; i++) {
    const target = minAhead[i];
    g = target < g ? target : target + (g - target) * release;
    out[i] = Math.max(-1, Math.min(1, x[i] * gain * g));
  }
  return out;
}

export function prepareForPlayback(pcm, rate, seconds, trimmed) {
  const n = Math.min(pcm.length, Math.floor(seconds * rate));
  const x = biquad(pcm.subarray(0, n), "high", 110, rate);
  // fade out (and a 10 ms fade in against clicks)
  const fade = Math.floor((trimmed ? 2.5 : 0.3) * rate);
  for (let i = 0; i < n; i++) {
    let g = 1;
    if (i > n - fade) g = Math.max(0, (n - i) / fade);
    if (i < rate / 100) g *= i / (rate / 100);
    x[i] *= g;
  }
  const TARGET = -14, CEILING = -2.5;    // Opus adds up to ~2 dB of overshoot
  let gain = Math.min(30, 10 ** ((TARGET - loudness(x, rate)) / 20));
  let out = limit(x, gain, rate, CEILING);
  // The limiter takes some loudness away: make up for it once.
  const short = TARGET - loudness(out, rate);
  if (short > 0.3) {
    gain *= 10 ** (Math.min(short, 4) / 20);
    out = limit(x, gain, rate, CEILING);
  }
  return out;
}

// ------------------------------------------------------------ Ogg/Opus
let oggTable = null;
function oggCrc(bytes) {
  if (!oggTable) {
    oggTable = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let r = i << 24;
      for (let k = 0; k < 8; k++) r = r & 0x80000000 ? (r << 1) ^ 0x04c11db7 : r << 1;
      oggTable[i] = r >>> 0;
    }
  }
  let crc = 0;
  for (let i = 0; i < bytes.length; i++) crc = ((crc << 8) ^ oggTable[((crc >>> 24) ^ bytes[i]) & 0xff]) >>> 0;
  return crc >>> 0;
}

function oggPage(packets, granule, serial, seq, flags) {
  const segs = [];
  for (const p of packets) {
    let len = p.length;
    while (len >= 255) { segs.push(255); len -= 255; }
    segs.push(len);
  }
  const bodyLen = packets.reduce((s, p) => s + p.length, 0);
  const page = new Uint8Array(27 + segs.length + bodyLen);
  const dv = new DataView(page.buffer);
  page.set([0x4f, 0x67, 0x67, 0x53], 0);
  page[4] = 0;
  page[5] = flags;
  dv.setUint32(6, granule % 0x100000000, true);
  dv.setUint32(10, Math.floor(granule / 0x100000000), true);
  dv.setUint32(14, serial, true);
  dv.setUint32(18, seq, true);
  page[26] = segs.length;
  page.set(segs, 27);
  let off = 27 + segs.length;
  for (const p of packets) { page.set(p, off); off += p.length; }
  dv.setUint32(22, oggCrc(page), true);
  return page;
}

// packets: Opus packets of `frameSamples48` samples each (48 kHz units).
export function muxOggOpus(packets, { inputRate = PLAY_RATE, preSkip = 312, totalSamples48 = null,
                                      frameSamples48 = 2880, serial = 0x436f676c } = {}) {
  const head = new Uint8Array(19);
  const hv = new DataView(head.buffer);
  head.set(new TextEncoder().encode("OpusHead"), 0);
  head[8] = 1;            // version
  head[9] = 1;            // mono
  hv.setUint16(10, preSkip, true);
  hv.setUint32(12, inputRate, true);
  hv.setInt16(16, 0, true);
  head[18] = 0;
  const vendor = new TextEncoder().encode("coglet web");
  const tags = new Uint8Array(8 + 4 + vendor.length + 4);
  tags.set(new TextEncoder().encode("OpusTags"), 0);
  new DataView(tags.buffer).setUint32(8, vendor.length, true);
  tags.set(vendor, 12);
  const pages = [oggPage([head], 0, serial, 0, 0x02), oggPage([tags], 0, serial, 1, 0)];
  const end = preSkip + (totalSamples48 ?? packets.length * frameSamples48);
  let seq = 2, granule = preSkip;
  for (let i = 0; i < packets.length; i += 50) {
    const group = packets.slice(i, i + 50);
    granule += group.length * frameSamples48;
    const last = i + 50 >= packets.length;
    pages.push(oggPage(group, last ? Math.min(granule, end) : granule, serial, seq++, last ? 0x04 : 0));
  }
  const size = pages.reduce((s, p) => s + p.length, 0);
  const out = new Uint8Array(size);
  let off = 0;
  for (const p of pages) { out.set(p, off); off += p.length; }
  return out;
}

// Duration of one Opus packet in ms, from its TOC byte.
export function opusPacketMs(pkt) {
  const toc = pkt[0], config = toc >> 3;
  let frame;
  if (config < 12) frame = [10, 20, 40, 60][config & 3];
  else if (config < 16) frame = [10, 20][config & 1];
  else frame = [2.5, 5, 10, 20][config & 3];
  const code = toc & 3;
  const n = code === 0 ? 1 : code < 3 ? 2 : (pkt[1] & 0x3f);
  return frame * n;
}

// ------------------------------------------------------------ browser parts
// Decode any audio/video file the browser understands into mono PCM at `rate`.
export async function decodeFile(file, rate, maxSeconds) {
  const buf = await file.arrayBuffer();
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  let audio;
  try {
    audio = await ctx.decodeAudioData(buf);
  } finally {
    ctx.close();
  }
  const seconds = Math.min(audio.duration, maxSeconds + 1);
  const length = Math.max(1, Math.ceil(seconds * rate));
  const off = new OfflineAudioContext(1, length, rate);   // mixes down to mono
  const src = off.createBufferSource();
  src.buffer = audio;
  src.connect(off.destination);
  src.start();
  const rendered = await off.startRendering();
  return { pcm: rendered.getChannelData(0), duration: audio.duration };
}

export function encoderSupported() {
  return typeof AudioEncoder !== "undefined";
}

// Encode mono PCM (PLAY_RATE) to Ogg/Opus with 60 ms packets.
export async function encodeOpus(pcm, bitrateKbps = 32) {
  const config = {
    codec: "opus", sampleRate: PLAY_RATE, numberOfChannels: 1, bitrate: bitrateKbps * 1000,
    opus: { frameDuration: 60000, application: "audio", complexity: 10 },
  };
  const support = await AudioEncoder.isConfigSupported(config);
  if (!support.supported) throw new Error("this browser can't encode Opus; please use Chrome or Edge");
  const packets = [];
  let preSkip = 312;
  let error = null;
  const enc = new AudioEncoder({
    output: (chunk, meta) => {
      const d = new Uint8Array(chunk.byteLength);
      chunk.copyTo(d);
      packets.push(d);
      const desc = meta && meta.decoderConfig && meta.decoderConfig.description;
      if (desc && desc.byteLength >= 12) {
        const v = new Uint8Array(desc instanceof ArrayBuffer ? desc : desc.buffer, desc.byteOffset || 0, desc.byteLength);
        if (v[0] === 0x4f && v[1] === 0x70) preSkip = v[10] | (v[11] << 8);   // "OpusHead"
      }
    },
    error: (e) => { error = e; },
  });
  enc.configure(config);
  const step = PLAY_RATE;   // feed one second at a time
  for (let off = 0; off < pcm.length; off += step) {
    const part = pcm.slice(off, Math.min(pcm.length, off + step));
    const data = new AudioData({
      format: "f32", sampleRate: PLAY_RATE, numberOfFrames: part.length, numberOfChannels: 1,
      timestamp: Math.round((off / PLAY_RATE) * 1e6), data: part,
    });
    enc.encode(data);
    data.close();
  }
  await enc.flush();
  enc.close();
  if (error) throw error;
  const bad = packets.filter((p) => opusPacketMs(p) !== 60).length;
  if (bad > 1) throw new Error("the encoder made " + bad + " packets that are not 60 ms");
  return muxOggOpus(packets, {
    preSkip,
    totalSamples48: Math.round((pcm.length * 48000) / PLAY_RATE),
  });
}

// File -> song ready for the library. opts: {name, preset: "auto"|"calm"|"energetic", bpm, maxSeconds, bitrate}
export async function makeSong(file, opts, progress = () => {}) {
  const maxSeconds = opts.maxSeconds || 60;
  progress("Reading the file…");
  const a = await decodeFile(file, SR, maxSeconds);
  const total = a.duration;
  const seconds = Math.min(total, maxSeconds);
  if (seconds < 3) throw new Error("the song is too short (" + seconds.toFixed(1) + " s)");
  const trimmed = total > maxSeconds + 0.5;
  progress("Finding the beat…");
  await new Promise((r) => setTimeout(r, 0));
  const forced = opts.preset && opts.preset !== "auto" ? opts.preset : null;
  const { beats, info } = analyse11k(a.pcm, seconds, forced, opts.bpm || null);
  progress("Converting for Coglet…");
  const p = await decodeFile(file, PLAY_RATE, maxSeconds);
  const ready = prepareForPlayback(p.pcm, PLAY_RATE, seconds, trimmed);
  const ogg = await encodeOpus(ready, opts.bitrate || 32);
  return {
    name: opts.name, preset: info.preset, bpm: pyRound(info.felt_bpm), duration_ms: Math.floor(seconds * 1000),
    ogg, beats, info, trimmed,
    pcm11k: a.pcm, seconds,      // kept so the dance style can be changed without re-reading the file
  };
}

// ------------------------------------------------------------ library format
export const LIB_SECTOR = 4096;
export const LIB_MAX_SONGS = 32;
const ENTRY = 64;

export function utf8Name(name) {
  // Trim to MAX_NAME_BYTES without cutting a character in half.
  const enc = new TextEncoder();
  let out = "";
  for (const ch of name.trim()) {
    if (enc.encode(out + ch).length > MAX_NAME_BYTES) break;
    out += ch;
  }
  return out;
}

// sector: the first 4 KB of the library area. Returns {songs, total} or null when empty/invalid.
export function parseLibraryHeader(sector) {
  const dv = new DataView(sector.buffer, sector.byteOffset, sector.byteLength);
  if (sector.length < LIB_SECTOR) return null;
  if (String.fromCharCode(sector[0], sector[1], sector[2], sector[3]) !== "CGML") return null;
  if (dv.getUint16(4, true) !== 1) return null;
  const count = dv.getUint16(6, true);
  const total = dv.getUint32(8, true);
  if (count > LIB_MAX_SONGS) return null;
  if (crc32(sector.subarray(16, 16 + count * ENTRY)) !== dv.getUint32(12, true)) return null;
  const songs = [];
  const dec = new TextDecoder();
  for (let i = 0; i < count; i++) {
    const o = 16 + i * ENTRY;
    const raw = sector.subarray(o, o + 36);
    const end = raw.indexOf(0);
    songs.push({
      name: dec.decode(raw.subarray(0, end < 0 ? 35 : end)),
      preset: sector[o + 36] ? "energetic" : "calm",
      bpm: dv.getUint16(o + 38, true),
      duration_ms: dv.getUint32(o + 40, true),
      ogg_offset: dv.getUint32(o + 44, true),
      ogg_size: dv.getUint32(o + 48, true),
      beats_offset: dv.getUint32(o + 52, true),
      beat_count: dv.getUint32(o + 56, true),
      crc32: dv.getUint32(o + 60, true),
    });
  }
  return { songs, total };
}

// One song's data block: Ogg, padding to 4 bytes, beat table (8 bytes per beat).
export function songBlock(song) {
  const oggLen = song.ogg.length;
  const beatsAt = (oggLen + 3) & ~3;
  const block = new Uint8Array(beatsAt + song.beats.length * 8);
  block.set(song.ogg, 0);
  const dv = new DataView(block.buffer);
  song.beats.forEach(([t, s, e, f], i) => {
    const o = beatsAt + i * 8;
    dv.setUint32(o, t, true);
    block[o + 4] = s; block[o + 5] = e; block[o + 6] = f; block[o + 7] = 0;
  });
  const crc = crc32(block.subarray(beatsAt), crc32(block.subarray(0, oggLen)));
  return { block, beatsAt, crc };
}

// entries: [{name, preset, bpm, duration_ms, ogg_offset, ogg_size, beats_offset, beat_count, crc32}]
export function headerSector(entries, total) {
  if (entries.length > LIB_MAX_SONGS) throw new Error("at most " + LIB_MAX_SONGS + " songs");
  const s = new Uint8Array(LIB_SECTOR);
  const dv = new DataView(s.buffer);
  s.set([0x43, 0x47, 0x4d, 0x4c], 0);   // "CGML"
  dv.setUint16(4, 1, true);
  dv.setUint16(6, entries.length, true);
  dv.setUint32(8, total, true);
  const enc = new TextEncoder();
  entries.forEach((e, i) => {
    const o = 16 + i * ENTRY;
    s.set(enc.encode(utf8Name(e.name)), o);   // rest stays 0 (NUL padded)
    s[o + 36] = e.preset === "energetic" ? 1 : 0;
    dv.setUint16(o + 38, e.bpm, true);
    dv.setUint32(o + 40, e.duration_ms, true);
    dv.setUint32(o + 44, e.ogg_offset, true);
    dv.setUint32(o + 48, e.ogg_size, true);
    dv.setUint32(o + 52, e.beats_offset, true);
    dv.setUint32(o + 56, e.beat_count, true);
    dv.setUint32(o + 60, e.crc32, true);
  });
  dv.setUint32(12, crc32(s.subarray(16, 16 + entries.length * ENTRY)), true);
  return s;
}

const alignUp = (v) => Math.ceil(v / LIB_SECTOR) * LIB_SECTOR;

// Bytes a song block takes in flash (whole sectors).
export function blockFootprint(song) {
  return alignUp(((song.ogg.length + 3) & ~3) + song.beats.length * 8);
}

// Plan the flash writes for a new song list.
//   keep: entries already in flash (from parseLibraryHeader) that stay;
//   add:  new songs from makeSong().
// Returns {writes: [{offset, data}], entries, total, compact} where offsets are
// relative to the library area, the header sector is the LAST write, and
// compact=true means existing songs move (their data must be read first and
// passed as keep[i].data).
export function planLibrary(keep, add, areaSize, { compact = false } = {}) {
  if (keep.length + add.length > LIB_MAX_SONGS) throw new Error("Coglet holds at most " + LIB_MAX_SONGS + " songs");
  const writes = [];
  const entries = [];
  let end = LIB_SECTOR;
  if (compact) {
    for (const k of keep) {
      if (!k.data) throw new Error("internal: song data missing for compaction");
      const at = end;
      writes.push({ offset: at, data: k.data });
      entries.push({ ...k, ogg_offset: at, beats_offset: at + (k.beats_offset - k.ogg_offset) });
      end = alignUp(at + k.data.length);
    }
  } else {
    for (const k of keep) {
      entries.push(k);
      end = Math.max(end, alignUp(k.beats_offset + k.beat_count * 8));
    }
  }
  for (const song of add) {
    const { block, beatsAt, crc } = songBlock(song);
    const at = end;
    writes.push({ offset: at, data: block });
    entries.push({
      name: song.name, preset: song.preset, bpm: song.bpm, duration_ms: song.duration_ms,
      ogg_offset: at, ogg_size: song.ogg.length, beats_offset: at + beatsAt, beat_count: song.beats.length,
      crc32: crc,
    });
    end = alignUp(at + block.length);
  }
  if (end > areaSize) return null;   // doesn't fit (try compact, or remove songs)
  writes.push({ offset: 0, data: headerSector(entries, end) });
  return { writes, entries, total: end, compact };
}

// Room used by the songs that stay, packed.
export function usedBytes(entries) {
  return LIB_SECTOR + entries.reduce((s, e) => s + alignUp(e.beats_offset - e.ogg_offset + e.beat_count * 8), 0);
}
