"""Emulator cases of plugin API 16: what a plugin keeps from the firmware is its own mask (korg.keyMask, and what korg.keyHold,
korg.padHold and korg.knobHold set for the calling plugin), and the input filter masks an input while ANY running plugin
masks it. Two plugins mask the same key, pads and knob: the firmware gets the input only when neither does, and both plugins
get it either way.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_api16_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

TRANSPORT = 0xC06BC318
COMMAND = 9                     # the pattern whose filter type byte of part 0 says which call to make
PLAY, STOP = 2, 1
PAD_BIT = 0x10                  # the pad bit of the capture mask (script_hooks.s: INPUT_PAD_BIT)

HEAD = f"""let plays = 0; let done = 0;
korg.onEvent("buttonPress", (k) => {{ if (k == korg.key.PLAY) plays = plays + 1; }});
korg.onEvent("frame", () => {{
  let go = korg.read.patternValue({COMMAND}, 0, 1);
  if (go == done) return;
  done = go;
"""
PROGRAMS = {
    "api16a": HEAD + """  if (go == 1) korg.keyMask(1 << korg.key.PLAY, 0);
  if (go == 2) korg.keyMask(0, 0);
  if (go == 5) korg.padHold(1);
  if (go == 6) korg.padHold(0);
  if (go == 7) korg.knobHold(9, 1);
  if (go == 8) korg.knobHold(9, 0);
});""",
    "api16b": HEAD + """  if (go == 3) korg.keyHold(korg.key.PLAY, 1);
  if (go == 4) korg.keyHold(korg.key.PLAY, 0);
  if (go == 9) korg.padHold(1);
  if (go == 10) korg.padHold(0);
  if (go == 11) korg.knobHold(9, 1);
  if (go == 12) korg.knobHold(9, 0);
});""",
}


def entry(name, ok, detail):
    return {"id": f"plugin_api16:{name}", "ok": bool(ok), "detail": str(detail)}


def command(dev, go, wait=0.3):
    edit.poke(dev, dev.a(edit.BANK) + COMMAND * 0x4000 + edit.PART_AT(0) + 12, [go])
    dev.run(wait)


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    build = identify(payload).build
    request = edit.compiled(PROGRAMS)
    built = script_hooks.build(request["include"], build=build)
    programs = request["programs"]
    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    at = script_cases.install(dev, built, programs, list(PROGRAMS))
    plays = lambda name: script_cases.variables(dev, at[name], programs[name])["plays"]  # noqa: E731
    mask = lambda: dev.u32(built.layout["runtime"] + built.symbols["SCRIPT_CONTROL_CAPTURE_MASK"])  # noqa: E731
    knobs = lambda: dev.u32(script_hooks.KNOB_HOLD)  # noqa: E731
    out = []

    command(dev, 0)
    edit.tap_key(dev, PLAY, 0.3)
    started = dev.u32(TRANSPORT)
    edit.tap_key(dev, STOP, 0.3)
    out.append(entry("nobody_masks_the_firmware_gets_the_key", started != 0 and dev.u32(TRANSPORT) == 0 and not dev.m.asserts,
                     f"transport after PLAY {started}"))

    command(dev, 1)
    before = plays("api16a"), plays("api16b")
    edit.tap_key(dev, PLAY, 0.3)
    one = dev.u32(TRANSPORT), plays("api16a") - before[0], plays("api16b") - before[1]
    out.append(entry("a_key_mask_keeps_the_key_and_both_plugins_get_it", one == (0, 1, 1) and not dev.m.asserts,
                     f"transport {one[0]}, presses seen by a {one[1]}, by b {one[2]}"))
    command(dev, 3)
    command(dev, 2)
    edit.tap_key(dev, PLAY, 0.3)
    both = dev.u32(TRANSPORT)
    out.append(entry("two_plugins_one_key_the_second_keeps_it_when_the_first_lets_go", both == 0 and not dev.m.asserts,
                     f"transport {both}, plugins' presses {plays('api16a') - before[0]} and {plays('api16b') - before[1]} since the mask"))
    command(dev, 4)
    edit.tap_key(dev, PLAY, 0.3)
    free = dev.u32(TRANSPORT)
    edit.tap_key(dev, STOP, 0.3)
    out.append(entry("both_let_go_the_firmware_gets_the_key", free != 0 and dev.u32(TRANSPORT) == 0 and not dev.m.asserts,
                     f"transport after PLAY {free}"))

    command(dev, 5)
    command(dev, 9)
    held = mask() & PAD_BIT
    command(dev, 6)
    still = mask() & PAD_BIT
    command(dev, 10)
    gone = mask() & PAD_BIT
    out.append(entry("pads_are_masked_while_either_plugin_holds_them", (held, still, gone) == (PAD_BIT, PAD_BIT, 0) and not dev.m.asserts,
                     f"pad bit with both {held:#x}, with b {still:#x}, with none {gone:#x}"))

    command(dev, 7)
    command(dev, 11)
    command(dev, 8)
    still = knobs()
    command(dev, 12)
    out.append(entry("a_knob_is_masked_while_either_plugin_holds_it", still == 0xFFFFFFFF ^ 1 << 9 and knobs() == 0xFFFFFFFF and not dev.m.asserts,
                     f"knob word with b {still:#x}, with none {knobs():#x}"))
    out.append(entry("both_plugins_still_run", dev.u32(at["api16a"] + 12) == 2 and dev.u32(at["api16b"] + 12) == 2,
                     f"states {dev.u32(at['api16a'] + 12)} and {dev.u32(at['api16b'] + 12)}"))
    return out


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
