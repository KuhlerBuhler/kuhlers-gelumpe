"""Emulator cases of the catalog apps (GAMES and TOOLS), as the catalog ships them: each app on the card opens from its
group in the BLECH menu, draws the same start screen as the browser's simulator (src/script/sim.mjs) byte for byte, and
EXIT gives the main screen back. The app's own cases follow in between. Blechy Run: TAP makes Blechy jump, a block ends
the run with GAME OVER.

A new catalog app: an entry in APPS (its id, group and own cases).

    PYTHONPATH=tools/patch python3 tools/emu/catalog_app_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import menu_cases  # noqa: E402
import node_json  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from machine import load_flash  # noqa: E402

FB = 0xC031B310                 # the LCD's 128x64 bytes, 8-pixel column strips, lowest bit on top
OPEN_S = 0.3                    # from ENTER to the comparison of the start screen

# the source of a catalog app, and its first screen in the simulator after OPEN_S (75 frames would be 3 s; the app has
# drawn its start screen at the first frame, and nothing moves before a key)
SIM = """
import { PRESETS } from "./data/script/presets.mjs";
import { compile } from "./src/script/compiler.mjs";
import { SimDevice } from "./src/script/sim.mjs";
const p = PRESETS.find(p => p.id === process.argv[1]);
const r = compile(p.source, { name: p.id });
const d = new SimDevice(); d.load(r.blob); d.openApp(0); d.run(3);
process.stdout.write(JSON.stringify({ source: p.source, screen: Buffer.from(d.display.bytes).toString("hex") }));
"""


def sim(app_id):
    """{source, screen (hex)} of the catalog app `app_id` from this checkout."""
    return node_json.run(SIM, app_id)


def pixel(fb, x, y):
    return (fb[(y >> 3) * 128 + x] >> (y & 7)) & 1


def blechyrun(dev, check):
    """TAP (key 3) makes Blechy jump: his top rises from 36 on the ground to about 11, not above the cleared field (y 10).
    Left alone, the next block ends the run: GAME OVER across the middle."""
    def top():
        fb = bytes(dev.read(FB, 1024))
        return next((y for y in range(10, 64) if any(pixel(fb, x, y) for x in range(8, 28))), None)

    script_cases.tap(dev, 3, hold=0.05)
    tops = []
    for _ in range(10):
        dev.run(0.04)
        tops.append(top())
    seen = [t for t in tops if t is not None]
    check("blechyrun_tap_jumps", seen and 11 <= min(seen) < 30 and not dev.m.asserts, f"his top every 40 ms: {tops}")
    dev.run(8.0)
    fb = bytes(dev.read(FB, 1024))
    check("blechyrun_a_block_ends_the_run", any(pixel(fb, x, 18) for x in range(37, 91)) and not dev.m.asserts,
          f"GAME OVER row y 18 lit: {sum(pixel(fb, x, 18) for x in range(37, 91))} pixels, asserts {dev.m.asserts}")


# id: (group in the BLECH menu, the app's own cases between opening and EXIT)
APPS = {
    "blechyrun": (menu_cases.GROUP_GAMES, blechyrun),
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    for app_id in APPS:
        edit.compiled({app_id: sim(app_id)["source"]})


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    out = []
    for app_id, (group, own) in APPS.items():
        def check(name, ok, detail=""):
            out.append({"id": f"catalog_app:{name}", "ok": bool(ok), "detail": str(detail)})

        ref = sim(app_id)
        programs = edit.compiled({app_id: ref["source"]})["programs"]
        dev = edit.boot(vsb, flash, programs, app_id)
        script_cases.open_app(dev, group)
        dev.run(OPEN_S)
        shown = bytes(dev.read(FB, 1024))
        start = bytes.fromhex(ref["screen"])
        check(f"{app_id}_opens_with_the_simulator_start_screen", shown == start and not dev.m.asserts,
              f"{sum(a != b for a, b in zip(shown, start))} of 1024 bytes differ, asserts {dev.m.asserts}")
        own(dev, check)
        dev.press("exit", 0.5)
        screen = dev.screen()
        check(f"{app_id}_exit_gives_the_main_screen_back", screen["number"] == 1 and not dev.m.asserts, screen)
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
