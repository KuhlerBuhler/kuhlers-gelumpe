"""Emulator cases of the catalog plugins on plugin API 28 to 34, as the catalog ships them: System Info redraws its power line
when the adapter goes, VU Meter draws a bar as long as the level, MIDI Echo sends the pads on the channel of its page and
Motion Clear clears the selected part's motion lanes from its page in the BLECH menu.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_catalog_api_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
import menu_cases  # noqa: E402
import node_json  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from plugin_api30_cases import UART1, GLOBAL, CHANNEL_AT  # noqa: E402
from plugin_api31_cases import LEVELS, METER  # noqa: E402
from tap_motion_cases import KEYS  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

NAMES = ("sysinfo", "vumeter", "midiecho", "motionclear")
PRESETS = node_json.run(
    "import {PRESETS} from './data/script/presets.mjs';"
    "import {PATTERN_MOTION} from './data/script/contract.mjs';"
    f"const ids = {json.dumps(list(NAMES))};"
    "const out = Object.fromEntries(ids.map(id => [id, PRESETS.find(p => p.id === id).source]));"
    "out.owner = PATTERN_MOTION.owner; out.lanes = PATTERN_MOTION.lanes;"
    "console.log(JSON.stringify(out))")
APP_PAGE = 1                                    # the page of the app in TOOLS, behind Blechy


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    for name in NAMES:
        edit.compiled({name: PRESETS[name]})


def entry(name, ok, detail):
    return {"id": f"plugin_catalog_api:{name}", "ok": bool(ok), "detail": str(detail)}


def lit(fb):
    return sum(bin(b).count("1") for b in fb)


def app(vsb, flash, name):
    """The app on the card, opened from TOOLS as the user opens it."""
    dev = edit.boot(vsb, flash, edit.compiled({name: PRESETS[name]})["programs"], name)
    script_cases.open_app(dev, menu_cases.GROUP_TOOLS, APP_PAGE)
    dev.run(0.5)
    return dev


def running(vsb, flash, name):
    """A background plugin on the card, as the user has it: its pages in the BLECH menu come from the card load."""
    return edit.boot(vsb, flash, edit.compiled({name: PRESETS[name]})["programs"], name)


def turn_page(dev, steps):
    """Turns the page the plugin added and goes back to the main screen: the firmware keeps pad presses from plugins while
    the BLECH menu is open."""
    menu_cases.goto_plugin(dev, 0, 2)              # DESCRIPTION, STATE, then the page it added
    dev.turn(steps, wait=0.5)
    menu_cases.leave_to_main(dev)


def sysinfo_cases(vsb, flash, build):
    """Panel message 7 switches between adapter and battery: the open app draws another last line within its 1 s redraw."""
    dev = app(vsb, flash, "sysinfo")
    shown = []
    for on in (1, 0, 1):
        dev.m.send([0x07, on, 0, 0, 0])
        dev.run(1.5)
        shown.append(bytes(dev.fb()))
    ok = lit(shown[0]) > 0 and shown[0] != shown[1] and shown[0] == shown[2] and not dev.m.asserts
    return [entry("sysinfo_follows_the_adapter", ok, f"build {build}: pixels {[lit(s) for s in shown]}, adapter/battery differ "
                  f"{shown[0] != shown[1]}, adapter again equal {shown[0] == shown[2]}")]


def vumeter_cases(vsb, flash, build):
    """Raw levels put into the meter's object right before every call of the meter, as the DSP side leaves them: a loud
    signal draws more pixels than silence, and the bars go back once the peak hold of 1 s is over."""
    dev = app(vsb, flash, "vumeter")
    raw = [0, 0]

    def poke():
        obj = dev.u32(LEVELS)
        if obj in (0, 0xFFFFFFFF):
            return
        word = dev.m.u32(obj + 0x14)
        dev.m.uc.mem_write(obj + 0x13, bytes([raw[0] & 0xFF]))
        dev.m.uc.mem_write(obj + 0x14, ((word & 0xFFFFFF) | ((raw[1] & 0xFF) << 24)).to_bytes(4, "little"))

    at = dev.a(METER)
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: poke(), begin=at, end=at)
    dev.m.uc.ctl_flush_tb()
    seen = []
    for a, b in ((0, 0), (127, 64), (0, 0)):
        raw[:] = [a, b]
        dev.run(2.5)
        seen.append(lit(dev.fb()))
    ok = seen[1] > seen[0] + 500 and seen[2] == seen[0] and not dev.m.asserts
    return [entry("vumeter_draws_the_level", ok, f"build {build}: pixels silent, loud, silent again {seen}")]


def midiecho_cases(vsb, flash, build):
    """Page 0 (off) sends nothing of its own; channel 10 sends pad 4 as note 39 with the pad's velocity, and the note off
    goes on the note on's channel after the page moved to 2."""
    dev = running(vsb, flash, "midiecho")
    tx = dev.m.uart[UART1]["tx"]
    mark = len(tx)

    def sent():
        nonlocal mark
        data, mark = bytes(tx[mark:]), len(tx)
        return bytes(b for b in data if b < 0xF8)

    channel = dev.m.uc.mem_read(dev.u32(GLOBAL) + CHANNEL_AT, 1)[0]
    edit.pad(dev, 3)
    off = sent()
    turn_page(dev, 10)
    sent()
    dev.m.send([4, 3, 0, 100, 1])
    dev.run(0.2)
    on = sent()
    turn_page(dev, -8)
    sent()
    dev.m.send([4, 3, 0, 0, 0])
    dev.run(0.2)
    release = sent()
    ok = (bytes([0x99, 39]) not in off and bytes([0x99, 39, 100]) in on and bytes([0x89, 39, 0x40]) in release
          and bytes([0x81, 39]) not in release and not dev.m.asserts)
    return [entry("midiecho_sends_on_the_page_channel", ok, f"build {build}: global channel {channel + 1}, off {off.hex(' ')}, "
                  f"on {on.hex(' ')}, release {release.hex(' ')}")]


def record(dev):
    """REC, PLAY, knob 0 swept for 3 s, STOP: the firmware records a lane for the selected part (tap_motion_cases.TBox)."""
    dev.press(KEYS["rec"], 0.2)
    dev.press(KEYS["play"], 0.0)
    for i in range(60):
        dev.m.send([2, 0, 0, (i * 4) & 0x7F, 0])
        dev.run(0.05)
    dev.press(KEYS["stop"], 0.5)


def motionclear_cases(vsb, flash, build):
    """A lane recorded for the selected part; the page at 2 changes nothing, 3 clears the lane through the firmware's
    clear, a lane recorded again stays when the page is turned on past 3 without going below."""
    dev = running(vsb, flash, "motionclear")
    owner = edit.pattern(dev) + PRESETS["owner"]
    part = dev.u32(dev.a(edit.PART)) & 0xFF
    lanes = lambda: [o for o in dev.read(owner, PRESETS["lanes"]) if o]  # noqa: E731
    record(dev)
    recorded = lanes()
    turn_page(dev, 2)
    below = lanes()
    turn_page(dev, 1)
    cleared = lanes()
    record(dev)
    again = lanes()
    turn_page(dev, 1)                        # the page ends at 3: the value stays
    kept = lanes()
    ok = (recorded == [part + 1] and below == recorded and cleared == [] and again == [part + 1] and kept == again
          and not dev.m.asserts)
    return [entry("motionclear_clears_the_selected_part", ok, f"build {build}: part {part + 1}, owners recorded {recorded}, "
                  f"at 2 {below}, at 3 {cleared}, recorded again {again}, turned on at 3 {kept}")]


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    build = identify(payload).build
    return (sysinfo_cases(vsb, flash, build) + vumeter_cases(vsb, flash, build) + midiecho_cases(vsb, flash, build)
            + motionclear_cases(vsb, flash, build))


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
