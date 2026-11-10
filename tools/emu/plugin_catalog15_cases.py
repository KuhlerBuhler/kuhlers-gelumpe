"""Emulator cases of the catalog plugins on plugin API 15, as the catalog ships them: Gate Hold fixes the note in Gate Arp
mode and lets X pick the pattern's Gate Arp rhythm, Momentary Mute leaves the firmware in PART MUTE mode only
while PART MUTE is held, and Step Copy copies the steps of one bar into another from its pages in the BLECH menu.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_catalog15_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1  # noqa: E402
from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import node_json  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import remote_cases  # noqa: E402
from plugin_api15_cases import SCALE_MODE, TOUCH_KEY  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

PRESETS = node_json.run(
    "import {PRESETS} from './data/script/presets.mjs';"
    "import {PATTERN_FIELDS} from './data/script/contract.mjs';"
    "const s = id => PRESETS.find(p => p.id === id).source;"
    "const at = n => PATTERN_FIELDS.find(f => f.name === n).offset;"
    "console.log(JSON.stringify({gatehold: s('gatehold'), momentmute: s('momentmute'), stepcopy: s('stepcopy'),"
    " gateArp: at('gateArp')}))")
GATE_ARP, TOUCH_SCALE, SHIFT, PART_MUTE, TRIGGER, SEQUENCER = 4, 5, 10, 16, 19, 21
LEDMGR = 0xC0345A1C             # the LED manager; +0xB58 the pad mode: 0 PART MUTE, 3 TRIGGER, 4 SEQUENCER
PLUGINS = ["gatehold", "momentmute"]
RAW_Y = 500


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled({"stepcopy": PRESETS["stepcopy"]})       # PRESETS is asked for when the module is imported
    edit.compiled({name: PRESETS[name] for name in PLUGINS})


def entry(name, ok, detail):
    return {"id": f"plugin_catalog15:{name}", "ok": bool(ok), "detail": str(detail)}


def touch(dev, x):
    dev.m.send([5, x >> 8, x & 0xFF, RAW_Y >> 8, RAW_Y & 0xFF])
    dev.run(0.12)


def gate_hold_cases(dev, build):
    """The finger down at raw X 400 (the firmware's 50), then on to 900 and 100, in Gate Arp and in Touch Scale mode."""
    xs = []
    mode = SCALE_MODE[build]
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: xs.append(uc.reg_read(UC_ARM_REG_R1)), begin=mode, end=mode)
    dev.m.uc.ctl_flush_tb()
    pattern = edit.pattern(dev)
    at = PRESETS["gateArp"]
    rhythm = lambda: dev.read(pattern + at, 1)[0]  # noqa: E731

    def slide():
        xs.clear()
        dev.m.send([0, TOUCH_KEY, 1, 0, 0])
        dev.run(0.05)
        seen = []
        for x in (400, 900, 100):
            touch(dev, x)
            seen.append(rhythm())
        firmware = sorted(set(xs))
        dev.m.send([0, TOUCH_KEY, 0, 0, 0])
        dev.run(0.15)
        return firmware, seen, rhythm()

    out = []
    edit.poke(dev, pattern + at, [7])
    edit.tap_key(dev, GATE_ARP, 0.3)
    firmware, seen, after = slide()
    out.append(entry("gate_hold_fixes_the_note", firmware == [50] and not dev.m.asserts,
                     f"firmware X {firmware} (the first touch's 50)"))
    want = [7, (900 * 50) >> 10, (100 * 50) >> 10]
    out.append(entry("gate_hold_x_picks_the_rhythm", seen == want and after == 7 and not dev.m.asserts,
                     f"rhythm while sliding {seen} (want {want}), after release {after} (want 7)"))

    dev.m.send([0, SHIFT, 1, 0, 0])
    dev.run(0.2)
    edit.tap_key(dev, TOUCH_SCALE, 0.4)
    dev.m.send([0, SHIFT, 0, 0, 0])
    dev.run(0.2)
    firmware, seen, after = slide()
    out.append(entry("gate_hold_leaves_touch_scale_alone", len(firmware) > 1 and seen == [7, 7, 7] and after == 7
                     and not dev.m.asserts, f"firmware X {firmware} (the finger's), rhythm {seen}, after {after}"))
    return out


def marked_presses(dev, key):
    """The down (1) and up (0) of each press of `key` that korg.pressKey hands over, seen at the dispatcher's start before
    the input filter (they carry the mark 0xB7)."""
    marked = []

    def dispatch(uc, *_):
        msg = bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0) + 0xC, 8))
        if msg[0] == 0 and msg[1] == key and msg[7] == 0xB7:
            marked.append(msg[2])
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, dispatch, begin=dev.a(remote_cases.DISPATCH), end=dev.a(remote_cases.DISPATCH))
    dev.m.uc.ctl_flush_tb()
    return marked


def moment_mute_cases(dev):
    """PART MUTE held: the firmware's PART MUTE mode, the pads toggle mutes and keep them. Released: TRIGGER mode."""
    mode = lambda: dev.u32(dev.u32(dev.a(LEDMGR)) + 0xB58)  # noqa: E731
    mutes = lambda: [dev.read(dev.a(edit.MUTE) + 0x330 * i, 1)[0] for i in range(16)]  # noqa: E731
    part = lambda: dev.u32(dev.a(edit.PART))  # noqa: E731
    toggled = lambda was, pads: [m ^ (1 if i in pads else 0) for i, m in enumerate(was)]  # noqa: E731
    marked = marked_presses(dev, TRIGGER)

    def key(k, down, wait=0.15):
        dev.m.send([0, k, down, 0, 0])
        dev.run(wait)

    out = []
    edit.tap_key(dev, SEQUENCER, 0.3)
    before = mutes()
    key(PART_MUTE, 1)
    held = mode()
    for index in (3, 5, 5, 7):
        edit.pad(dev, index)
    edited = mutes()
    # pad 10 goes down while PART MUTE is held and comes up after its release
    dev.m.send([4, 9, 0, 100, 1])
    dev.run(0.12)
    key(PART_MUTE, 0, 0.3)
    dev.m.send([4, 9, 0, 0, 0])
    dev.run(0.12)
    want = toggled(before, (3, 7, 9))
    out.append(entry("moment_mute_held_pads_toggle", held == 0 and edited == toggled(before, (3, 7)) and mutes() == want
                     and not dev.m.asserts,
                     f"pad mode while held {held} (want 0), mutes {before} -> {edited} -> {mutes()} (want {want})"))
    after = mutes()
    edit.pad(dev, 11)
    out.append(entry("moment_mute_release_is_trigger", mode() == 3 and marked == [1, 0] and mutes() == after
                     and part() == 11 and not dev.m.asserts,
                     f"pad mode after the release {mode()} (want 3), TRIGGER passed on {marked} (want press and release), "
                     f"pad 12 selects part {part()} (want 11), mutes kept {mutes() == after}"))

    edit.tap_key(dev, SEQUENCER, 0.3)
    marked.clear()
    key(PART_MUTE, 1)
    edit.tap_key(dev, SEQUENCER)
    key(PART_MUTE, 0, 0.3)
    chosen = mode()
    key(SHIFT, 1)
    key(PART_MUTE, 1)
    key(PART_MUTE, 0)
    key(SHIFT, 0, 0.3)
    out.append(entry("moment_mute_leaves_mode_keys_and_shift_alone", chosen == 4 and mode() == 4 and marked == []
                     and not dev.m.asserts,
                     f"SEQUENCER while held keeps {chosen}, after SHIFT + PART MUTE {mode()} (want 4), "
                     f"TRIGGER passed on {marked}"))
    return out


def step_copy_cases(vsb, flash, build):
    """The pages of Step Copy are turned in MANAGE PLUGINS (page 1 FROM, 2 TO, 3 COPY): the copy runs 0.6 s after the dial rests."""
    payload = vsb[0x100:]
    request = edit.compiled({"stepcopy": PRESETS["stepcopy"]})
    built = script_hooks.build(request["include"], build=build)
    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    edit.script_cases.install(dev, built, request["programs"], ["stepcopy"])
    dev.run(0.3)
    base = edit.pattern(dev)
    part = dev.u32(dev.a(edit.PART))
    other = (part + 1) % 16
    empty = [bytes(8)] * 16

    def record(p, step):
        return base + 2048 + 816 * p + 48 + 12 * step

    def bar(p, n):
        # writeSteps clamps the velocity to 1 or more, so an empty step is compared without it
        steps = [bytes(dev.read(record(p, 16 * n + s), 8)) for s in range(16)]
        return [x if x[0] else bytes([0, x[1], 0]) + x[3:] for x in steps]

    def put(p, n, step, note, velocity):
        edit.poke(dev, record(p, 16 * n + step), [1, 60 + step, velocity, 1, note + 1, 0, 0, 0])

    def length(bars):
        edit.poke(dev, base + 37, [bars - 1])

    def turn(n, steps, wait=1.0):
        menu_cases.goto_plugin(dev, 0, n + 1)
        dev.turn(steps, wait=wait)

    out = []
    length(4)
    for p in (part, other):
        for s in range(64):
            edit.poke(dev, record(p, s), [0] * 8)
    for s, (note, vel) in {0: (36, 100), 5: (40, 77), 15: (43, 90)}.items():
        put(part, 0, s, note, vel)
    put(other, 0, 2, 50, 64)
    turn(3, 1)
    out.append(entry("step_copy_part_into_bar_2", bar(part, 1) == bar(part, 0) and bar(part, 1)[5][2] == 77
                     and bar(other, 1) == empty and bar(part, 2) == empty and not dev.m.asserts,
                     f"bar 2 equals bar 1 {bar(part, 1) == bar(part, 0)}, other part untouched {bar(other, 1) == empty}, "
                     f"bar 3 untouched {bar(part, 2) == empty}"))

    turn(3, -1)
    turn(2, 1)
    turn(3, 2)
    out.append(entry("step_copy_all_parts_into_bar_3", bar(part, 2) == bar(part, 0) and bar(other, 2) == bar(other, 0)
                     and bar(other, 2)[2][4] == 51 and bar(part, 3) == empty and not dev.m.asserts,
                     f"bar 3 of both parts equals bar 1, bar 4 untouched {bar(part, 3) == empty}"))

    length(1)
    turn(3, -2)
    turn(2, 1)
    turn(3, 1)
    grown = dev.read(base + 37, 1)[0]
    out.append(entry("step_copy_target_beyond_length_lengthens", grown == 3 and bar(part, 3) == bar(part, 0) and not dev.m.asserts,
                     f"length byte {grown} (want 3), bar 4 equals bar 1 {bar(part, 3) == bar(part, 0)}"))

    length(2)
    turn(3, -2)
    turn(1, 3)
    before = bar(part, 0) + bar(part, 1)
    turn(3, 1)
    out.append(entry("step_copy_source_beyond_length_copies_nothing", bar(part, 0) + bar(part, 1) == before
                     and dev.read(base + 37, 1)[0] == 1 and not dev.m.asserts, "source bar 4 of a 2 bar pattern: no change"))
    return out


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    build = identify(payload).build
    request = edit.compiled({name: PRESETS[name] for name in PLUGINS})
    built = script_hooks.build(request["include"], build=build)
    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    edit.script_cases.install(dev, built, request["programs"], PLUGINS)
    dev.run(0.3)
    return gate_hold_cases(dev, build) + moment_mute_cases(dev) + step_copy_cases(vsb, flash, build)


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
