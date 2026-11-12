// node analyse_node.mjs <f32le mono 11025 file> <seconds> [preset] [bpm]
import { readFileSync } from "node:fs";
import { analyse11k } from "../../tools/web_flasher/coglet_songs.js";
const [, , path, seconds, preset, bpm] = process.argv;
const buf = readFileSync(path);
const pcm = new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4);
const r = analyse11k(pcm, parseFloat(seconds), preset && preset !== "-" ? preset : null, bpm ? parseFloat(bpm) : null);
process.stdout.write(JSON.stringify(r));
