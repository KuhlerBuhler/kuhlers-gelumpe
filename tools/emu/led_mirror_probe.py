# SPDX-License-Identifier: GPL-2.0-only
"""Do the emulator's LEDs show only what the firmware sent? docs/messungen/2026-10-31-emulator-leds.md.

    tools/emu/.venv/bin/python tools/emu/led_mirror_probe.py ORIGINAL.VSB [MORE.VSB ...]

Boots each firmware for 6 s on mains power, then presses pad 2 and lets it go. After every step the LEDs the
emulator hands to the page (Machine.leds) are compared with the last panel message `00 LED value` the firmware
sent for each LED, and the pads that are lit are printed. Prints numbers and addresses, never firmware bytes.
The exit status is 1 when one comparison fails.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).parent))
from splash_cases import Dev  # noqa: E402


def sent(m):
    """LED number to the value of the last `00 LED value` the firmware put on UART0."""
    out = {}
    for msg in m.panel_log:
        if msg[0] == 0x00:
            out[msg[1]] = msg[2]
    return out


def pads(m):
    """Pad 1 to 16 to (red, blue), only the lit ones."""
    out = {}
    for n in range(16):
        red, blue = m.leds.get(0x2C + 2 * n, 0), m.leds.get(0x2D + 2 * n, 0)
        if red or blue:
            out[n + 1] = (red, blue)
    return out


def main(files):
    ok = True
    for f in files:
        d = Dev(Path(f).read_bytes()[0x100:], None, adapter=True)
        d.run(6.0)
        m = d.m
        kinds = sorted({msg[0] for msg in m.panel_log})
        print(f"{Path(f).name}: build {m.profile.build}, {len(m.panel_log)} panel messages, kinds {[hex(k) for k in kinds]}")
        for step, act in (("idle", None), ("pad 2 down", [4, 1, 0, 100, 1]), ("pad 2 up", [4, 1, 0, 0, 0])):
            if act:
                m.send(act)
                d.run(0.3)
            same = sent(m) == m.leds
            ok &= same
            print(f"  {step:10} {'ok' if same else 'FAIL'}  pads {pads(m)}  lit {sorted(hex(k) for k, v in m.leds.items() if v)}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
