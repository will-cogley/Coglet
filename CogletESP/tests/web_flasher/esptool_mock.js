// Stand-in for esptool-js in the page tests: a 16 MB flash in memory.
const SECTOR = 4096;
function mem() {
  if (!window.__mem) window.__mem = new Uint8Array(16 * 1024 * 1024).fill(0xff);
  return window.__mem;
}
window.__writes = [];
export class Transport {
  constructor(port) { this.port = port; }
  async disconnect() { window.__disconnects = (window.__disconnects || 0) + 1; }
}
export class ESPLoader {
  constructor(o) { window.__loaderBaud = o.baudrate; this.t = o.terminal; }
  async main() {
    if (window.__failConnect) throw new Error("Failed to connect with the device");
    this.t.writeLine("mock: chip detected");
    return window.__chip || "ESP32-S3 (QFN56) (revision v0.2)";
  }
  async readFlashId() { return (0x18 << 16) | 0x4020; }        // 16 MB
  async readFlash(addr, size) {
    window.__reads = (window.__reads || 0) + size;
    return mem().slice(addr, addr + size);
  }
  async writeFlash(opts) {
    const m = mem();
    if (opts.eraseAll) m.fill(0xff);
    const batch = [];
    opts.fileArray.forEach((f, i) => {
      // erase the sectors the write touches, like the real chip
      const start = Math.floor(f.address / SECTOR) * SECTOR;
      const end = Math.ceil((f.address + f.data.length) / SECTOR) * SECTOR;
      m.fill(0xff, start, end);
      m.set(f.data, f.address);
      batch.push({ address: f.address, len: f.data.length, md5: opts.calculateMD5Hash(f.data) });
      opts.reportProgress(i, f.data.length / 2, f.data.length);
      opts.reportProgress(i, f.data.length, f.data.length);
    });
    window.__writes.push(batch);
    window.__flash = { eraseAll: opts.eraseAll, mode: opts.flashMode, files: batch };
  }
  async after(m) { window.__after = m; }
}
