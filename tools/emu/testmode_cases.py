# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of the test mode (korg.system.testMode, tools/patch/script_remote.s): the device looks switched off while it
keeps running, so tests on the device need nobody at it.

Switched on over USB (the command word of the keys from the computer, kind 4): the display is off (the controller got 0xAE)
while the firmware keeps drawing into its buffer, which the computer reads; the light pins stay off and every LED is 0, also
while PLAY runs, a knob turns and a plugin sets the light, an LED and korg.ledHold(0); Auto Power Off does not switch the
device off ("4 hours later": the counter is set to 1 s before its end). Switched off, the display, the light and the LEDs
are what a twin device shows that went through the same steps without the test mode, an LED a plugin set meanwhile shows its
value, and Auto Power Off counts again. A plugin only reads the switch; with EXIT held at power-on nothing of it runs.

    tools/emu/.venv/bin/python tools/emu/testmode_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import menu_cases  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
from tools.patch import script_hooks  # noqa: E402

SIGN, SIGN2 = 0x544D4552, 0x32544D52      # "REMT", "RMT2" (remote_sign in script_remote.s)
MARK, KEY, MESSAGE, TEST = 0xA5000000, 1, 3, 4
PLAY, STOP = 0x02, 0x01
DISPLAY = 0xC031B310                      # the firmware's display buffer, 1024 bytes (tools/device/screen_check.py)
APO_TIMER = 0xC033E6B4                    # *APO_TIMER + 0x18: Auto Power Off, 2 ms ticks
APO_TICKS = 7200000
LED_COUNT = 88
KILL = menu_cases.KILL                    # EXIT held at power-on
PROGRAM = """let n = 0;
korg.onEvent("frame", () => {
  n = n + 1;
  if (korg.system.testMode == 1) { korg.backlight(1, 1, 1); korg.led(9, 255); korg.ledHold(0); korg.system.keepAwake(); }
});"""
WRITES = 'korg.onEvent("ready", () => { korg.system.testMode = 1; });'


def entry(name, ok, detail):
    return {"id": f"testmode:{name}", "ok": bool(ok), "detail": str(detail)}


def signature(payload):
    """(command word, message, korg.system.testMode) addresses from the runtime's signature, or None."""
    for code in range(0x150300, 0x170000 - 24, 4):
        a, b, c, d, e = struct.unpack_from("<5I", payload, code)
        if a == SIGN and c == SIGN2:
            return b, d, e
    return None


class Remote:
    """What KORG.exec leaves behind, without the SysEx around it."""

    def __init__(self, dev, payload):
        self.dev = dev
        self.cmd, self.msg, self.flag = signature(payload)

    def send(self, kind, index=0, value=0, wait=0.3):
        self.dev.m.uc.mem_write(self.cmd, struct.pack("<I", MARK | (value & 0xFF) << 16 | index << 8 | kind))
        self.dev.run(wait)

    def test(self, on, wait=0.6):
        self.send(TEST, 0, 1 if on else 0, wait)

    def message(self, data, wait=0.3):
        self.dev.m.uc.mem_write(self.msg, bytes(data).ljust(8, b"\0"))
        self.send(MESSAGE, wait=wait)


def looks(dev):
    """What someone in front of the device sees: lit LCD pixels, the share of time each light pin is on, LEDs above 0."""
    pins = menu_cases.duty(dev, 0.3)[0]
    return {"lcd": sum(1 for b in dev.m.shown() if b), "light": pins, "leds": sorted(i for i, v in dev.m.leds.items() if v),
            "buffer": sum(1 for b in dev.read(DISPLAY, 1024) if b)}


def dark(seen):
    return seen["lcd"] == 0 and max(seen["light"].values()) == 0 and not seen["leds"] and seen["buffer"] > 0


def apo(dev):
    return struct.unpack("<i", dev.read(dev.u32(APO_TIMER) + 0x18, 4))[0]


def set_apo(dev, ticks):
    dev.m.uc.mem_write(dev.a(dev.u32(APO_TIMER)) + 0x18, struct.pack("<i", ticks))


def steps(remote):
    """What a test does on the device: PLAY, a knob, STOP."""
    remote.send(KEY, PLAY, wait=0.5)
    remote.message([2, 0, 0, 40, 0], wait=0.3)
    remote.send(KEY, STOP, wait=0.5)


def boot(payload, flash):
    dev = menu_cases.boot(payload, flash, adapter=True, seconds=2.0)
    menu_cases.watch_pins(dev)
    return dev


def usb_cases(payload, flash):
    out = []
    twin = boot(payload, flash)
    steps(Remote(twin, payload))
    twin.run(0.6)
    want = looks(twin)

    dev = boot(payload, flash)
    remote = Remote(dev, payload)
    before = looks(dev)
    remote.test(True)
    off = looks(dev)
    out.append(entry("usb_dark", dark(off) and dev.read(remote.flag, 1)[0] == 1 and not dev.m.lcd_on,
                     f"before {before}, test mode {off}"))
    steps(remote)
    held = looks(dev)
    out.append(entry("stays_dark", dark(held), f"after PLAY, a knob and STOP {held}"))
    remote.test(False)
    back = looks(dev)
    out.append(entry("usb_back", back == want and dev.m.lcd_on and dev.read(remote.flag, 1)[0] == 0,
                     f"after the test mode {back}, without it {want}"))
    out.append(entry("no_assert", not dev.m.asserts and not twin.m.asserts, f"asserts {dev.m.asserts[:2]} {twin.m.asserts[:2]}"))
    return out


def awake_cases(payload, flash):
    out = []
    plain = boot(payload, flash)
    set_apo(plain, 500)
    plain.run(2.5)
    dev = boot(payload, flash)
    remote = Remote(dev, payload)
    remote.test(True)
    set_apo(dev, 500)
    dev.run(2.5)
    awake = dev.m.powered, apo(dev)
    remote.test(False)
    first = apo(dev)
    dev.run(0.5)
    counts = first, apo(dev)
    out.append(entry("stays_on", not plain.m.powered and awake[0] and awake[1] > APO_TICKS - 1000 and counts[1] < counts[0],
                     f"without the test mode powered {plain.m.powered}; with it powered {awake[0]}, counter {awake[1]}; after it {counts}"))
    return out


def compiled():
    code = """
import { asmInclude } from "./src/script/arm-tables.mjs";
import { compile } from "./src/script/compiler.mjs";
const r = compile(process.argv[1], { name: "testmode" });
if (!r.ok) { console.error(r.errors.map(e => e.message).join("; ")); process.exit(1); }
const w = compile(process.argv[2], { name: "writes" });
process.stdout.write(JSON.stringify({ include: asmInclude(), programs: { testmode: { blob: Buffer.from(r.blob).toString("hex") } },
  refused: w.ok ? null : w.errors.map(e => e.message).join("; ") }));
"""
    result = subprocess.run(["node", "--input-type=module", "-e", code, PROGRAM, WRITES], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def plugin_cases(payload, flash):
    request = compiled()
    built = script_hooks.build(request["include"], build=identify(payload).build)
    dev = boot(payload, flash)
    remote = Remote(dev, payload)
    script_cases.install(dev, built, request["programs"], ["testmode"])
    remote.test(True)
    off = looks(dev)
    remote.test(False)
    back = looks(dev)
    return [entry("plugin_reads_only", request["refused"] and "testMode" in request["refused"], f"a plugin that sets it: {request['refused']}"),
            entry("plugin_dark", dark(off), f"while the plugin sets the light, LED 9 and korg.ledHold(0) every frame {off}"),
            entry("plugin_back", back["lcd"] > 0 and min(back["light"].values()) == 1.0 and 9 in back["leds"] and not dev.m.asserts,
                  f"after the test mode, with LED 9 as the plugin set it {back}")]


def exit_cases(payload, flash):
    """EXIT held at power-on: the runtime is off, the command words stay where they are, the device stays as it is."""
    dev = menu_cases.boot(payload, flash, held=KILL, adapter=True, seconds=2.0)
    menu_cases.watch_pins(dev)
    remote = Remote(dev, payload)
    before, done = looks(dev), dev.u32(remote.cmd + 8)
    remote.test(True)
    remote.send(KEY, 0x09, wait=0.5)
    after = looks(dev)
    return [entry("exit_at_power_on", after["lcd"] > 0 and after["light"] == before["light"] and dev.m.lcd_on and dev.u32(remote.cmd + 8) == done
                  and dev.read(remote.flag, 1)[0] == 0 and dev.m.screen() == 1, f"before {before}, after test mode and MENU {after}")]


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    if not signature(payload):
        return [entry("present", False, "no runtime with the test mode in this copy")]
    return usb_cases(payload, flash) + awake_cases(payload, flash) + plugin_cases(payload, flash) + exit_cases(payload, flash)


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
