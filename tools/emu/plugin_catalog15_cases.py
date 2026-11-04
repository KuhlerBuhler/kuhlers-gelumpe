"""Emulator cases of the catalog plugins on plugin API 15, as the catalog ships them: Gate Hold fixes the note in Gate Arp
mode and lets X pick the pattern's Gate Arp rhythm, Key Pads sets the pattern's KEY with KEYBOARD held and a pad, and a
short press of KEYBOARD alone still reaches the firmware.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_catalog15_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1  # noqa: E402
from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import remote_cases  # noqa: E402
from plugin_api15_cases import SCALE_MODE, TOUCH_KEY  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

PRESETS = json.loads(subprocess.check_output(["node", "--input-type=module", "-e",
    "import {PRESETS} from './data/script/presets.mjs';"
    "import {PATTERN_FIELDS} from './data/script/contract.mjs';"
    "const s = id => PRESETS.find(p => p.id === id).source;"
    "const at = n => PATTERN_FIELDS.find(f => f.name === n).offset;"
    "console.log(JSON.stringify({gatehold: s('gatehold'), keypads: s('keypads'), gateArp: at('gateArp'), key: at('key')}))"], cwd=ROOT))
GATE_ARP, TOUCH_SCALE, SHIFT, KEYBOARD = 4, 5, 10, 23
RAW_Y = 500
# Per pad the KEY Key Pads sets, -1 none: the lower row (pads 9 to 16) C D E F G A B C, the upper row the black keys.
NOTES = [-1, 1, 3, -1, 6, 8, 10, -1, 0, 2, 4, 5, 7, 9, 11, 0]


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


def key_pads_cases(dev):
    pattern = edit.pattern(dev)
    at = PRESETS["key"]
    key = lambda: dev.read(pattern + at, 1)[0]  # noqa: E731
    marked = []

    # the dispatcher's start, before the input filter: a press korg.pressKey hands over carries the mark 0xB7
    def dispatch(uc, *_):
        msg = bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0) + 0xC, 8))
        if msg[0] == 0 and msg[1] == KEYBOARD and msg[7] == 0xB7:
            marked.append(msg[2])
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, dispatch, begin=dev.a(remote_cases.DISPATCH), end=dev.a(remote_cases.DISPATCH))
    dev.m.uc.ctl_flush_tb()

    out = []
    edit.poke(dev, pattern + at, [0])
    dev.m.send([0, KEYBOARD, 1, 0, 0])
    dev.run(0.15)
    got = []
    for index in range(16):
        edit.pad(dev, index)
        got.append(key())
    dev.m.send([0, KEYBOARD, 0, 0, 0])
    dev.run(0.3)
    want, last = [], 0
    for n in NOTES:
        last = n if n >= 0 else last
        want.append(last)
    out.append(entry("key_pads_set_the_key", got == want and marked == [] and not dev.m.asserts,
                     f"KEY after each pad {got} (want {want}), KEYBOARD passed on {marked}"))

    edit.tap_key(dev, KEYBOARD, 0.4)
    out.append(entry("key_pads_short_press_reaches_the_firmware", marked == [1, 0] and key() == want[-1]
                     and dev.read(script_hooks.PRESS_KEY, 8) == b"\xff" * 8 and not dev.m.asserts,
                     f"KEYBOARD passed on {marked} (want press and release), KEY {key()}"))
    return out


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    build = identify(payload).build
    request = edit.compiled({"gatehold": PRESETS["gatehold"], "keypads": PRESETS["keypads"]})
    built = script_hooks.build(request["include"], build=build)
    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    edit.script_cases.install(dev, built, request["programs"], ["gatehold", "keypads"])
    dev.run(0.3)
    return gate_hold_cases(dev, build) + key_pads_cases(dev)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
