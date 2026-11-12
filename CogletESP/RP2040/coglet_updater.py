# Coglet RP2040 updater (MicroPython)
#
# Lets the ESP32-S3 update the RP2040's files over the existing UART link,
# so users only ever flash the ESP. Keep this module small and stable: it is
# also the recovery path when app.py fails to start.
#
# Protocol (text lines; the ESP waits for every reply before sending more):
#   ESP -> "upd:ver?"                         RP -> "upd:ver:<bundle id>|none"
#   ESP -> "upd:begin:<bundle id>:<files>"    RP -> "upd:ready"
#   ESP -> "upd:file:<name>:<size>:<crc32>"   RP -> "upd:ok:f"
#   ESP -> "upd:d:<seq>:<base64>"             RP -> "upd:ok:<seq>"   (repeats are re-acked)
#   ESP -> "upd:end"                          RP -> "upd:ok:e" | "upd:err:<why>"
#   ESP -> "upd:commit"                       RP -> "upd:done", then reset
#   ESP -> "upd:abort"                        staged files are deleted
# Lines that don't start with "upd:" (normal state lines) are ignored.
#
# Files are written as "<name>.new" and only renamed over the real files on
# "commit". The list of files being committed is written to COMMIT_FILE first,
# so a power cut halfway through the renames is finished on the next boot.

import os
import sys
import time

try:
    import binascii
except ImportError:          # very old MicroPython
    import ubinascii as binascii

try:
    import machine
except ImportError:          # host tests
    machine = None

_CRC_TABLE = None


def _crc32(data, crc=0):
    """binascii.crc32 when the firmware has it, a table version otherwise."""
    fn = getattr(binascii, "crc32", None)
    if fn is not None:
        return fn(data, crc) & 0xFFFFFFFF
    global _CRC_TABLE
    if _CRC_TABLE is None:
        _CRC_TABLE = []
        for i in range(256):
            c = i
            for _ in range(8):
                c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
            _CRC_TABLE.append(c)
    crc ^= 0xFFFFFFFF
    for byte in data:
        crc = _CRC_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF

BUNDLE_FILE = "coglet_bundle.txt"
COMMIT_FILE = "coglet_commit.txt"
SESSION_IDLE_TIMEOUT_MS = 15000
UART_ID = 1
UART_TX_PIN = 4
UART_RX_PIN = 5
UART_BAUD = 115200


def _ticks_ms():
    return time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)


def _ticks_diff(a, b):
    return time.ticks_diff(a, b) if hasattr(time, "ticks_diff") else a - b


def _sleep_ms(ms):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(ms)
    else:
        time.sleep(ms / 1000.0)


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _valid_name(name):
    if not name or len(name) > 40 or "/" in name or name.startswith("."):
        return False
    base, dot, ext = name.rpartition(".")
    if not dot or ext not in ("py", "mpy", "json", "txt"):
        return False
    for ch in base:
        if not (ch.isalpha() or ch.isdigit() or ch in "_-"):
            return False
    return name not in (COMMIT_FILE,)


def bundle_id():
    try:
        with open(BUNDLE_FILE) as f:
            value = f.read().strip()
        return value or "none"
    except OSError:
        return "none"


def finish_pending_commit():
    """Complete a commit that was interrupted (e.g. by a power cut)."""
    if not _exists(COMMIT_FILE):
        return False
    try:
        with open(COMMIT_FILE) as f:
            lines = [l.strip() for l in f.read().split("\n") if l.strip()]
    except OSError:
        lines = []
    new_id = lines[0] if lines else ""
    for name in lines[1:]:
        if _exists(name + ".new"):
            _remove(name)
            os.rename(name + ".new", name)
    if new_id:
        with open(BUNDLE_FILE, "w") as f:
            f.write(new_id)
    _remove(COMMIT_FILE)
    print("[UPD] finished an interrupted update:", new_id)
    return True


def open_uart():
    from machine import UART, Pin
    return UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN), rxbuf=2048)


class LineReader:
    def __init__(self, uart):
        self.uart = uart
        self.buf = b""

    def readline(self, timeout_ms):
        """Next line starting with 'upd:' (others are dropped), or None."""
        start = _ticks_ms()
        while True:
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                text = line.decode("utf-8", "ignore").strip()
                if text.startswith("upd:"):
                    return text
            if _ticks_diff(_ticks_ms(), start) > timeout_ms:
                return None
            n = self.uart.any()
            if n:
                data = self.uart.read(n)
                if data:
                    self.buf += data
                    if len(self.buf) > 4096:          # garbage guard
                        self.buf = self.buf[-1024:]
            else:
                _sleep_ms(2)


def _send(uart, text):
    uart.write((text + "\n").encode())


class Session:
    """One update transfer. run() returns True when committed."""

    def __init__(self, uart, reader=None):
        self.uart = uart
        self.reader = reader or LineReader(uart)
        self.staged = []
        self.new_id = ""
        self.file = None
        self.name = ""
        self.size = 0
        self.crc = 0
        self.written = 0
        self.run_crc = 0
        self.next_seq = 0

    def _abort(self, why):
        if self.file:
            try:
                self.file.close()
            except Exception:
                pass
            self.file = None
        for name in self.staged + ([self.name] if self.name else []):
            _remove(name + ".new")
        self.staged = []
        print("[UPD] aborted:", why)

    def run(self, begin_line):
        parts = begin_line.split(":")
        if len(parts) < 4:
            _send(self.uart, "upd:err:begin")
            return False
        self.new_id = parts[2]
        print("[UPD] receiving bundle", self.new_id, "with", parts[3], "files")
        _send(self.uart, "upd:ready")
        while True:
            line = self.reader.readline(SESSION_IDLE_TIMEOUT_MS)
            if line is None:
                self._abort("timeout")
                return False
            if line.startswith("upd:d:"):
                self._chunk(line)
            elif line.startswith("upd:file:"):
                self._file(line)
            elif line == "upd:end":
                self._end()
            elif line == "upd:commit":
                return self._commit()
            elif line == "upd:abort":
                self._abort("ESP aborted")
                return False
            elif line == "upd:ver?":
                _send(self.uart, "upd:ver:" + bundle_id())
            elif line.startswith("upd:begin:"):
                self._abort("restarted")
                self.__init__(self.uart, self.reader)
                return self.run(line)

    def _file(self, line):
        parts = line.split(":")
        if self.file or len(parts) != 5 or not _valid_name(parts[2]):
            _send(self.uart, "upd:err:file")
            return
        self.name = parts[2]
        self.size = int(parts[3])
        self.crc = int(parts[4], 16)
        self.written = 0
        self.run_crc = 0
        self.next_seq = 0
        self.file = open(self.name + ".new", "wb")
        _send(self.uart, "upd:ok:f")

    def _chunk(self, line):
        try:
            _, _, seq, payload = line.split(":", 3)
            seq = int(seq)
        except ValueError:
            _send(self.uart, "upd:err:chunk")
            return
        if self.file is None:
            _send(self.uart, "upd:err:nofile")
            return
        if seq == self.next_seq - 1:                     # our ack was lost
            _send(self.uart, "upd:ok:%d" % seq)
            return
        if seq != self.next_seq:
            _send(self.uart, "upd:err:seq:%d" % self.next_seq)
            return
        try:
            data = binascii.a2b_base64(payload)
        except Exception:
            _send(self.uart, "upd:err:b64")
            return
        self.file.write(data)
        self.written += len(data)
        self.run_crc = _crc32(data, self.run_crc)
        self.next_seq += 1
        _send(self.uart, "upd:ok:%d" % seq)

    def _end(self):
        if self.file is None:
            # repeated "end" after a lost ack: the file was already accepted
            if self.name and self.name in self.staged:
                _send(self.uart, "upd:ok:e")
            else:
                _send(self.uart, "upd:err:nofile")
            return
        self.file.close()
        self.file = None
        if self.written != self.size or (self.run_crc & 0xFFFFFFFF) != self.crc:
            _remove(self.name + ".new")
            print("[UPD] bad file", self.name, self.written, self.size)
            self.name = ""
            _send(self.uart, "upd:err:crc")
            return
        self.staged.append(self.name)
        _send(self.uart, "upd:ok:e")

    def _commit(self):
        if self.file is not None:
            self._abort("commit with an open file")
            _send(self.uart, "upd:err:commit")
            return False
        with open(COMMIT_FILE, "w") as f:
            f.write(self.new_id + "\n" + "\n".join(self.staged) + "\n")
        finish_pending_commit()
        print("[UPD] updated", len(self.staged), "files ->", self.new_id)
        _send(self.uart, "upd:done")
        return True


def handle_line(line, uart, before_session=None):
    """Called by app.py for every 'upd:' line from the ESP.

    Returns True if the line was an update command. A 'begin' takes over the
    RP2040 until the transfer ends, then resets it so the new files run.
    """
    if line == "upd:ver?":
        _send(uart, "upd:ver:" + bundle_id())
        return True
    if line.startswith("upd:begin:"):
        if before_session:
            try:
                before_session()
            except Exception as exc:
                print("[UPD] before_session failed:", exc)
        try:
            session_uart = open_uart()
        except Exception:
            session_uart = uart
        ok = Session(session_uart).run(line)
        _sleep_ms(200)
        if ok and machine is not None:
            machine.reset()
        return True
    return line.startswith("upd:")


def recovery():
    """app.py failed to start: keep answering the ESP so it can repair us."""
    print("[UPD] RECOVERY MODE: waiting for the ESP to send a working app")
    uart = open_uart()
    reader = LineReader(uart)
    led = None
    try:
        from machine import Pin
        led = Pin(25, Pin.OUT)
    except Exception:
        pass
    blink = 0
    while True:
        line = reader.readline(500)
        if led is not None:
            blink ^= 1
            led.value(blink)
        if line is None:
            continue
        if line == "upd:ver?":
            # "recovery" never matches a real bundle id, so the ESP always
            # re-sends everything.
            _send(uart, "upd:ver:recovery")
        elif line.startswith("upd:begin:"):
            if Session(uart, reader).run(line) and machine is not None:
                _sleep_ms(200)
                machine.reset()
