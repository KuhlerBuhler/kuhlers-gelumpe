"""Press keys and turn the main dial of an Electribe with the BLECH runtime from a computer over USB, and read back where it is.

RAM only: a 76-byte stub (src/remote.mjs) goes to 0xC1000000, runs once per step through Hacktribe's execute command
0x57 and leaves a command word for the runtime's frame hook (tools/patch/script_remote.s); the original bytes are put
back at the end. Stops before anything is written when the runtime's signature or the cache routine is not found.

    python3 remote_press.py --emu VSB menu edit_next +1 exit     # against the local emulator
    python3 remote_press.py --dry-run menu                       # device on USB: checks only, writes nothing
    python3 remote_press.py menu edit_next +1 +1 exit            # device on USB: the steps, then where it is
    python3 remote_press.py --screen                             # where it is and the display, nothing written

A step is a key name (data/panel.mjs, with "_" for camel case: edit_next is editRight) or a signed number of dial clicks.
"""
import argparse
import hashlib
import re
import struct
import sys
from pathlib import Path

from led_show import Device, emulator_ask, mido_ask, ICACHE_INVALIDATE, EXPECTED as LED_EXPECTED
from screen_check import MANAGER_PTR, EDIT_PTR, PATTERN_PTR, DISPLAY, state

STUB_AT = 0xC1000000
CODE = (0xC018D000, 0xC018FF00)          # the runtime's second code area, where its signature lies
SIGN = 0x544D4552                        # "REMT", then the address of the command word
MARK, KEY, ENCODER = 0xA5000000, 1, 2
OS_WAIT = 0xC0000B78
ICACHE = (ICACHE_INVALIDATE, 0x34)
ALIASES = {"edit_next": "editRight", "edit_prev": "editLeft", "part_next": "partInc", "part_prev": "partDec"}


def keys():
    text = (Path(__file__).resolve().parents[2] / "data" / "panel.mjs").read_text()
    return {name: int(index, 16) for name, index in re.findall(r'button\("(\w+)", "[^"]*", (0x[0-9a-f]+)', text)}


def stub(mailbox, word):
    """The same words as stub() in src/remote.mjs."""
    words = [0xE92D4070, 0xE59F4034, 0xE5945008, 0xE59F0030, 0xE5840000, 0xE3A06032, 0xE3A0000A, 0xE59FC024,
             0xE12FFF3C, 0xE5940008, 0xE1500005, 0x1A000001, 0xE2566001, 0x1AFFFFF7, 0xE3A00001, 0xE8BD8070,
             mailbox, word, OS_WAIT]
    return b"".join(struct.pack("<I", w) for w in words)


def command(step, names):
    if re.fullmatch(r"[+-]\d+", step):
        return MARK | (int(step) & 0xFF) << 16 | ENCODER, f"Rad {step}"
    name = ALIASES.get(step, step)
    if name not in names:
        raise SystemExit(f"unknown key {step!r}; keys: {', '.join(sorted(names))}")
    return MARK | names[name] << 8 | KEY, name


def mailbox_of(dev):
    code = b"".join(dev.read(at, min(0x1000, CODE[1] - at)) for at in range(CODE[0], CODE[1], 0x1000))
    at = next((i for i in range(0, len(code) - 8, 4) if struct.unpack_from("<I", code, i)[0] == SIGN), None)
    return None if at is None else struct.unpack_from("<I", code, at + 4)[0]


def where(dev):
    u32 = lambda addr: struct.unpack("<I", dev.read(addr, 4))[0]
    found = {"manager": u32(MANAGER_PTR), "edit": u32(EDIT_PTR), "pattern": u32(PATTERN_PTR)}
    return state(dev.read, found)


def display(dev):
    img = dev.read(DISPLAY, 1024)
    return "\n".join("".join("#" if (img[(y >> 3) * 128 + x] >> (y & 7)) & 1 else " " for x in range(128)).rstrip()
                     for y in range(0, 64, 2))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--emu", metavar="VSB")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--screen", action="store_true", help="print the display after the steps")
    p.add_argument("steps", nargs="*")
    a = p.parse_args()
    dev = Device(emulator_ask(a.emu)[0] if a.emu else mido_ask())
    names = keys()
    steps = [command(s, names) for s in a.steps]
    print("vorher:", where(dev))
    if steps:
        if hashlib.sha256(dev.read(*ICACHE)).hexdigest() != LED_EXPECTED[ICACHE]:
            raise SystemExit("the cache routine differs from the measured build; nothing written")
        mailbox = mailbox_of(dev)
        if mailbox is None:
            raise SystemExit("no BLECH runtime with the keys from the computer on this device; nothing written")
        done = lambda: struct.unpack("<I", dev.read(mailbox + 8, 4))[0]
        original = dev.read(STUB_AT, len(stub(0, 0)))
        print(f"Befehlswort bei {mailbox:#x}, {len(steps)} Schritt(e)")
        if a.dry_run:
            print("dry run: nothing written")
            return 0
        try:
            dev.write(STUB_AT, stub(mailbox, steps[0][0]), verify=False)
            dev.execute(ICACHE_INVALIDATE)
            for word, label in steps:
                before = done()
                dev.write(STUB_AT, stub(mailbox, word), verify=False)
                dev.execute(STUB_AT)
                ok = (done() - before) & 0xFFFFFFFF == 1
                print(f"{label:10} {'ok' if ok else 'NICHT ausgeführt'} | {where(dev)}")
                if not ok:
                    return 1
        finally:
            dev.write(STUB_AT, original)
            print("Originalbytes im Stub-Puffer zurück")
    if a.screen:
        print(display(dev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
