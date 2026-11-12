// Runs makeSong() in headless Chromium on a real file and writes the Ogg +
// beats for checking. node browser_encode.mjs <audio file> <out dir>
const pw = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const chromium = pw.chromium || pw.default.chromium;
import { createServer } from "node:http";
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";

const [, , audio, outDir] = process.argv;
const root = join(dirname(fileURLToPath(import.meta.url)), "../../tools/web_flasher");
const server = createServer((req, res) => {
  if (req.url === "/") { res.setHeader("content-type", "text/html"); res.end("<!doctype html><title>t</title>"); return; }
  if (req.url === "/song") { res.end(readFileSync(audio)); return; }
  try {
    const data = readFileSync(join(root, req.url.slice(1)));
    res.setHeader("content-type", req.url.endsWith(".js") ? "text/javascript" : "application/octet-stream");
    res.end(data);
  } catch { res.statusCode = 404; res.end(); }
}).listen(0);
const port = server.address().port;
const browser = await chromium.launch();
const page = await browser.newPage();
page.on("console", (m) => console.log("[page]", m.text()));
await page.goto(`http://localhost:${port}/`);
const result = await page.evaluate(async () => {
  const m = await import("/coglet_songs.js");
  const blob = await (await fetch("/song")).blob();
  const file = new File([blob], "song");
  const t0 = performance.now();
  const s = await m.makeSong(file, { name: "Test", preset: "auto" }, (p) => console.log(p));
  return { ms: performance.now() - t0, ogg: Array.from(s.ogg), beats: s.beats, info: s.info,
           bpm: s.bpm, preset: s.preset, duration_ms: s.duration_ms, trimmed: s.trimmed };
});
console.log(JSON.stringify({ file: basename(audio), seconds: (result.ms / 1000).toFixed(1), bpm: result.bpm,
  preset: result.preset, beats: result.beats.length, oggKB: (result.ogg.length / 1024).toFixed(0),
  duration_ms: result.duration_ms, trimmed: result.trimmed }));
writeFileSync(join(outDir, "web.ogg"), Buffer.from(result.ogg));
writeFileSync(join(outDir, "web.json"), JSON.stringify({ beats: result.beats, info: result.info }));
await browser.close();
server.close();
