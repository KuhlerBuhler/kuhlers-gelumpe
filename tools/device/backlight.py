"""Colour the display light of the own Electribe through the firmware's own GPIO function.

The light is three pins, GP6P3/4/5 for red, green and blue (Freetribe
dev_lcd_set_backlight); the firmware switches all three on at start
(docs/messungen/2026-10-10-startphase.md) by calling 0xC0016BB4(0x01E26000,
on, 3, mask). This stub makes the same calls, with bank pair 3 fixed in the
code and only the masks 0x08, 0x10 and 0x20. RAM only, as led_show.py: the
stub goes to 0xC1000000, runs through Hacktribe's execute 0x57, and the
original bytes are put back. Stops before writing if the code it calls is
not the measured build. Nothing is stored; a restart brings back white.

    python3 backlight.py --emu VSB --rgb 1,0,0     # against the local emulator
    python3 backlight.py --dry-run                 # on the laptop: checks only
    python3 backlight.py --rgb 0,0,1               # on the laptop: blue
    python3 backlight.py --cycle                   # all seven colours, then white again
    python3 backlight.py --party --seconds 30      # rainbow in a loop, 0.35 s per colour, then white

Every program goes up in one write before the first colour: a write makes
the firmware show "Working..." for a moment, an execute only redraws the
same screen (measured in the emulator). The screen cannot be blanked this
way, the redraw after the execute puts it back.
"""
import argparse
import hashlib
import struct
import time

from led_show import Device, ICACHE_INVALIDATE, emulator_ask, mido_ask

STUB_AT = 0xC1000000
GPIO_BASE = 0x01E26000
GPIO_WRITE = 0xC0016BB4                 # (base, on, pair, mask): set or clear pins of one bank pair
MASKS = (0x08, 0x10, 0x20)              # GP6P3 red, GP6P4 green, GP6P5 blue
SLOT = 0x40                             # one colour program per slot

EXPECTED = {                            # sha256 of the code the run relies on (own VSB)
    (0xC0016BB4, 0x64): "826d2f44786a37997f7f68f3e360842ce697c2d409e6a05fc9b0140fe174055f",
    (0xC0016ABC, 0x54): "d19d982a1c624bf86579786a23254deaa03835afbb2415b59f73a51e4fa62a01",
    (0xC0016B10, 0x54): "2cb8c377cd1a5beb3f51358f1d9589b0a2342f98430d864e870c3362d8e5c682",
    (0xC00016A4, 0x34): "f33f00d1ca5392c857af29991ed0e4e10340bb4675df9e2f030af0caf730bd6a",
}

CYCLE = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (0, 1, 1), (1, 0, 1), (1, 1, 1)]
RAINBOW = [(1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1), (1, 0, 1)]
WHITE = (1, 1, 1)


def stub(rgb):
    words = [
        0xE92D4010,              # push {r4, lr}
        0xE28F402C,              # add r4, pc, #44        -> table
        0xE4D41001,              # loop: ldrb r1, [r4], #1 (on, or 0xFF to end)
        0xE35100FF,              # cmp r1, #0xff
        0x0A000005,              # beq done
        0xE4D43001,              # ldrb r3, [r4], #1     (mask)
        0xE59F0010,              # ldr r0, =GPIO_BASE
        0xE3A02003,              # mov r2, #3            (bank pair 6/7, fixed)
        0xE59FC00C,              # ldr r12, =GPIO_WRITE
        0xE12FFF3C,              # blx r12
        0xEAFFFFF6,              # b loop
        0xE8BD8010,              # done: pop {r4, pc}
        GPIO_BASE, GPIO_WRITE,
    ]
    table = b"".join(bytes([1 if on else 0, mask]) for on, mask in zip(rgb, MASKS)) + b"\xff"
    return b"".join(struct.pack("<I", w) for w in words) + table


def programs(colours):
    """One colour program per slot."""
    return b"".join(stub(rgb).ljust(SLOT, b"\0") for rgb in colours)


def run(dev, dry, colours, hold, loop_seconds=0.0):
    for (addr, length), digest in EXPECTED.items():
        if hashlib.sha256(dev.read(addr, length)).hexdigest() != digest:
            raise SystemExit(f"code at {addr:#x} differs from the measured build; nothing written")
    blob = programs(colours)
    original = dev.read(STUB_AT, len(blob))
    print(f"checks passed: firmware code matches; {len(colours)} colour(s)")
    if dry:
        print("dry run: nothing written")
        return
    try:
        dev.write(STUB_AT, blob)
        time.sleep(1.5)                          # the "Working..." of this one write passes
        dev.execute(ICACHE_INVALIDATE)
        if loop_seconds:
            # The last program is white: loop over the others, end on white.
            shown, deadline = 0, time.monotonic() + loop_seconds
            while time.monotonic() < deadline:
                dev.execute(STUB_AT + (shown % (len(colours) - 1)) * SLOT)
                shown += 1
                time.sleep(hold)
            dev.execute(STUB_AT + (len(colours) - 1) * SLOT)
            print(f"party: {shown} colour changes, back to white")
        else:
            for n, rgb in enumerate(colours):
                dev.execute(STUB_AT + n * SLOT)
                print("light", "".join(c for c, on in zip("RGB", rgb) if on) or "off")
                time.sleep(hold)
    finally:
        time.sleep(0.2)
        dev.write(STUB_AT, original)
        print("original bytes at the stub address restored")


def colour(text):
    parts = tuple(int(x) for x in text.split(","))
    if len(parts) != 3 or any(p not in (0, 1) for p in parts):
        raise argparse.ArgumentTypeError("three values 0 or 1, e.g. 1,0,1")
    return parts


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--emu", metavar="VSB")
    p.add_argument("--dry-run", action="store_true")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--rgb", type=colour, default=(0, 0, 1), help="red,green,blue as 0 or 1 (default blue)")
    g.add_argument("--cycle", action="store_true", help="step through the seven colours, end on white")
    g.add_argument("--party", action="store_true", help="rainbow in a loop for --seconds, end on white")
    p.add_argument("--hold", type=float, help="seconds per colour (default 1.5, party 0.35)")
    p.add_argument("--seconds", type=float, default=20.0, help="how long the party runs")
    a = p.parse_args()
    colours = RAINBOW + [WHITE] if a.party else CYCLE if a.cycle else [a.rgb]
    hold = a.hold if a.hold is not None else 0.35 if a.party else 1.5
    loop = a.seconds if a.party else 0.0
    if a.emu:
        ask, m = emulator_ask(a.emu)
        run(Device(ask), a.dry_run, colours, 0, 0.5 if a.party else 0.0)
        bits = m.gpio.get(3, 0)
        print("emulator GP6P3..5 (R,G,B):", [(bits >> n) & 1 for n in (3, 4, 5)],
              "other pair-3 bits (0x800 the firmware toggles itself):", hex(bits & ~0x38), "asserts:", m.asserts, "powered:", m.powered)
    else:
        run(Device(mido_ask()), a.dry_run, colours, hold, loop)


if __name__ == "__main__":
    main()
