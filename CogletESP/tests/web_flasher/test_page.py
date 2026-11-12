"""End-to-end test of the web flasher page against a simulated Coglet.

The simulation: two USB serial ports (ESP32-S3 bridge and RP2040), a 16 MB
flash in memory behind a stand-in for esptool-js, Coglet's boot log after a
reset, and a MicroPython raw REPL for the servo board setup. Song images the
page writes are parsed by the firmware's own C++ code (dump_library).

usage: python test_page.py <work dir> <dump_library binary> <song files...>
"""
import builtins
import contextlib
import functools
import hashlib
import http.server
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import types

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
WORK, DUMP = sys.argv[1], sys.argv[2]
SONG_FILES = sys.argv[3:]
SONG_AREA_KB = 400          # small, so the page has to pack songs at some point

fails = 0


def check(cond, label, detail=""):
    global fails
    print(("  ok    " if cond else "  FAIL  ") + label + (("  [" + detail + "]") if detail else ""))
    fails += not cond


# ---------------------------------------------------------------- site
def build_site():
    site = os.path.join(WORK, "site")
    shutil.rmtree(site, ignore_errors=True)
    build = os.path.join(WORK, "build")
    os.makedirs(os.path.join(build, "bootloader"), exist_ok=True)
    os.makedirs(os.path.join(build, "partition_table"), exist_ok=True)
    os.makedirs(os.path.join(build, "config"), exist_ok=True)
    rows = [("nvs", 1, 2, 0x9000, 0x4000), ("otadata", 1, 0, 0xd000, 0x2000), ("phy_init", 1, 1, 0xf000, 0x1000),
            ("ota_0", 0, 0x10, 0x20000, 0x3f0000), ("ota_1", 0, 0x11, 0x410000, 0x3f0000),
            ("assets", 1, 0x82, 0x800000, 0x800000)]
    pt = b"".join(struct.pack("<HBBII16sI", 0x50aa, t, st, o, sz, n.encode(), 0) for n, t, st, o, sz in rows)
    pt += b"\xff" * (0xc00 - len(pt))
    files = {"bootloader/bootloader.bin": 20000, "partition_table/partition-table.bin": None,
             "ota_data_initial.bin": 8192, "xiaozhi.bin": 300000, "generated_assets.bin": 200000}
    for rel, size in files.items():
        with open(os.path.join(build, rel), "wb") as f:
            f.write(pt if size is None else os.urandom(size))
    json.dump({"flash_settings": {"flash_mode": "dio", "flash_size": "16MB", "flash_freq": "80m"},
               "flash_files": {"0x0": "bootloader/bootloader.bin", "0x8000": "partition_table/partition-table.bin",
                               "0xd000": "ota_data_initial.bin", "0x20000": "xiaozhi.bin",
                               "0x800000": "generated_assets.bin"},
               "extra_esptool_args": {"chip": "esp32s3"}}, open(os.path.join(build, "flasher_args.json"), "w"))
    json.dump({"COGLET_DANCE": True, "COGLET_MUSIC": True, "COGLET_MUSIC_LIBRARY_KB": SONG_AREA_KB},
              open(os.path.join(build, "config", "sdkconfig.json"), "w"))
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/web_flasher/make_manifest.py"), "--build", build,
                    "--site", site, "--version", "v9.9.9", "--commit", "abc1234", "--repo", "example/Coglet"],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/rp2040_bundle/build_bundle.py"), "--src",
                    os.path.join(ROOT, "RP2040"), "--site", os.path.join(site, "rp2040")],
                   check=True, stdout=subprocess.DEVNULL)
    for name in ("index.html", "coglet_songs.js"):
        shutil.copy(os.path.join(ROOT, "tools/web_flasher", name), site)
    return site


SITE = build_site()
MANIFEST = json.load(open(os.path.join(SITE, "firmware/manifest.json")))
AREA = MANIFEST["songs"]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=SITE))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


# ---------------------------------------------------------------- MicroPython REPL
class RawReplEmu:
    def __init__(self, fs):
        self.fs, self.mode, self.code, self.reboots, self.ns = fs, "running", b"", 0, {}

    def feed(self, data):
        out = b""
        for byte in data:
            ch = bytes([byte])
            if self.mode == "running":
                if ch == b"\x03":
                    self.mode = "normal"
                    out += b"KeyboardInterrupt: \r\nMicroPython v1.24.1\r\n>>> "
            elif self.mode == "normal":
                if ch == b"\x01":
                    self.mode, self.code = "raw", b""
                    out += b"raw REPL; CTRL-B to exit\r\n>"
                elif ch == b"\x04":
                    self.reboots += 1
                    self.mode = "running"
            elif self.mode == "raw":
                if ch == b"\x04":
                    out += b"OK" + self._run(self.code.decode()) + b">"
                    self.code = b""
                elif ch == b"\x02":
                    self.mode = "normal"
                elif ch not in (b"\x01", b"\x03"):
                    self.code += ch
        return list(out)

    def _run(self, code):
        fake_sys = types.SimpleNamespace(platform="rp2")
        real_import = builtins.__import__
        g = self.ns
        g["__builtins__"] = dict(builtins.__dict__,
                                 __import__=lambda n, *a, **k: fake_sys if n == "sys" else real_import(n, *a, **k))
        o, e = io.StringIO(), ""
        cwd = os.getcwd()
        try:
            os.chdir(self.fs)
            with contextlib.redirect_stdout(o):
                exec(code, g)
        except Exception as exc:
            e = "Traceback:\r\n%s: %s\r\n" % (type(exc).__name__, exc)
        finally:
            os.chdir(cwd)
        return o.getvalue().replace("\n", "\r\n").encode() + b"\x04" + e.encode() + b"\x04"


FAKE = """
(() => {
  const enc = new TextEncoder();
  function makePort(kind, vid, pid) {
    const p = {
      kind, opens: 0, ctl: null, stream: null, lastRts: false,
      getInfo() { return { usbVendorId: vid, usbProductId: pid }; },
      async open() {
        this.opens++;
        this.stream = new ReadableStream({ start: (c) => { this.ctl = c; }, cancel: () => { this.ctl = null; } });
      },
      async close() { this.ctl = null; },
      get readable() { return this.stream; },
      get writable() {
        return new WritableStream({ write: async (chunk) => {
          if (kind !== 'rp') return;
          const back = await window.__toBoard(Array.from(chunk));
          if (back.length && this.ctl) this.ctl.enqueue(new Uint8Array(back));
        }});
      },
      async setSignals(s) {
        window.__signals.push({ kind, ...s });
        // RTS high -> low = EN pulse: Coglet reboots and prints its boot log
        if (kind === 'esp' && this.lastRts && !s.requestToSend) {
          const lines = (window.__bootLines || []).slice();
          (async () => {
            for (const l of lines) {
              await new Promise((r) => setTimeout(r, 40));
              if (this.ctl) this.ctl.enqueue(enc.encode(l + "\\r\\n"));
            }
          })();
        }
        this.lastRts = !!s.requestToSend;
      },
    };
    return p;
  }
  window.__signals = [];
  window.__requests = [];
  const esp = makePort('esp', 0x1a86, 0x55d4);
  const rp = makePort('rp', 0x2e8a, 0x0005);
  window.__ports = { esp, rp };
  // Chrome remembers granted ports across reloads.
  const granted = new Set(JSON.parse(sessionStorage.getItem('granted') || '[]').map((k) => window.__ports[k]));
  const listeners = {};
  Object.defineProperty(Navigator.prototype, 'serial', { get() { return {
    requestPort: async (opts) => {
      window.__requests.push(opts);
      const wantsRp = opts && opts.filters && opts.filters.some((f) => f.usbVendorId === 0x2e8a);
      const p = window.__pick ? window.__ports[window.__pick] : (wantsRp ? rp : esp);
      granted.add(p);
      sessionStorage.setItem('granted', JSON.stringify(Array.from(granted).map((x) => x.kind)));
      return p;
    },
    getPorts: async () => Array.from(granted),
    addEventListener: (t, f) => { listeners[t] = f; },
  }; } });
  window.confirm = () => true;
})();
"""

BOOT_NEEDS_RP = ["I (35) boot: ESP-IDF v5.5.3", "I (5120) CogletMusic: song library: empty (add songs from the web flasher)",
                 "W (6200) CogletRp2040: RP2040 did not answer: it needs the one-time setup from the web flasher"]
BOOT_RP_OK = ["I (35) boot: ESP-IDF v5.5.3",
              "I (6100) CogletRp2040: RP2040 bundle none -> 1a2b3c, sending 8 files",
              "I (36100) CogletRp2040: RP2040 updated (bundle 1a2b3c, 30 s)"]


def area_image(page):
    data = page.evaluate("Array.from(window.__mem.subarray(%d, %d))" % (AREA["offset"], AREA["offset"] + AREA["size"]))
    path = os.path.join(WORK, "area.bin")
    with open(path, "wb") as f:
        f.write(bytes(data))
    return json.loads(subprocess.run([DUMP, path], stdout=subprocess.PIPE, check=True).stdout)


def wait_status(page, el, kinds=("ok", "err", "warn"), timeout=60000, contains=None):
    cond = "(() => { const e = document.getElementById('%s'); return [%s].some(k => e.classList.contains(k))%s; })()" % (
        el, ",".join("'%s'" % k for k in kinds),
        (" && e.textContent.includes(%s)" % json.dumps(contains)) if contains else "")
    page.wait_for_function(cond, timeout=timeout)
    return page.inner_text("#" + el)


def song_files(names):
    d = tempfile.mkdtemp(dir=WORK)
    out = []
    for src, name in names:
        dst = os.path.join(d, name)
        shutil.copy(src, dst)
        out.append(dst)
    return out


def new_page(browser, scheme="light", width=1100):
    ctx = browser.new_context(viewport={"width": width, "height": 1300}, color_scheme=scheme)
    page = ctx.new_page()
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.route("https://cdn.jsdelivr.net/**", lambda r: r.fulfill(path=os.path.join(HERE, "esptool_mock.js"),
                                                                  content_type="text/javascript"))
    page.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=os.path.join(HERE, "md5.js"),
                                                                      content_type="text/javascript"))
    page.add_init_script(FAKE)
    return ctx, page


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ------------------------------------------------------------ look + accessibility
    print("page")
    for scheme in ("light", "dark"):
        ctx, page = new_page(browser, scheme)
        page.expose_function("__toBoard", lambda arr: [])
        page.goto("http://127.0.0.1:%d/" % PORT)
        page.wait_for_function("document.getElementById('version').textContent.includes('Version')")
        page.screenshot(path=os.path.join(WORK, "page_%s.png" % scheme), full_page=True)
        if scheme == "light":
            names = page.evaluate("""() => {
              const bad = [];
              const nameOf = (el) => {
                if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
                if (el.getAttribute('aria-labelledby')) return el.getAttribute('aria-labelledby').split(' ')
                    .map((id) => (document.getElementById(id) || {}).textContent || '').join(' ');
                if (el.labels && el.labels.length) return el.labels[0].textContent;
                return el.textContent;
              };
              for (const el of document.querySelectorAll('button, input, select, progress, svg[role=img], pre'))
                if (!(nameOf(el) || '').trim()) bad.push(el.outerHTML.slice(0, 80));
              // same check with every hidden part shown
              document.querySelectorAll('.hidden').forEach((e) => e.classList.remove('hidden'));
              for (const el of document.querySelectorAll('button, input, select, progress'))
                if (!(nameOf(el) || '').trim() && !bad.includes(el.outerHTML.slice(0, 80))) bad.push(el.outerHTML.slice(0, 80));
              const hs = Array.from(document.querySelectorAll('h1,h2,h3')).map((h) => +h.tagName[1]);
              const jumps = hs.some((h, i) => i && h > hs[i - 1] + 1);
              return { bad, jumps, lang: document.documentElement.lang, h1: hs.filter((h) => h === 1).length };
            }""")
            check(not names["bad"], "every control has an accessible name", "; ".join(names["bad"]))
            check(not names["jumps"] and names["h1"] == 1 and names["lang"] == "en", "headings in order, one h1, lang set")
            page.keyboard.press("Tab")
            check(page.evaluate("document.activeElement.className") == "skip", "first Tab reaches the skip link")
            page.keyboard.press("Enter")
            page.keyboard.press("Tab")
            check(page.evaluate("document.activeElement.id") == "flash", "skip link leads to Connect & Update")
            check(page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none",
                  "keyboard focus is visible")
            link = page.evaluate("document.querySelector('#version a') && document.querySelector('#version a').href")
            check(link == "https://github.com/example/Coglet/releases/tag/v9.9.9", "What's new links to the release", str(link))
        check(not page.errors, "no script errors (%s)" % scheme, "; ".join(page.errors))
        ctx.close()
    ctx = browser.new_context(viewport={"width": 390, "height": 900}, color_scheme="dark")
    page = ctx.new_page()
    page.add_init_script("Object.defineProperty(Navigator.prototype, 'serial', { get() { return undefined; } });")
    page.goto("http://127.0.0.1:%d/" % PORT)
    page.wait_for_timeout(500)
    check(page.evaluate("document.documentElement.scrollWidth") <= 390, "no sideways scrolling on a phone")
    check(not page.evaluate("document.getElementById('unsupported').hidden"), "phone/no Web Serial: warning shown")
    page.screenshot(path=os.path.join(WORK, "page_phone.png"), full_page=True)
    ctx.close()

    # ------------------------------------------------------------ update -> servo board needed
    print("update")
    ctx, page = new_page(browser)
    fs = tempfile.mkdtemp(dir=WORK)
    open(os.path.join(fs, "main.py"), "w").write("# old program\n")
    emu = RawReplEmu(fs)
    page.expose_function("__toBoard", lambda arr: emu.feed(bytes(arr)))
    page.goto("http://127.0.0.1:%d/" % PORT)
    page.wait_for_function("document.getElementById('version').textContent.includes('Version')")
    page.evaluate("window.__bootLines = %s" % json.dumps(BOOT_NEEDS_RP))
    page.click("#flash")
    st = wait_status(page, "status", ("warn", "err"), contains="One more step")
    fl = page.evaluate("window.__flash")
    got = [(f["address"], f["len"], f["md5"]) for f in fl["files"]]
    check(got == [(x["offset"], x["size"], x["md5"]) for x in MANIFEST["parts"]] and not fl["eraseAll"],
          "all parts written at their offsets, nothing erased")
    req = page.evaluate("window.__requests")
    check(len(req) == 1 and req[0].get("filters") and all(f["usbVendorId"] != 0x2e8a for f in req[0]["filters"]),
          "port list filtered to USB-serial chips")
    check("attention" in page.get_attribute("#rpcard", "class") and page.is_visible("#rpneeded"),
          "servo board card highlighted after 'did not answer'")
    check(page.evaluate("document.activeElement.id") == "rpcard", "focus moved to the servo board step")
    check(page.evaluate("Array.from(window.__mem.subarray(%d, %d)).every(b => b === 255)" %
                        (AREA["offset"], AREA["offset"] + 4096)), "update did not touch the song area")
    print("    status:", st)
    page.screenshot(path=os.path.join(WORK, "page_rp_needed.png"), full_page=True)

    # ------------------------------------------------------------ servo board setup + check
    page.click("#rpsetup")
    st = wait_status(page, "rpstatus", timeout=120000)
    man = json.load(open(os.path.join(SITE, "rp2040", "manifest.json")))
    ok_files = all(hashlib.md5(open(os.path.join(fs, f["name"]), "rb").read()).hexdigest() == f["md5"]
                   for f in man["files"])
    check("ok" in page.get_attribute("#rpstatus", "class") and ok_files and emu.reboots == 1 and
          open(os.path.join(fs, "coglet_bundle.txt")).read() == man["bundle_id"],
          "servo board set up (files, bundle id, reboot)")
    check(page.evaluate("window.__requests").pop().get("filters")[0]["usbVendorId"] == 0x2e8a,
          "servo board port list shows only the RP2040")
    check(page.evaluate("document.activeElement.id") == "rpcheck", "focus moved to Check Coglet")
    page.evaluate("window.__bootLines = %s" % json.dumps(BOOT_RP_OK))
    n_req = len(page.evaluate("window.__requests"))
    page.click("#rpcheck")
    st = wait_status(page, "rpstatus", ("ok",), contains="All set", timeout=15000)
    check("All set" in st and len(page.evaluate("window.__requests")) == n_req,
          "Check Coglet confirms the servo board, without asking for the port again")
    check("attention" not in page.get_attribute("#rpcard", "class"), "highlight removed once all set")

    # ------------------------------------------------------------ songs
    print("songs")
    page.evaluate("window.__bootLines = ['I (5120) CogletMusic: song library: 3 songs at assets+0x79c000']")
    files = song_files([(SONG_FILES[0], "Mecha Beat.mp3"), (SONG_FILES[1], "Night Rain.calm.mp3"),
                        (SONG_FILES[2], "Evil_Waltz.mp3")])
    page.set_input_files("#songfiles", files)
    page.wait_for_function("document.querySelectorAll('#newsongs li').length === 3 && "
                           "!document.getElementById('songsave').disabled", timeout=60000)
    names = page.eval_on_selector_all("#newsongs input[type=text]", "els => els.map(e => e.value)")
    presets = page.eval_on_selector_all("#newsongs select", "els => els.map(e => e.value)")
    check(names == ["Mecha Beat", "Night Rain", "Evil Waltz"] and presets[1] == "calm",
          "names and .calm tag taken from the file names", str(names) + str(presets))
    # change the first song's style to calm before saving
    page.select_option("#newsongs li:nth-child(1) select", "calm")
    meta0 = page.inner_text("#newsongs li:nth-child(1) .meta")
    check(meta0.startswith("Calm"), "changing the dance style re-analyses the song", meta0)
    page.click("#songsave")
    st = wait_status(page, "songstatus", ("ok", "err", "warn"), contains="found", timeout=30000)
    lib = area_image(page)
    check(lib["ok"] and [s["name"] for s in lib["songs"]] == ["Mecha Beat", "Night Rain", "Evil Waltz"] and
          lib["songs"][0]["preset"] == "calm" and lib["skipped"] == 0,
          "firmware parser reads the 3 saved songs", json.dumps(lib)[:200])
    writes = page.evaluate("window.__writes").pop()
    check(writes[-1]["address"] == AREA["offset"] and writes[-1]["len"] == 4096,
          "song list written last")
    check(all(AREA["offset"] <= w["address"] and w["address"] + w["len"] <= AREA["offset"] + AREA["size"]
              for w in writes), "writes stay inside the song area")
    check("found 3 songs" in st, "page confirms what Coglet loaded", st)

    # read back, remove one, add one that only fits after packing
    area_b64 = page.evaluate("""() => { const a = window.__mem.subarray(%d, %d); let s = '';
        for (let i = 0; i < a.length; i += 8192) s += String.fromCharCode.apply(null, a.subarray(i, i + 8192));
        return btoa(s); }""" % (AREA["offset"], AREA["offset"] + AREA["size"]))
    page.reload()        # the flash keeps its content: put it back after the reload
    page.wait_for_function("document.getElementById('version').textContent.includes('Version')")
    page.evaluate("""(b) => { const s = atob(b); const m = new Uint8Array(16 * 1024 * 1024).fill(255);
        for (let i = 0; i < s.length; i++) m[%d + i] = s.charCodeAt(i); window.__mem = m; }""" % AREA["offset"], area_b64)
    page.click("#songread")
    wait_status(page, "songstatus", ("ok",), contains="Coglet has 3 songs")
    check(page.evaluate("window.__requests.length") == 0, "remembered port reused after reload (no prompt)")
    page.click("#devsongs li:nth-child(1) button")
    files = song_files([(SONG_FILES[3], "Cat Pop.mp3")])
    page.set_input_files("#songfiles", files)
    page.wait_for_function("!document.getElementById('songsave').disabled", timeout=60000)
    reads_before = page.evaluate("window.__reads || 0")
    page.evaluate("window.__bootLines = ['I (5120) CogletMusic: song library: 3 songs at assets+0x79c000']")
    page.click("#songsave")
    st = wait_status(page, "songstatus", ("ok", "err", "warn"), contains="found", timeout=30000)
    lib = area_image(page)
    check(lib["ok"] and [s["name"] for s in lib["songs"]] == ["Night Rain", "Evil Waltz", "Cat Pop"] and lib["skipped"] == 0,
          "removed one, added one; songs packed to make room", json.dumps([s["name"] for s in lib["songs"]]))
    check(page.evaluate("window.__reads") - reads_before > 100000, "packing read the songs that stay")

    # remove everything: only the song list is rewritten
    page.click("#devsongs li:nth-child(1) button")
    page.click("#devsongs li:nth-child(2) button")
    page.click("#devsongs li:nth-child(3) button")
    page.evaluate("window.__bootLines = []")
    page.click("#songsave")
    wait_status(page, "songstatus", ("ok", "warn"), contains="Saved", timeout=40000)
    writes = page.evaluate("window.__writes").pop()
    lib = area_image(page)
    check(len(writes) == 1 and lib["ok"] and not lib["songs"], "removing songs rewrites only the song list")

    # unreadable file
    bad = os.path.join(WORK, "notes.mp3")
    open(bad, "wb").write(b"this is not audio" * 100)
    page.set_input_files("#songfiles", [bad])
    page.wait_for_function("document.querySelector('#newsongs li .meta').textContent.includes(\"Can't use\")",
                           timeout=20000)
    check(page.is_disabled("#songsave"), "a broken file can't be saved")
    check(not page.errors, "no script errors", "; ".join(page.errors))
    page.screenshot(path=os.path.join(WORK, "page_songs.png"), full_page=True)
    ctx.close()

    # ------------------------------------------------------------ connection problems
    print("errors")
    ctx, page = new_page(browser)
    page.expose_function("__toBoard", lambda arr: [])
    page.goto("http://127.0.0.1:%d/" % PORT)
    page.wait_for_function("document.getElementById('version').textContent.includes('Version')")
    page.evaluate("window.__chip = 'ESP32-C3'")
    page.click("#flash")
    st = wait_status(page, "status", ("err",))
    check(st.startswith("Error:") and "ESP32-S3" in st, "wrong chip refused, message starts with 'Error:'", st)
    n_req = len(page.evaluate("window.__requests"))
    page.evaluate("window.__chip = null")
    page.click("#flash")
    wait_status(page, "status", ("ok",), contains="Done")
    check(len(page.evaluate("window.__requests")) == n_req + 1, "after a wrong port, the next try asks for the port again")
    page.evaluate("window.__chip = 'ESP32-C3'")
    page.wait_for_timeout(100)
    ann = page.evaluate("document.getElementById('announce').textContent")
    check("Error:" in ann, "errors are announced to screen readers", ann)
    page.evaluate("window.__chip = null; window.__failConnect = true")
    page.click("summary >> text=Advanced options")
    page.check("#allports")
    page.click("#flash")
    st = wait_status(page, "status", ("err",))
    check("Failed to connect" in st and "switch on ESP" in st, "connection failure explains what to check", st)
    check(page.evaluate("window.__requests").pop() == {}, "'Show all ports' lists every port")
    ctx.close()
    browser.close()

srv.shutdown()
print("FAILURES:", fails)
sys.exit(1 if fails else 0)
