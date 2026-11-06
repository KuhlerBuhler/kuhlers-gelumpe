"""Emulator cases of plugin API 15: korg.touchLockX gives the firmware's touchpad modes a fixed X while the plugins get the
finger's, korg.keyHold keeps a key from the firmware without an app, korg.pressKey gives the firmware a short press through
its panel path, and korg.seq.setPatternValue sets each pattern value through the firmware's own setter, the byte as the
Pattern menu stores it.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_api15_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
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
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

TRANSPORT = 0xC06BC318
COMMAND = 9                     # the pattern whose filter type byte of part 0 says which call to make
TOUCH_KEY = 34
# Where the firmware turns the raw X of a touch message into its own X, (raw >> 4) * 2 on all three builds (measured in the
# emulator): in Master FX mode (the touchpad's start mode with BLECH) the handler stores it at +0x1c of its object (r0); in
# Touch Scale mode the scale handler hands it to the mode function in r1. The addresses of hacktribe and red are the same.
MFX_TOUCH = {"hacktribe": 0xC00454F8, "stock": 0xC00454F8, "synth": 0xC003F818}
SCALE_MODE = {"hacktribe": 0xC0060830, "stock": 0xC0060830, "synth": 0xC00572E8}
SHIFT, TOUCH_SCALE = 10, 5
RAW_X, RAW_Y = 400, 500

# korg.seq.setPatternValue: one value per field, each away from a pattern's usual one; mfxType past every build's top, syncGroup past 999
VALUES = {"tempo": 1234, "swing": -20, "length": 3, "beat": 2, "key": 5, "scale": 7, "chordSet": 3, "level": 77, "mfxType": 99,
          "chainTo": 5, "chainRepeat": 9, "gateArp": 12, "syncGroup": 1500}
FIELDS = json.loads(subprocess.check_output(["node", "--input-type=module", "-e",
    "import {PATTERN_FIELDS, PATTERN_WRITES} from './data/script/contract.mjs';"
    "console.log(JSON.stringify(PATTERN_FIELDS.map(f => [f.name, f.offset, f.kind, PATTERN_WRITES[f.name]])))"], cwd=ROOT))
SET_FIRST = 8

PROGRAM = f"""let tx = -1; let plays = 0; let done = 0;
korg.onEvent("touch", (x, y, first) => {{ tx = x; }});
korg.onEvent("buttonPress", (k) => {{ if (k == korg.key.PLAY) plays = plays + 1; }});
korg.onEvent("frame", () => {{
  let go = korg.read.patternValue({COMMAND}, 0, 1);
  if (go == done) return;
  done = go;
  if (go == 1) korg.touchLockX(64);
  if (go == 2) korg.touchLockX(127);
  if (go == 3) korg.touchLockX(-1);
  if (go == 4) korg.keyHold(korg.key.PLAY, 1);
  if (go == 5) korg.keyHold(korg.key.PLAY, 0);
  if (go == 6) korg.pressKey(korg.key.PLAY);
  if (go == 7) korg.pressKey(korg.key.STOP);
""" + "".join(f"\n  if (go == {SET_FIRST + i}) korg.seq.setPatternValue({i}, {VALUES[f[0]]});" for i, f in enumerate(FIELDS)) + """
});"""


def entry(name, ok, detail):
    return {"id": f"plugin_api15:{name}", "ok": bool(ok), "detail": str(detail)}


def command(dev, go, wait=0.3):
    edit.poke(dev, dev.a(edit.BANK) + COMMAND * 0x4000 + edit.PART_AT(0) + 12, [go])
    dev.run(wait)


def touch_cases(dev, build, program, at):
    """The finger at X 400 (the firmware's 50) with the touchpad key down, each lock in turn, in Master FX and Touch Scale mode."""
    objects, scale = [], []
    mfx, mode = MFX_TOUCH[build], SCALE_MODE[build]
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: objects.append(uc.reg_read(UC_ARM_REG_R0)), begin=mfx, end=mfx)
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: scale.append(uc.reg_read(UC_ARM_REG_R1)), begin=mode, end=mode)
    dev.m.uc.ctl_flush_tb()

    def finger():
        objects.clear()
        scale.clear()
        dev.m.send([0, TOUCH_KEY, 1, 0, 0])
        dev.run(0.05)
        dev.m.send([5, RAW_X >> 8, RAW_X & 0xFF, RAW_Y >> 8, RAW_Y & 0xFF])
        dev.run(0.1)
        firmware = sorted({dev.u32(o + 0x1C) for o in objects}) + sorted(set(scale))
        dev.m.send([0, TOUCH_KEY, 0, 0, 0])
        dev.run(0.1)
        return firmware, edit.script_cases.variables(dev, at, program)["tx"]

    def locks():
        free = finger()
        command(dev, 1)
        locked = finger()
        command(dev, 2)
        top = finger()
        command(dev, 3)
        return free, locked, top, finger()

    out = []
    command(dev, 3)         # the command byte is the stored pattern's: whatever it held at boot, start with no lock
    for name in ("master_fx", "touch_scale"):
        if name == "touch_scale":
            dev.m.send([0, SHIFT, 1, 0, 0])
            dev.run(0.2)
            edit.tap_key(dev, TOUCH_SCALE, 0.4)
            dev.m.send([0, SHIFT, 0, 0, 0])
            dev.run(0.2)
        free, locked, top, back = locks()
        command(dev, 0)
        out.append(entry(f"touch_lock_x_{name}", free[0] == [RAW_X >> 4 << 1] and locked[0] == [64] and top[0] == [126]
                         and back[0] == free[0] and not dev.m.asserts,
                         f"firmware X free {free[0]}, lock 64 {locked[0]}, lock 127 {top[0]}, after -1 {back[0]}"))
        out.append(entry(f"touch_lock_x_{name}_plugin_gets_the_finger", free[1] == locked[1] == top[1] == back[1] == RAW_X,
                         f"plugin X free {free[1]}, lock 64 {locked[1]}, lock 127 {top[1]}, after -1 {back[1]}"))
    return out


def key_cases(dev, program, at):
    out = []
    dispatched = []

    # the hook sits at the dispatcher's start, before the input filter: it sees what the panel queue hands over
    def dispatch(uc, *_):
        msg = bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0) + 0xC, 8))
        if msg[0] == 0 and msg[1] in (1, 2):
            dispatched.append(msg)
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, dispatch, begin=dev.a(remote_cases.DISPATCH), end=dev.a(remote_cases.DISPATCH))
    dev.m.uc.ctl_flush_tb()
    plays = lambda: edit.script_cases.variables(dev, at, program)["plays"]  # noqa: E731

    command(dev, 4)
    before = plays()
    edit.tap_key(dev, 2, 0.3)
    held = dev.u32(TRANSPORT), plays() - before
    out.append(entry("key_hold_without_an_app", held[0] == 0 and held[1] == 1 and dev.read(script_hooks.KEY_HOLD, 4) != b"\xff" * 4
                     and not dev.m.asserts, f"transport {held[0]}, plugin presses {held[1]}"))
    command(dev, 5)
    edit.tap_key(dev, 2, 0.3)
    free = dev.u32(TRANSPORT)
    edit.tap_key(dev, 1, 0.3)
    stopped = dev.u32(TRANSPORT)
    out.append(entry("key_hold_lets_go", free != 0 and stopped == 0 and not dev.m.asserts, f"transport after PLAY {free}, after STOP {stopped}"))

    before = plays()
    dispatched.clear()
    command(dev, 6)
    pressed = dev.u32(TRANSPORT), plays() - before, list(dispatched)
    marked = [m.hex() for m in pressed[2]]
    out.append(entry("press_key_plays_through_the_panel_path", pressed[0] != 0 and pressed[1] == 0
                     and [(m[1], m[2], m[7]) for m in pressed[2]] == [(2, 1, 0xB7), (2, 0, 0xB7)]
                     and dev.read(script_hooks.PRESS_KEY, 8) == b"\xff" * 8 and not dev.m.asserts,
                     f"transport {pressed[0]}, plugin presses {pressed[1]}, dispatched {marked}"))
    command(dev, 7)
    out.append(entry("press_key_stop", dev.u32(TRANSPORT) == 0 and not dev.m.asserts, f"transport {dev.u32(TRANSPORT)}"))
    return out


def expected(build, name, kind, write):
    """The bytes the Pattern menu stores for VALUES[name]: clamped to the write range (MFX TYPE to 31 on the synth), bars
    minus 1, Chain To plus 1, tempo as a u16."""
    top = 31 if build == "synth" and name == "mfxType" else write[1]
    v = min(top, max(write[0], VALUES[name]))
    v = v - 1 if kind == "bars" else v + 1 if kind == "chain" else v
    return v.to_bytes(2, "little") if kind == "u16" else bytes([v & 0xFF])


def pattern_cases(dev, build, at):
    pattern = edit.pattern(dev)
    out = []
    for i, (name, offset, kind, write) in enumerate(FIELDS):
        want = expected(build, name, kind, write)
        before = dev.read(pattern, 0x4900)
        command(dev, SET_FIRST + i)
        after = dev.read(pattern, 0x4900)
        got = after[offset:offset + len(want)]
        changed = [hex(j) for j in range(0x4900) if before[j] != after[j]]
        state = dev.u32(at + 12)
        out.append(entry(f"set_pattern_value_{name}", got == want and state == 2 and not dev.m.asserts,
                         f"byte {offset} {got.hex()} (want {want.hex()}), changed {changed[:8]}, script state {state}"))
    command(dev, 0)
    return out


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    build = identify(payload).build
    request = edit.compiled({"api15": PROGRAM})
    built = script_hooks.build(request["include"], build=build)
    program = request["programs"]["api15"]
    dev, at = edit.running(vsb, flash, built, request["programs"], "api15")
    return touch_cases(dev, build, program, at) + key_cases(dev, program, at) + pattern_cases(dev, build, at)


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
