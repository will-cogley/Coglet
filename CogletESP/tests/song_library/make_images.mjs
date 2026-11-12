// Builds song library images with the web page's code for test_library.cc.
import { readFileSync, writeFileSync } from "node:fs";
import { planLibrary, parseLibraryHeader, LIB_SECTOR } from "../../tools/web_flasher/coglet_songs.js";

const AREA = 512 * 1024;
const out = process.argv[2];
const ogg = (p) => new Uint8Array(readFileSync(p));
const song = (name, file, preset, n) => ({
  name, preset, bpm: 100 + n, duration_ms: 30000, ogg: ogg(file),
  beats: Array.from({ length: n }, (_, i) => [i * 500, i % 10, 5, i % 4 === 0 ? 1 : 0]),
});
const area = () => new Uint8Array(AREA).fill(0xff);
const apply = (img, plan) => { for (const w of plan.writes) img.set(w.data, w.offset); };

// 1. two songs
const img = area();
const p1 = planLibrary([], [song("Night Rain 夜雨", `${out}/a.ogg`, "calm", 40),
                             song("Drop", `${out}/b.ogg`, "energetic", 60)], AREA);
apply(img, p1);
writeFileSync(`${out}/lib_two.bin`, img);

// 2. add a third song without touching the others
const h = parseLibraryHeader(img.subarray(0, LIB_SECTOR));
const p2 = planLibrary(h.songs, [song("Third", `${out}/a.ogg`, "energetic", 10)], AREA);
if (p2.writes.some((w) => w.offset !== 0 && w.offset < h.total)) throw new Error("add overwrote old songs");
apply(img, p2);
writeFileSync(`${out}/lib_three.bin`, img);

// 3. remove the first song: header only
const h3 = parseLibraryHeader(img.subarray(0, LIB_SECTOR));
const p3 = planLibrary(h3.songs.slice(1), [], AREA);
if (p3.writes.length !== 1) throw new Error("remove should only write the header");
apply(img, p3);
writeFileSync(`${out}/lib_removed.bin`, img);

// 4. compaction: move the remaining songs to the front
const h4 = parseLibraryHeader(img.subarray(0, LIB_SECTOR));
const keep = h4.songs.map((e) => ({ ...e, data: img.slice(e.ogg_offset, e.beats_offset + e.beat_count * 8) }));
const p4 = planLibrary(keep, [], AREA, { compact: true });
const img4 = area();
apply(img4, p4);
writeFileSync(`${out}/lib_compact.bin`, img4);

// 5. damaged second song (one byte flipped in its Ogg data)
const img5 = img.slice();
const e5 = parseLibraryHeader(img5.subarray(0, LIB_SECTOR)).songs[1];
img5[e5.ogg_offset + 100] ^= 0x55;
writeFileSync(`${out}/lib_damaged.bin`, img5);

// 6. too big
const big = Array.from({ length: 40 }, (_, i) => song("s" + i, `${out}/b.ogg`, "calm", 5));
let threw = false;
try { planLibrary([], big, AREA); } catch (e) { threw = true; }
if (!threw) throw new Error("40 songs should be refused");
const huge = planLibrary([], [song("x", `${out}/b.ogg`, "calm", 5)], 8192);
if (huge !== null) throw new Error("song larger than the area should not fit");

writeFileSync(`${out}/lib_empty.bin`, area());
console.log("images written; header total after add:", p2.total, "after compact:", p4.total);
