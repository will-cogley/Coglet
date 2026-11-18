"""Host test for RP2040 music.py (dance player) using the vision_sim mocks.
python3 test_dance.py
"""
import builtins, importlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vision_sim"))
import sim
RP = os.path.abspath(os.path.join(HERE, "..", "..", "RP2040"))

def load():
    real_time = sys.modules.get("time")
    for n in ("vision", "animation", "servoclass", "music", "dance_data", "dance_xmas", "dance_elf", "dance_snow"):
        sys.modules.pop(n, None)
    sys.modules["time"] = sim.make_time_module()
    emu = sim.GroveEmu(sim.World({}, .22, .22, 0, lambda t: 0, lambda t: 0, lambda t: True), 33.3, (2, 15, 1), True)
    sys.modules["machine"] = sim.make_machine_module(emu)
    if RP not in sys.path:
        sys.path.insert(0, RP)
    p = builtins.print; builtins.print = lambda *a, **k: None
    try:
        animation = importlib.import_module("animation")
        music = importlib.import_module("music")
        data = None
    finally:
        builtins.print = p     # RP2040 dir stays on sys.path: music imports dance data lazily
    # music.time must stay the fake clock for the whole run
    return animation, music, data, sys.modules["time"], real_time

def run(name, stop_at_ms=None, state_change_at_ms=None, loop_ms=2):
    animation, music, data, ftime, real_time = load()
    S = animation.servos
    defaults = {k: (s.max_speed, s.max_accel) for k, s in S.items()}
    logs = []
    p = builtins.print; builtins.print = lambda *a, **k: logs.append(" ".join(map(str, a)))
    errors = []
    sim.SIM.now_ms = 0.0
    try:
        now = ftime.ticks_ms()
        music.start(name, now)
        start = now
        dispatched = []
        orig = music._do_move
        def spy(move, arg, n):
            dispatched.append((ftime.ticks_diff(n, start), move)); orig(move, arg, n)
        music._do_move = spy
        owned_until = None
        last_target = {}
        moves_per_servo = {k: 0 for k in S}
        while sim.SIM.now_ms < 40000:
            sim.SIM.now_ms += loop_ms
            now = ftime.ticks_ms()
            t = ftime.ticks_diff(now, start)
            if stop_at_ms and t >= stop_at_ms and music.active():
                music.stop(now, "test stop")
            if state_change_at_ms and abs(t - state_change_at_ms) < loop_ms and music.active():
                # main.py: state change while dancing must not reset limits
                if not music.active():
                    animation.reset_servo_motion_defaults()
                animation.current_state = "listening"
            owns = music.update(now)
            if not owns and owned_until is None:
                owned_until = t
            for k, s in S.items():
                if not (s.min_angle <= s.target <= s.max_angle):
                    errors.append("{} target {} out of range at {} ms".format(k, s.target, t))
                if last_target.get(k) != s.target:
                    moves_per_servo[k] += 1; last_target[k] = s.target
                s.update(loop_ms / 1000.0)
            if owned_until is not None and t > owned_until + 50:
                break
    finally:
        builtins.print = p
        sys.modules["time"] = real_time
    # timing: every move dispatched at score time + latency - lead, within one loop
    track = music._track(name)
    if any("unknown move" in l for l in logs):
        errors.append("unknown move: " + next(l for l in logs if "unknown move" in l))
    mine = music._module(name)
    others = [m for m in ("dance_data", "dance_xmas", "dance_elf", "dance_snow") if m != mine]
    other = next((m for m in others if m in sys.modules), others[0])
    if other in sys.modules:
        errors.append("{} was loaded for {} (wastes RAM)".format(other, name))
    final = {k: S[k].target for k in S}
    off = music.AUDIO_LATENCY_MS - music.SERVO_LEAD_MS
    n_expected = len(track["moves"]) if not stop_at_ms else sum(1 for m in track["moves"] if m[0] + off < stop_at_ms)
    if len(dispatched) != n_expected:
        errors.append("dispatched {} moves, expected {}".format(len(dispatched), n_expected))
    worst = max((abs(d[0] - (m[0] + off)) for d, m in zip(dispatched, track["moves"])), default=0)
    if worst > loop_ms + 1:
        errors.append("timing error {} ms".format(worst))
    restored = all((S[k].max_speed, S[k].max_accel) == defaults[k] for k in S)
    if not restored:
        errors.append("motion limits not restored")
    if not animation.new_state_flag:
        errors.append("new_state_flag not set at hand-back")
    if music.active():
        errors.append("still active")
    return dict(owned_ms=owned_until, worst_ms=worst, moves=len(dispatched), final=final,
                servo_changes=moves_per_servo, errors=errors,
                log=[l for l in logs if "[DANCE]" in l])

if __name__ == "__main__":
    fails = 0
    for name in ("mecha", "evil", "cat", "lyrical", "classic", "grand", "workshop", "mischief", "party",
                 "lullaby", "stomp", "blizzard"):
        r = run(name)
        print("{:<6} handback@{} ms  moves={}  worst_sync={} ms  {}".format(
            name, r["owned_ms"], r["moves"], r["worst_ms"], "OK" if not r["errors"] else r["errors"]))
        print("       servo target changes:", r["servo_changes"])
        fails += bool(r["errors"])
    r = run("mecha", stop_at_ms=5000)
    print("stop@5s  handback@{} ms  {}".format(r["owned_ms"], "OK" if not r["errors"] else r["errors"])); fails += bool(r["errors"])
    r = run("cat", state_change_at_ms=8000)
    print("state change mid-dance  {}".format("OK" if not r["errors"] else r["errors"])); fails += bool(r["errors"])
    animation, music, *_ = load()
    p = builtins.print; builtins.print = lambda *a, **k: None
    ok = music.start("disco", 0) is False and not music.active()
    builtins.print = p
    print("unknown style rejected", "OK" if ok else "FAIL"); fails += not ok
    print("FAILURES:", fails)
    if fails:
        sys.exit(1)


# ------------------------------------------------------------------ groove mode
def run_groove(preset, beats, end_with_message=True, loop_ms=2):
    """beats: [(t_ms, strength, energy, bar)] as produced by build_music.py."""
    animation, music, data, ftime, real_time = load()
    import servoclass
    S = animation.servos
    defaults = {k: (s.max_speed, s.max_accel) for k, s in S.items()}
    writes = {k: 0 for k in S}
    chan = {s.channel: k for k, s in S.items()}
    orig_write = servoclass._pca.write_us
    def spy(channel, us):
        writes[chan[channel]] += 1
        return orig_write(channel, us)
    servoclass._pca.write_us = spy
    errors = []
    p = builtins.print; builtins.print = lambda *a, **k: None
    sim.SIM.now_ms = 0.0
    try:
        start = ftime.ticks_ms()
        music.start_groove(preset, 100, start)
        released = [k for k, s in S.items() if s.released]
        writes_at_start = dict(writes)
        idx = 0
        last_t = beats[-1][0] if beats else 0
        ended_at = None
        while sim.SIM.now_ms < last_t + 10000:
            sim.SIM.now_ms += loop_ms
            now = ftime.ticks_ms()
            t = ftime.ticks_diff(now, start)
            while idx < len(beats) and beats[idx][0] <= t:
                b = beats[idx]
                music.groove_beat("{}{}{}".format(b[1], b[2], b[3]), now)
                idx += 1
            if end_with_message and idx >= len(beats) and t >= last_t + 500 and music.active() \
                    and music._dance["end_at"] is None:
                music.groove_end(now)
            during = dict(writes)          # PCA writes while the groove still owns the servos
            owns = music.update(now)
            for k, s in S.items():
                if not (s.min_angle <= s.target <= s.max_angle):
                    errors.append("{} target out of range".format(k))
                s.update(loop_ms / 1000.0)
            if owns:
                during = dict(writes)
            if not owns:
                ended_at = t
                break
        released_writes = {k: during[k] - writes_at_start[k] for k in released}
    finally:
        builtins.print = p
        sys.modules["time"] = real_time
        servoclass._pca.write_us = orig_write
    if ended_at is None:
        errors.append("never handed back")
    if any(released_writes.values()):
        errors.append("released servos were driven: {}".format(released_writes))
    if any(s.released for s in S.values()):
        errors.append("servos still released after the song")
    if not all((S[k].max_speed, S[k].max_accel) == defaults[k] for k in S):
        errors.append("motion limits not restored")
    return dict(released=released, ended_at=ended_at, errors=errors)


def groove_tests():
    fails = 0
    # 2 bars per second-ish synthetic beat maps
    energetic = [(500 + i * 469, (9 if i % 4 == 0 else 5), min(9, i // 8), int(i % 4 == 0)) for i in range(60)]
    calm = [(800 + i * 882, 6, min(9, i // 4), int(i % 4 == 0)) for i in range(30)]
    r = run_groove("energetic", energetic)
    print("groove energetic  handback@{} ms  released={}  {}".format(
        r["ended_at"], r["released"] or "-", "OK" if not r["errors"] else r["errors"]))
    fails += bool(r["errors"])
    r = run_groove("calm", calm)
    ok = r["released"] == sorted(["LID", "EYL", "EYR"]) or set(r["released"]) == {"LID", "EYL", "EYR"}
    print("groove calm       handback@{} ms  released={}  {}".format(
        r["ended_at"], ",".join(r["released"]), "OK" if (not r["errors"] and ok) else (r["errors"], ok)))
    fails += bool(r["errors"]) or not ok
    r = run_groove("calm", calm[:5], end_with_message=False)
    expect = calm[4][0] + 4000 + 1200
    ok = r["ended_at"] is not None and abs(r["ended_at"] - expect) < 100
    print("groove silence    handback@{} ms (expect ~{})  {}".format(
        r["ended_at"], expect, "OK" if (not r["errors"] and ok) else r["errors"]))
    fails += bool(r["errors"]) or not ok
    return fails


if __name__ == "__main__":
    f = groove_tests()
    print("GROOVE FAILURES:", f)
    sys.exit(1 if f else 0)
