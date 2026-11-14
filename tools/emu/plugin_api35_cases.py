"""Emulator cases of plugin API 35: korg.touchLockY gives the firmware's touchpad modes a fixed Y while the plugins get the
finger's, in Master FX, Touch Scale and Gate Arp mode.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_api35_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-12-plugin-touch-lock-y.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2  # noqa: E402
from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
from plugin_api15_cases import COMMAND, MFX_TOUCH, SCALE_MODE, SHIFT, TOUCH_KEY, TOUCH_SCALE, command

GATE_ARP = 4
RAW_X, RAW_Y = 400, 500
LOCKS = {1: 64, 2: 127, 3: 33}     # the command byte and the y it locks; 4 lets go

PROGRAM = f"""let tx = -1; let ty = -1; let done = 0;
korg.onEvent("touch", (x, y, first) => {{ tx = x; ty = y; }});
korg.onEvent("frame", () => {{
  let go = korg.read.patternValue({COMMAND}, 0, 1);
  if (go == done) return;
  done = go;
""" + "".join(f"  if (go == {go}) korg.touchLockY({y});\n" for go, y in LOCKS.items()) + """  if (go == 4) korg.touchLockY(-1);
});"""


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled({"api35": PROGRAM})


def entry(name, ok, detail):
    return {"id": f"plugin_api35:{name}", "ok": bool(ok), "detail": str(detail)}


def want_y(mode, y):
    """The Y the firmware takes from raw y << 3: (raw >> 4) * 2 in Master FX, raw >> 3 in the scale and gate mode function."""
    return (y << 3 >> 4 << 1) if mode == "master_fx" else y


def touch_cases(dev, build, program, at):
    """The finger at X 400, Y 500 with the touchpad key down, each Y lock in turn, in each touchpad mode."""
    objects, scale = [], []
    mfx, mode_fn = MFX_TOUCH[build], SCALE_MODE[build]
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: objects.append(uc.reg_read(UC_ARM_REG_R0)), begin=mfx, end=mfx)
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: scale.append((uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2))),
                      begin=mode_fn, end=mode_fn)
    dev.m.uc.ctl_flush_tb()

    def finger(mode):
        objects.clear()
        scale.clear()
        dev.m.send([0, TOUCH_KEY, 1, 0, 0])
        dev.run(0.05)
        dev.m.send([5, RAW_X >> 8, RAW_X & 0xFF, RAW_Y >> 8, RAW_Y & 0xFF])
        dev.run(0.1)
        if mode == "master_fx":
            seen = sorted({(dev.u32(o + 0x1C), dev.u32(o + 0x20)) for o in objects})
        else:
            seen = sorted(set(scale))
        dev.m.send([0, TOUCH_KEY, 0, 0, 0])
        dev.run(0.1)
        v = edit.script_cases.variables(dev, at, program)
        return seen, (v["tx"], v["ty"])

    out = []
    command(dev, 4)         # the command byte is the stored pattern's: whatever it held at boot, start with no lock
    for mode in ("master_fx", "gate_arp", "touch_scale"):
        if mode == "gate_arp":
            edit.tap_key(dev, GATE_ARP, 0.3)
        if mode == "touch_scale":
            dev.m.send([0, SHIFT, 1, 0, 0])
            dev.run(0.2)
            edit.tap_key(dev, TOUCH_SCALE, 0.4)
            dev.m.send([0, SHIFT, 0, 0, 0])
            dev.run(0.2)
        free = finger(mode)
        locked = {}
        for go, y in LOCKS.items():
            command(dev, go)
            locked[y] = finger(mode)
        command(dev, 4)
        back = finger(mode)
        command(dev, 0)
        fx = free[0][0][0] if len(free[0]) == 1 else None
        want = {y: [(fx, want_y(mode, y))] for y in LOCKS.values()}
        ok = (len(free[0]) == 1 and free[0][0][1] == want_y(mode, RAW_Y >> 3) and all(locked[y][0] == want[y] for y in want)
              and back[0] == free[0] and not dev.m.asserts)
        out.append(entry(f"touch_lock_y_{mode}", ok, f"firmware (X, Y) free {free[0]}, "
                         + ", ".join(f"lock {y} {locked[y][0]} (want {want[y]})" for y in want) + f", after -1 {back[0]}"))
        plugin = [free[1]] + [locked[y][1] for y in want] + [back[1]]
        out.append(entry(f"touch_lock_y_{mode}_plugin_gets_the_finger", all(p == (RAW_X, RAW_Y) for p in plugin),
                         f"plugin (x, y) {plugin}"))
    out.append(entry("touch_lock_y_lets_go_when_the_plugin_stops", dev.read(script_hooks.TOUCH_LOCK_Y, 4) == b"\xff" * 4,
                     f"record {dev.read(script_hooks.TOUCH_LOCK_Y, 12).hex()}"))
    return out


def stop_case(vsb, flash, build):
    """A plugin that locked Y and is then stopped: the runtime's guard lets go."""
    request = edit.compiled({"api35": PROGRAM})
    built = script_hooks.build(request["include"], build=build)
    dev, at = edit.running(vsb, flash, built, request["programs"], "api35")
    command(dev, 1)
    held = dev.read(script_hooks.TOUCH_LOCK_Y, 4)
    edit.poke(dev, at + 12, (3).to_bytes(4, "little"))      # the script state of a plugin that faulted
    dev.run(0.3)
    after = dev.read(script_hooks.TOUCH_LOCK_Y, 4)
    return [entry("touch_lock_y_stopped_plugin_lets_go", held == (64 << 3).to_bytes(4, "little") and after == b"\xff" * 4
                  and not dev.m.asserts, f"record while running {held.hex()}, after the stop {after.hex()}")]


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    build = identify(payload).build
    request = edit.compiled({"api35": PROGRAM})
    built = script_hooks.build(request["include"], build=build)
    program = request["programs"]["api35"]
    dev, at = edit.running(vsb, flash, built, request["programs"], "api35")
    return touch_cases(dev, build, program, at) + stop_case(vsb, flash, build)


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
