"""Simulated RP2040 for the sync test: runs the real coglet_updater.py.

stdin/stdout stand in for the UART. Usage:
  rp_sim.py <fs dir> <mode>
modes: normal | no_updater | lose_ack | power_cut
"""
import os
import sys
import time

FS, MODE = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "RP2040"))
os.chdir(FS)
import coglet_updater as U  # noqa: E402

U.machine = None   # no real reset; we "reboot" by finishing the commit


class Uart:
    def __init__(self):
        self.fd = sys.stdin.buffer.fileno()
        os.set_blocking(self.fd, False)
        self.dropped = False
        self.renames = 0

    def any(self):
        import select
        r, _, _ = select.select([self.fd], [], [], 0)
        return 1 if r else 0

    def read(self, n):
        try:
            return os.read(self.fd, 4096)
        except BlockingIOError:
            return b""

    def write(self, data):
        if MODE == "lose_ack" and not self.dropped and data.startswith(b"upd:ok:5\n"):
            self.dropped = True          # this ack gets lost on the wire
            return
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


uart = Uart()
U.open_uart = lambda: uart

if MODE == "power_cut":
    real_rename = os.rename
    state = {"n": 0, "cut": False}

    def flaky_rename(a, b):
        state["n"] += 1
        if not state["cut"] and state["n"] == 3:
            state["cut"] = True
            raise KeyboardInterrupt("power cut")
        real_rename(a, b)
    U.os.rename = flaky_rename

reader = U.LineReader(uart)
while True:
    line = reader.readline(30000)
    if line is None or line == "upd:quit":
        break
    if MODE == "no_updater":
        continue                         # old RP2040 program: ignores upd:
    try:
        if line.startswith("upd:begin:"):
            ok = U.Session(uart, reader).run(line)
            print("SIM session ok=%s" % ok, file=sys.stderr)
        else:
            U.handle_line(line, uart)
    except KeyboardInterrupt:
        print("SIM power cut during commit; rebooting", file=sys.stderr)
        U.finish_pending_commit()        # what main.py does on the next boot
        # the ESP never got "upd:done": it reports a failure and retries later
