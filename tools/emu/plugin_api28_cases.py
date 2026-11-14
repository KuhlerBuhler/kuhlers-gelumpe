"""Emulator cases of plugin API 28: korg.motion.lane, destination and value read the motion lanes the firmware recorded,
setValue writes a value, output reads what the motion engine plays, clearLane, clearPart and clearMfx clear through the
firmware's own functions, and korg.motion.enabled reads the selected part's motion switch and sets it with one TAP of the patch
tap-motion (nothing without the patch, here: EXIT held at power-on).

    python3 tools/emu/plugin_api28_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api28-motion.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import synthaddr  # noqa: E402
import tap_motion_cases as tm  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

OWNER, DEST, VALUES = 0x104, 0x11C, 0x134      # RAM offsets in the pattern object (data/script/contract.mjs PATTERN_MOTION + 4)
ENGINE, ENGINE_STRIDE = 0xC068DB0C, 0x24        # the motion engine's lane table, +0 in use, +0x10 output
MFX = 17
MOTION_LEAF = 54
INCLUDE = None


def runtime_symbols(build):
    """The glue addresses of the runtime this build's set carries (the include does not change them: no program is needed)."""
    global INCLUDE
    if INCLUDE is None:
        import plugin_edit_cases as edit
        INCLUDE = edit.compiled({"api28": "let x = 0;"})["include"]
    return script_hooks.build(INCLUDE, build=build).symbols


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    import plugin_edit_cases as edit
    edit.compiled({"api28": "let x = 0;"})


def entry(name, ok, detail):
    return {"id": f"plugin_api28:{name}", "ok": bool(ok), "detail": str(detail)}


def signed(v):
    return v - (1 << 32) if v & 0x80000000 else v


class World:
    def __init__(self, payload, flash=None, held=0):
        tm.for_build(payload)
        self.build = identify(payload).build
        self.box = tm.TBox(payload, flash, held)
        self.dev = self.box.dev
        self.sym = runtime_symbols(self.build)
        self.engine = synthaddr.tr(ENGINE) if self.build == "synth" else ENGINE

    def call(self, name, *args):
        return signed(self.dev.call(self.sym[f"script_motion_{name}_glue"], *[a & 0xFFFFFFFF for a in args]))

    def raw(self, at, n=1):
        return list(self.dev.read(self.box.pat() + at, n))

    def lanes(self):
        return self.raw(OWNER, 24)

    def in_use(self, lane):
        return self.dev.m.u32(self.engine + ENGINE_STRIDE * lane)

    def enabled(self):
        return signed(self.dev.call(self.sym["script_object_get_glue"], MOTION_LEAF, 0xFFFFFFFF))

    def set_enabled(self, value):
        self.dev.call(self.sym["script_object_set_glue"], MOTION_LEAF, 0xFFFFFFFF, value)
        self.box.run(0.4)                    # the press goes out with the panel's queue, the release one frame later


def read_cases(w):
    """A knob recorded in steps 16 to 31 of part 1 and a Master FX gesture: the calls read what the pattern object holds."""
    out = []
    w.box.record_knob()
    w.box.record_gesture()
    owners, dests = w.lanes(), w.raw(DEST, 24)
    got = [(w.call("lane", i), w.call("destination", i)) for i in range(24)]
    out.append(entry("lane_and_destination", got == list(zip(owners, dests)) and owners[:4] == [1, MFX, MFX, MFX] and dests[0] == 10
                     and not w.dev.m.asserts, f"build {w.build}: owners {owners[:5]}, destinations {dests[:5]}, calls {got[:5]}"))
    values = [w.call("value", 0, s) for s in range(64)]
    bytes0 = w.raw(VALUES, 64)
    want = {s: tm.SWEEP[s - 16] >> 1 for s in tm.WINDOW}
    ok = values == [b - 1 for b in bytes0] and all(values[s] == v for s, v in want.items())
    out.append(entry("value_reads_the_lane", ok and not w.dev.m.asserts, f"steps 16 to 31 read {values[16:32]}, sweep halved {list(want.values())}"))
    return out


def write_cases(w):
    out = []
    w.call("set_value", 0, 40, 100)
    a = (w.raw(VALUES + 40)[0], w.call("value", 0, 40))
    w.call("set_value", 0, 40, -1)
    b = (w.raw(VALUES + 40)[0], w.call("value", 0, 40))
    w.call("set_value", 0, 41, 0)
    c = (w.raw(VALUES + 41)[0], w.call("value", 0, 41))
    free = w.lanes().index(0)
    w.call("set_value", free, 3, 90)
    d = w.raw(VALUES + 0x40 * free + 3)[0]
    out.append(entry("set_value", a == (101, 100) and b == (0, -1) and c == (1, 0) and d == 0 and not w.dev.m.asserts,
                     f"100 -> {a}, -1 -> {b}, 0 -> {c}, on the free lane {free}: byte {d}"))
    return out


def output_cases(w):
    """PLAY: korg.motion.output(i) is the engine's word +0x10 of lane i, 0x24 apart; lanes 1 to 3 (the gesture) sound too."""
    def sample(box):
        return tuple(w.call("output", i) for i in range(4)) + (box.out(0),)
    seen = w.box.script({}, loops=1, sample=sample)
    window = [seen.get((0, s)) for s in tm.WINDOW if (0, s) in seen]
    first = [s[0] for s in window]
    want = [tm.SWEEP[s - 16] >> 1 for s in tm.WINDOW if (0, s) in seen]
    # the engine glides (mode Smooth) and runs up to a step ahead of the sampled step: the call must equal its word, inside the sweep
    lane0 = (len(window) > 8 and all(s[0] == signed(s[4]) for s in window) and first == sorted(first)
             and min(want) <= first[0] and first[-1] <= max(want) and len(set(first)) > 8)
    others = all(any(s[i] != -1 for s in window) for i in (1, 2, 3))
    stopped = [w.call("output", i) for i in range(4)]
    out = [entry("output_follows_the_engine", lane0 and others and not w.dev.m.asserts,
                 f"lane 0 in steps 16 to 31 {first}, want {want}; lanes 1 to 3 sound {others}; first samples {window[:2]}"),
           entry("output_silent_when_stopped", stopped == [-1] * 4, f"after STOP {stopped}")]
    return out


def clear_cases(w):
    out = []
    owners = w.lanes()
    mfx = [i for i, o in enumerate(owners) if o == MFX]
    w.call("clear_mfx")
    after = w.lanes()
    ok = all(after[i] == 0 and w.in_use(i) == 0 and not any(w.raw(VALUES + 0x40 * i, 64)) for i in mfx) and after[0] == 1
    out.append(entry("clear_mfx", ok and not w.dev.m.asserts, f"lanes before {owners[:5]}, after {after[:5]}, engine in use {[w.in_use(i) for i in range(4)]}"))
    w.call("clear_part", 1)                  # part 2 has no lane: nothing changes
    kept = w.lanes()[0] == 1 and w.in_use(0) != 0
    w.call("clear_part", 0)
    gone = w.lanes()[0] == 0 and w.in_use(0) == 0 and not any(w.raw(VALUES, 64))
    out.append(entry("clear_part", kept and gone and not w.dev.m.asserts, f"part 2 kept part 1's lane {kept}, part 1 cleared it {gone}"))
    return out


def clear_lane_cases(payload, flash):
    w = World(payload, flash)
    w.box.record_knob()
    w.box.record_gesture()
    before = w.lanes()[:4]
    w.call("clear_lane", 2)
    after = w.lanes()[:4]
    ok = after == [before[0], before[1], 0, before[3]] and w.in_use(2) == 0 and w.in_use(3) != 0 and not any(w.raw(VALUES + 0x80, 64))
    seen = w.box.script({}, loops=1, sample=lambda box: (w.call("output", 2), w.call("output", 0)))
    silent = all(v[0] == -1 for v in seen.values()) and any(v[1] != -1 for v in seen.values())
    return [entry("clear_lane", ok and silent and not w.dev.m.asserts,
                  f"lanes {before} -> {after}, lane 2 silent while playing {silent}, lane 3 in use {w.in_use(3) != 0}")]


def enabled_cases(payload, flash):
    """TAP motion on: the leaf reads the selected part's switch and one write switches it as TAP does (the patch remembers
    Trigger Hold). EXIT held at power-on (the patch off): a write changes nothing."""
    w = World(payload, flash)
    w.box.record_knob()
    w.box.set_mode(2)                        # Trigger Hold, so turning on again shows the patch's memory
    first = w.enabled()
    w.set_enabled(0)
    off = (w.enabled(), w.box.mode()[0])
    w.set_enabled(0)
    still = w.box.mode()[0]
    w.set_enabled(1)
    on = (w.enabled(), w.box.mode()[0])
    ok = first == 1 and off == (0, 0) and still == 0 and on == (1, 2)
    out = [entry("enabled_switches_like_tap", ok and not w.dev.m.asserts,
                 f"build {w.build}: read {first}, = 0 -> {off}, = 0 again -> mode {still}, = 1 -> {on}")]
    k = World(payload, flash, tm.KILL)
    k.box.record_knob()
    before = (k.enabled(), k.box.mode()[0])
    k.set_enabled(0)
    after = (k.enabled(), k.box.mode()[0])
    out.append(entry("enabled_without_the_patch_changes_nothing", before == after and before[0] == 1 and not k.dev.m.asserts,
                     f"EXIT held at power-on: {before} -> {after}"))
    return out


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    w = World(payload, flash)
    out = read_cases(w)
    out += output_cases(w)
    out += write_cases(w)
    out += clear_cases(w)
    out += clear_lane_cases(payload, flash)
    out += enabled_cases(payload, flash)
    return out


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
