"""Emulator cases of plugin API 18: korg.viewedPattern is the pattern the display shows (the wheel's browse and a confirmed next
pattern move it away from the playing one), korg.nextPattern the next pattern the pattern switch has confirmed, -1 when none.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_api18_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import pswitch_cases as ps  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

PROGRAM = """let viewed = -9; let next = -9; let sel = -9;
korg.onEvent("frame", () => { viewed = korg.viewedPattern; next = korg.nextPattern; sel = korg.selectedPattern; });"""


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled({"api18": PROGRAM})


def entry(name, ok, detail):
    return {"id": f"plugin_api18:{name}", "ok": bool(ok), "detail": str(detail)}


class Run:
    """A device of the pattern switch cases with the plugin installed; look() is what the plugin read in its last frame."""

    def __init__(self, vsb, flash, built, programs, program):
        self.box = ps.Box(vsb[0x100:], flash)
        self.program = program
        self.at = edit.script_cases.install(self.box.dev, built, programs, ["api18"])["api18"]

    def look(self):
        self.box.run(0.1)
        v = edit.script_cases.variables(self.box.dev, self.at, self.program)
        return v["viewed"], v["next"], v["sel"]


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    ps.for_build(payload)
    build = identify(payload).build
    request = edit.compiled({"api18": PROGRAM})
    built = script_hooks.build(request["include"], build=build)
    program = request["programs"]["api18"]
    mk = lambda: Run(vsb, flash, built, request["programs"], program)  # noqa: E731
    out = []

    r = mk()
    b = r.box
    ps.play(b)
    out.append(entry("idle", r.look()[:2] == (0, -1) and not b.m.asserts, f"playing pattern 0: viewed, next, selected {r.look()}"))
    b.turn(3)
    seen = r.look()
    out.append(entry("browse_moves_the_view_not_the_next", seen == (3, -1, 3) and b.running() == 0 and not b.m.asserts,
                     f"wheel +3 while playing, not confirmed: viewed, next, selected {seen}, playing {b.running()}"))
    b.key("menu")
    seen = r.look()
    out.append(entry("confirm_sets_next", seen[:2] == (3, 3) and b.running() == 0 and not b.m.asserts, f"MENU: viewed, next {seen[:2]}, playing {b.running()}"))
    b.turn(2)
    seen = r.look()
    out.append(entry("browse_after_confirm", seen[:2] == (5, 3) and b.running() == 0 and not b.m.asserts,
                     f"wheel +2 after the confirmation: viewed, next {seen[:2]} (the view moves on, the confirmed one stays)"))
    b.key("exit")
    first = r.look()[:2]
    b.key("exit")
    second = r.look()[:2]
    out.append(entry("exit_steps_back", first == (3, 3) and second == (0, -1) and not b.m.asserts, f"EXIT: {first}, EXIT again: {second}"))

    r = mk()
    b = r.box
    ps.play(b)
    b.turn(2)
    b.key("menu")
    b.until_change()
    seen = r.look()
    out.append(entry("switch_clears_next", seen[:2] == (2, -1) and b.running() == 2 and not b.m.asserts,
                     f"after the sequence end the confirmed 2 plays: viewed, next {seen[:2]}, playing {b.running()}"))

    r = mk()
    b = r.box
    b.turn(5)
    seen = r.look()
    out.append(entry("stopped_view_follows_the_load", seen[:2] == (5, -1) and b.running() == 5 and not b.m.asserts,
                     f"stopped, wheel +5 loads at once: viewed, next {seen[:2]}, playing {b.running()}"))

    r = mk()
    b = r.box
    b.set_setting(0)
    ps.play(b)
    b.turn(3)
    seen = r.look()
    out.append(entry("firmware_queue_is_not_a_confirmation", seen == (0, -1, 3) and b.pending() == 1 and not b.m.asserts,
                     f"PATTERN CONFIRM off (the firmware's own queue): viewed, next, selected {seen}, pending flag {b.pending()}"))
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
