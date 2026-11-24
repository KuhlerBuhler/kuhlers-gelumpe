"""How much of the firmware heap (operator new) is left in normal use: boot with a card, pattern changes, a sample import, a
plugin with a data file. Prints the heap cursor after each step, the largest single request seen, and the largest block a new
still gets at the end (tried from big to small, each given back at once). The numbers are in
docs/messungen/2026-11-17-plugin-daten-heap.md.

    tools/emu/.venv/bin/python tools/emu/heap_headroom.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import import_slots_cases as imp  # noqa: E402
import last_pattern_cases as lp  # noqa: E402
import menu_cases  # noqa: E402
import plugin_api32_cases as api32  # noqa: E402
import script_cases  # noqa: E402
from highram_watch import plain_wav  # noqa: E402
from machine import load_flash  # noqa: E402
from tools.patch import script_hooks  # noqa: E402
import lifetime  # noqa: E402
import unicorn  # noqa: E402
from unicorn import arm_const  # noqa: E402

# Sampler places (2026-10-08-systemspeicher-offline.md); the blue's from its grow routine 0xC002A060 and data/synth-map/.
CURSOR = 0xC03404AC
NEW, DELETE = 0xC0028DCC, 0xC0028DD4
POOL = {False: (0xC06A2940, 0xC08A2940), True: (0xC0573CFC, 0xC0773CFC)}
SYNTH_DELETE = 0xC0026248
PROBE = [1 << 20, 768 << 10, 512 << 10, 384 << 10, 256 << 10, 192 << 10, 128 << 10, 96 << 10, 64 << 10, 32 << 10]
MAIN_SCREEN = 1


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    api32.node_requests()


def measure(vsb, flash):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    dev = lp.boot(payload, flash, files={imp.WAV: plain_wav(48000)})
    menu_cases.keep_awake(dev)
    synth = dev.synth
    base, end = POOL[synth]
    new = dev.a(NEW)
    delete = SYNTH_DELETE if synth else DELETE
    requests = []
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: requests.append(uc.reg_read(arm_const.UC_ARM_REG_R0)), begin=new, end=new)
    dev.m.uc.ctl_flush_tb()
    steps = []

    def step(name, ok=True):
        cursor = dev.u32(CURSOR)
        steps.append({"step": name, "ok": bool(ok), "used": cursor - base, "left": end - cursor,
                      "largest_request": max(requests, default=0), "requests": len(requests)})

    dev.run(3.0)
    step("boot")
    before = len(dev.chosen)
    for _ in range(5):
        dev.turn(1, 1.0)
    dev.run(2.0)
    step("pattern changes", len(dev.chosen) > before)
    if not synth:                       # the blue has no sample import
        imp.destination_screen(dev)
        slot = imp.dest(dev) - 1
        dev.press(imp.KEYS["menu"], 1.0)
        for _ in range(40):
            dev.run(1.0)
            if imp.name_of(dev, slot) == "Kick":
                break
        dev.run(3.0)
        step("sample import", imp.name_of(dev, slot) == "Kick")
    menu_cases.go(dev, MAIN_SCREEN)
    dev.run(1.0)
    request = api32.edit.compiled(api32.PROGRAMS)
    built = script_hooks.build(request["include"], build=api32.identify(payload).build)
    at = script_cases.install(dev, built, request["programs"], ["keeper"])["keeper"]
    dev.run(4.0)
    program = request["programs"]["keeper"]
    step("plugin with data file", script_cases.variables(dev, at, program)["wrote"] > 0)
    for _ in range(3):
        dev.turn(-1, 1.0)
    dev.run(2.0)
    step("pattern changes with plugin")
    largest = 0
    for size in PROBE:
        block = dev.call(NEW, size)            # call() maps the Sampler address itself
        if block:
            dev.call(delete, block)
            largest = size
            break
    cursor = dev.u32(CURSOR)
    return {"build": api32.identify(payload).build, "pool": [hex(base), hex(end)], "steps": steps,
            "largest_new_at_end": largest, "left_at_end": end - cursor, "asserts": dev.m.asserts}


def main():
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    print(json.dumps(measure(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None), indent=1))


if __name__ == "__main__":
    main()
