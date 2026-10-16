"""Light every LED of the own Electribe one after the other, to see which are fitted.

RAM only, through the same stub as led_show.py: each step switches the previous
LED off and the next one on, then waits. Before anything is written it prints
fingerprints of the code places our patches change, so the running firmware
can be named, and it stops if the LED code is not the measured build. The
original bytes at the stub address are put back at the end.

    python3 led_inventory.py --identify          # only read and print the fingerprints
    python3 led_inventory.py --hold 1.5          # all LEDs 0x00..0x57, one at a time
    python3 led_inventory.py --only 0-4          # just the five knob LEDs
    python3 led_inventory.py --emu VSB --hold 0  # against the local emulator
"""
import argparse
import hashlib
import struct
import time

from led_show import (Device, EXPECTED, ICACHE_INVALIDATE, PANEL_PTR, STUB_AT, CHUNK,
                      emulator_ask, mido_ask, show_frame, stub)

LAST = 0x57

NAMES = {
    0x00: "Regler VALUE", 0x01: "Regler SAMPLE/OSC", 0x02: "Regler CUTOFF",
    0x03: "Regler MOD TYPE", 0x04: "Regler IFX TYPE",
    0x05: "Edit links", 0x06: "Edit rechts", 0x07: "MENU", 0x08: "EXIT", 0x09: "PLAY",
    0x0a: "SHIFT", 0x0b: "WRITE", 0x0c: "LPF", 0x0d: "HPF", 0x0e: "BPF", 0x0f: "MFX SEND",
    0x10: "AMP EG", 0x11: "IFX ON", 0x12: "REC", 0x13: "STOP", 0x14: "TAP", 0x15: "PLAY blau (2. LED)", 0x16: "Taste 1 blau", 0x17: "Taste 2 blau",
    0x18: "Taste 3 blau", 0x19: "Taste 4 blau",
    0x1a: "GATE ARP", 0x1b: "TOUCH SCALE", 0x1c: "MASTER FX", 0x1d: "MFX HOLD",
    0x1e: "Part links", 0x1f: "Part rechts", 0x20: "PART MUTE", 0x21: "PART ERASE",
    0x22: "TRIGGER", 0x23: "SEQUENCER", 0x24: "KEYBOARD", 0x25: "CHORD",
    0x26: "STEP JUMP", 0x27: "PATTERN SET", 0x28: "Taste 1 rot", 0x29: "Taste 2 rot",
    0x2a: "Taste 3 rot", 0x2b: "Taste 4 rot",
    **{0x2c + 2 * n: f"Pad {n + 1} rot" for n in range(16)},
    **{0x2d + 2 * n: f"Pad {n + 1} blau" for n in range(16)},
    0x4c: "RGB 2 rot", 0x4d: "RGB 2 grün", 0x4e: "RGB 2 blau",
    0x4f: "RGB 3 rot", 0x50: "RGB 3 grün", 0x51: "RGB 3 blau",
    0x52: "RGB 0 rot", 0x53: "RGB 0 grün", 0x54: "RGB 0 blau",
    0x55: "RGB 1 rot", 0x56: "RGB 1 grün", 0x57: "RGB 1 blau",
}

# LEDs the firmware keeps lit on the main screen when stopped (emulator,
# SYSTEM-ringtest.VSB with the own flash, 2026-10-13). These blink off during
# their step and come back on; all others blink on and go back off.
DEFAULT_ON = {0x01, 0x02, 0x03, 0x04, 0x0c, 0x0f, 0x11, 0x16, 0x1b, 0x22, 0x28, 0x2d}

# Places our code patches change: the MFX 2 key hook, the splash editor start
# hook and the start image. Their hashes name the firmware on the device.
FINGERPRINTS = {"MFX 2 Haken": (0xC00700D8, 16), "Startbild-Haken": (0xC002ADAC, 4),
                "Startbild": (0xC00F9854, 1024)}


def identify(dev):
    for name, (addr, length) in FINGERPRINTS.items():
        print(f"{name:16} {addr:#x} {hashlib.sha256(dev.read(addr, length)).hexdigest()[:16]}")


def span(text):
    lo, _, hi = text.partition("-")
    return range(int(lo, 0), int(hi or lo, 0) + 1)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--identify", action="store_true", help="read fingerprints only, write nothing")
    p.add_argument("--hold", type=float, default=1.5, help="seconds per LED")
    p.add_argument("--only", type=span, default=range(0, LAST + 1), help="LED numbers, e.g. 0-4 or 0x2c-0x4b")
    p.add_argument("--emu", metavar="VSB")
    a = p.parse_args()
    m = None
    if a.emu:
        ask, m = emulator_ask(a.emu)
        dev = Device(ask)
    else:
        dev = Device(mido_ask())
    identify(dev)
    if a.identify:
        return
    for (addr, length), digest in EXPECTED.items():
        if hashlib.sha256(dev.read(addr, length)).hexdigest() != digest:
            raise SystemExit(f"code at {addr:#x} differs from the measured build; nothing written")
    panel = struct.unpack("<I", dev.read(PANEL_PTR, 4))[0]
    if not 0xC0000000 <= panel < 0xC4000000 or dev.read(panel + 4, 1) != b"\0":
        raise SystemExit(f"panel object {panel:#x} not ready; nothing written")
    original = dev.read(STUB_AT, len(stub([(0, 0)] * CHUNK)))
    rest = lambda led: 255 if led in DEFAULT_ON else 0
    previous = None
    try:
        dev.execute(ICACHE_INVALIDATE)
        for led in a.only:
            pairs = ([(previous, rest(previous))] if previous is not None else []) + [(led, 255 - rest(led))]
            show_frame(dev, pairs)
            print(f"{led:#04x} {NAMES.get(led, 'unbekannt')}{' (sonst an, jetzt aus)' if led in DEFAULT_ON else ''}", flush=True)
            previous = led
            time.sleep(a.hold)
        if previous is not None:
            show_frame(dev, [(previous, rest(previous))])
    finally:
        time.sleep(0.2)
        dev.write(STUB_AT, original)
        print("original bytes at the stub address restored")
        if m is not None:
            m.run_until(m.time_ns / 1e9 + 0.5)
            print("emulator LEDs still on:", {hex(k): v for k, v in sorted(m.leds.items()) if v}, "asserts:", m.asserts)


if __name__ == "__main__":
    main()
