"""Emulator cases of plugin API 34: korg.system.power follows panel message 7 (1 adapter, 0 battery) as the firmware's power
model keeps it, korg.system.battery reads the level of the firmware's battery model, korg.read.led the brightness the firmware
last sent for a LED.

    python3 tools/emu/plugin_api34_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api34-system.md.
"""
import argparse
import json
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

BATTERY_MODEL, LEVEL_AT = 0xC03405C8, 0x328
LED_MANAGER, LED_COPY = 0xC0345A1C, 0x88C
LEDS = (0x00, 0x01, 0x02, 0x09, 0x0C, 0x15, 0x16, 0x1B)
KEY_PLAY = 0x02

PROGRAMS = {
    "power": """let p = -9; let b = -9;
korg.every(20, () => { p = korg.system.power; b = korg.system.battery; });""",
    "leds": "let " + ", ".join(f"l{n} = -9" for n in LEDS) + ";\nkorg.every(20, () => { "
            + " ".join(f"l{n} = korg.read.led({n});" for n in LEDS) + " });",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api34:{name}", "ok": bool(ok), "detail": str(detail)}


class Run:
    """A device booted to the main screen with a card, on the adapter or on battery, that runs one program."""
    def __init__(self, vsb, flash, name, adapter):
        payload = vsb[0x100:]
        self.synth = synthaddr.is_synth(payload)
        self.build = identify(payload).build
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"][name]
        built = script_hooks.build(self.request["include"], build=self.build)
        self.dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=adapter, seconds=2.0)
        self.dev.run(1.0)
        self.at = script_cases.install(self.dev, built, self.request["programs"], [name])[name]
        self.dev.run(0.3)

    def vars(self):
        return script_cases.variables(self.dev, self.at, self.program)

    def copy(self, led):
        """Brightness byte of the LED manager's copy of what it last sent for `led`."""
        mgr = self.dev.u32(synthaddr.tr(LED_MANAGER) if self.synth else LED_MANAGER)
        return self.dev.m.uc.mem_read(mgr + LED_COPY + 8 * led + 2, 1)[0]

    def model(self):
        return self.dev.u32(synthaddr.tr(BATTERY_MODEL) if self.synth else BATTERY_MODEL)


def power_cases(vsb, flash):
    """Booted on battery power reads 0; panel message 7 with 1 makes it 1, with 0 again 0 (the plug symbol the firmware draws)."""
    r = Run(vsb, flash, "power", adapter=False)
    seen = [r.vars()["p"]]
    for on in (1, 0):
        r.dev.m.send([0x07, on, 0, 0, 0])
        r.dev.run(0.3)
        seen.append(r.vars()["p"])
    return [entry("power_follows_message_7", seen == [0, 1, 0] and not r.dev.m.asserts, f"build {r.build}: battery, adapter, battery {seen}")]


def battery_cases(vsb, flash):
    """The level the battery model holds after boot (the emulator sends no battery reading), then a level written into the model."""
    r = Run(vsb, flash, "power", adapter=False)
    model = r.model()
    first, raw = r.vars()["b"], r.dev.u32(model + LEVEL_AT)
    r.dev.m.uc.mem_write(model + LEVEL_AT, (2).to_bytes(4, "little"))
    r.dev.run(0.2)
    second = r.vars()["b"]
    ok = first == raw and 0 <= first <= 4 and second == 2 and not r.dev.m.asserts
    return [entry("battery_reads_the_model", ok, f"build {r.build}: after boot {first} (model {raw}), after writing 2 {second}")]


def sent(m):
    """LED number to the value of the last `00 LED value` the firmware put on the panel line."""
    out = {}
    for msg in m.panel_log:
        if msg[0] == 0x00:
            out[msg[1]] = msg[2]
    return out


def led_cases(vsb, flash):
    """korg.read.led gives the LED manager's copy for each LED, at rest and after PLAY lit its LEDs. The copy equals the last
    panel message for every LED but VALUE (0): the patch pad-colors sends that one as 255 after start past the manager."""
    r = Run(vsb, flash, "leds", adapter=True)
    out = []
    for step in ("idle", "play"):
        if step == "play":
            r.dev.m.send([0x00, KEY_PLAY, 1, 0, 0])
            r.dev.run(0.1)
            r.dev.m.send([0x00, KEY_PLAY, 0, 0, 0])
            r.dev.run(0.4)
        v, last = r.vars(), sent(r.dev.m)
        got = {n: v[f"l{n}"] for n in LEDS}
        copy = {n: r.copy(n) for n in LEDS}
        want = {n: last.get(n, 0) for n in LEDS}
        ok = got == copy and all(got[n] == want[n] for n in LEDS if n != 0) and not r.dev.m.asserts
        out.append(entry(f"read_led_{step}", ok, f"build {r.build}: read {got}, copy {copy}, sent {want}"))
    return out


def cases(vsb, flash=None):
    return power_cases(vsb, flash) + battery_cases(vsb, flash) + led_cases(vsb, flash)


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
