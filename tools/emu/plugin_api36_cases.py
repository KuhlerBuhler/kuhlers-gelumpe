"""Emulator cases of plugin API 36: korg.menu.blech.customizations.led.knobLeds is the page KNOB LEDS of the menu BLECH. A plugin
sets it to 0, the five knob LEDs 0 to 4 go out at once while the firmware keeps the brightness it wants, the page shows OFF;
set to 1 they light as the firmware wants again and the page shows ON.

    python3 tools/emu/plugin_api36_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The page itself is measured in docs/messungen/2026-11-12-knopf-leds.md.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks, synthaddr  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

KNOB = "korg.menu.blech.customizations.led.knobLeds"
LED_MANAGER, LED_WANTED = 0xC0345A1C, 0x4E      # + 8 * LED the brightness the firmware wants (menu_cases.knob_leds_cases)
KNOB_PAGE = 8                                    # the ninth page of the group LED

# the test writes `want`; the next tick sets the leaf to it and reads it back into `seen`
PROGRAMS = {
    "knob": f"""let want = -1; let seen = -9; let first = -9;
korg.every(20, () => {{
  if (first == -9) first = {KNOB};
  if (want >= 0) {{ {KNOB} = want; seen = {KNOB}; want = -1; }}
}});""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api36:{name}", "ok": bool(ok), "detail": str(detail)}


class Run:
    """A device booted to the main screen with a card on the adapter, running the program knob."""
    def __init__(self, vsb, flash):
        payload = vsb[0x100:]
        self.synth = synthaddr.is_synth(payload)
        self.build = identify(payload).build
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"]["knob"]
        built = script_hooks.build(self.request["include"], build=self.build)
        wait = 10.0 if self.synth else 2.0        # the synth reaches its main screen after about 8 s
        self.dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=wait)
        self.dev.run(1.0)
        self.at = script_cases.install(self.dev, built, self.request["programs"], ["knob"])["knob"]
        self.dev.run(0.3)

    def vars(self):
        return script_cases.variables(self.dev, self.at, self.program)

    def set(self, value):
        slot = self.program["symbols"]["want"]["slot"]
        self.dev.m.uc.mem_write(self.dev.u32(self.at + 8) + slot * 4, struct.pack("<i", value))
        self.dev.run(0.4)

    def sent(self):
        """The brightness last sent to the panel for the knob LEDs 0 to 4."""
        return [self.dev.m.leds.get(led, 0) for led in range(5)]

    def wanted(self):
        mgr = self.dev.u32(synthaddr.tr(LED_MANAGER) if self.synth else LED_MANAGER)
        return [self.dev.read(mgr + LED_WANTED + 8 * led, 1)[0] for led in range(5)]

    def page(self):
        menu_cases.goto_group(self.dev, menu_cases.GROUP_LED, KNOB_PAGE)
        shown = menu_cases.texts_of(self.dev)
        script_cases.leave_menu(self.dev)
        return shown


def cases(vsb, flash=None):
    """Read 1 at start; set 0: sent [0] * 5 at once, the firmware still wants its values, reads 0, page OFF; set 1: sent the
    firmware's values again (VALUE, LED 0, is left out as in menu_cases: the firmware lights it only while it is turned), page ON."""
    import pad_colors as PC
    menu_cases.for_build(vsb[0x100:])
    r = Run(vsb, flash)
    if r.dev.u32(PC.CODE_AT) == 0xFFFFFFFF:
        return [entry("no_pad_colors", True, f"build {r.build}: the set has no patch pad-colors, no KNOB LEDS")]
    out = []
    stock, first = r.sent(), r.vars()["first"]
    out.append(entry("reads_on_at_start", first == 1 and any(stock[1:]) and not r.dev.m.asserts,
                     f"build {r.build}: read {first}, knob LEDs {stock}, the firmware wants {r.wanted()}"))

    r.set(0)
    off, seen, wanted = r.sent(), r.vars()["seen"], r.wanted()
    out.append(entry("off_at_once", off == [0] * 5 and seen == 0 and wanted[1:] == stock[1:] and not r.dev.m.asserts,
                     f"build {r.build}: read {seen}, sent {off}, the firmware still wants {wanted}"))
    shown = r.page()
    out.append(entry("page_shows_off", shown[:2] == ("KNOB LEDS", "OFF") and not r.dev.m.asserts, f"build {r.build}: page {shown}"))

    r.set(1)
    on, seen = r.sent(), r.vars()["seen"]
    out.append(entry("on_again", on[1:] == stock[1:] and seen == 1 and not r.dev.m.asserts,
                     f"build {r.build}: read {seen}, sent {on}, at start {stock}"))
    shown = r.page()
    out.append(entry("page_shows_on", shown[:2] == ("KNOB LEDS", "ON") and not r.dev.m.asserts, f"build {r.build}: page {shown}"))
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
