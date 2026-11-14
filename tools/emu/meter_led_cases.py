"""Emulator cases of the meter LEDs (meter_dedupe_hook, tools/patch/script_menu.s): the LED manager's send function 0xC00875F4
sends the twelve meter LEDs (0x4C to 0x57) only when brightness or mode changed. Idle, the panel gets no meter message; a changed
brightness goes out once, an equal one not again; a forced send (lock released, test mode, korg.led refresh) always goes out.
With EXIT held at power-on the firmware sends as before, about 300 meter messages a second.

    python3 tools/emu/meter_led_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

Measured in docs/messungen/2026-11-14-energie-befunde.md ("Pegel-LEDs nur bei Änderung").
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import menu_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

LED_MANAGER, LED_SEND = 0xC0345A1C, 0xC00875F4   # (manager, led, force)
METER_UPDATE = 0xC0088284                        # the firmware's meter, every 40 ms; paused while a case calls the send function
METER = range(0x4C, 0x58)
WANTED = 0x4E                                    # + 8 * LED: the brightness the firmware wants, mode behind it
IDLE_MAX = 5                                     # meter messages a second the idle device may still send (before: about 300)


def entry(name, ok, detail):
    return {"id": f"meter_led:{name}", "ok": bool(ok), "detail": str(detail)}


class Run:
    """A device booted to the main screen on mains power, counting the panel's messages to the meter LEDs."""
    def __init__(self, payload, flash, held=0):
        self.build = identify(payload).build
        wait = 10.0 if self.build == "synth" else 2.0    # the synth reaches its main screen after about 8 s
        self.dev = menu_cases.boot(payload, flash, held=held, files=menu_cases.CARD_FOLDER, adapter=True, seconds=wait)
        self.sent = []
        panel = self.dev.m.panel

        def watch(msg):
            if msg[0] == 0 and msg[1] in METER:
                self.sent.append((msg[1], msg[2]))
            return panel(msg)
        self.dev.m.panel = watch
        self.dev.run(0.5)

    def idle(self, seconds=1.0):
        """Meter messages a second while nothing happens."""
        self.sent.clear()
        self.dev.run(seconds)
        return len(self.sent) / seconds

    def pause_meter(self):
        """The firmware's meter returns at once from now on, so it writes no level into the table while a case sends."""
        import unicorn
        uc, arm = self.dev.m.uc, self.dev.m.A
        uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, *_: u.reg_write(arm.UC_ARM_REG_PC, u.reg_read(arm.UC_ARM_REG_LR)),
                    begin=self.dev.a(METER_UPDATE), end=self.dev.a(METER_UPDATE))
        uc.ctl_flush_tb()

    def send(self, led, force, brightness=None):
        """One call of the send function from the screen tick, the brightness written into the manager's table first; returns
        the meter messages that reached the panel in the 50 ms after it."""
        manager = self.dev.u32(LED_MANAGER)
        if brightness is not None:
            self.dev.m.uc.mem_write(manager + WANTED + 8 * led, bytes([brightness]))
        self.sent.clear()
        self.dev.call(LED_SEND, manager, led, force)
        self.dev.run(0.05)
        return list(self.sent)


def cases(vsb, flash=None):
    """Idle quiet; a new brightness goes out once, the same not again; forced goes out with the same value; another meter LED
    keeps its own value; EXIT at power-on sends as Korg's firmware does."""
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    out = []
    r = Run(payload, flash)
    rate = r.idle()
    out.append(entry("idle_quiet", rate <= IDLE_MAX and not r.dev.m.asserts,
                     f"build {r.build}: {rate:.1f} meter messages a second idle (at most {IDLE_MAX}, before about 300)"))
    r.pause_meter()
    led = 0x50
    first, again = r.send(led, 0, 200), r.send(led, 0)
    out.append(entry("change_once", first == [(led, 200)] and again == [] and not r.dev.m.asserts,
                     f"build {r.build}: brightness 200 sent {first}, the same again sent {again}"))
    forced = r.send(led, 1)
    out.append(entry("forced_resends", forced == [(led, 200)] and not r.dev.m.asserts,
                     f"build {r.build}: forced with the same value sent {forced}"))
    one, other = r.send(led, 0, 1), r.send(0x51, 0, 200)
    out.append(entry("brightness_one_and_neighbour", one == [(led, 1)] and other == [(0x51, 200)] and not r.dev.m.asserts,
                     f"build {r.build}: brightness 1 sent {one}, LED 0x51 with 200 sent {other}"))
    stock = Run(payload, flash, held=menu_cases.KILL)
    rate = stock.idle()
    out.append(entry("exit_at_power_on_as_before", rate > 100 and not stock.dev.m.asserts,
                     f"build {stock.build}: EXIT held at power-on, {rate:.1f} meter messages a second idle"))
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
