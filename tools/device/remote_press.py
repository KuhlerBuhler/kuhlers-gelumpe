"""Operate an Electribe with the BLECH runtime from a computer over USB: every key, the encoders, the knobs, the pads, the
touchpad and the test mode, and read back where it is and what the display shows.

RAM only: a stub of 76 or 104 bytes (src/remote.mjs) goes to the EXEC buffer at 0xC1000000 and runs once per step through
BLECH's own SysEx commands (WRITE and EXEC, tools/patch/blech_sysex.py); it leaves a command word (and a panel message) for
the runtime's frame hook (tools/patch/script_remote.s), which hands it to the firmware as a message from the panel. The
original bytes of the buffer are put back at the end. Stops before anything is written when the firmware has no BLECH
EXEC (the blue Electribe refuses writes) or no runtime with the keys from the computer.

    python3 remote_press.py --emu VSB menu edit_next +1 exit     # against the local emulator
    python3 remote_press.py --dry-run menu                       # device on USB: checks only, writes nothing
    python3 remote_press.py menu edit_next +1 +1 exit            # device on USB: the steps, then where it is
    python3 remote_press.py --screen                             # where it is and the display, nothing written
    python3 remote_press.py testmode=on                          # display, light and LEDs off, Auto Power Off held

Steps (names from data/panel.mjs, with "_" for camel case: edit_next is editRight, mod_depth is modDepth):
    menu, play, bar1 ...        a key, pressed and let go
    +3, -1                      the main dial
    cutoff+2, osc-1             an encoder by name
    level=200                   a knob, 0 to 255
    pad5, pad5:64               a pad struck (velocity 100, or the number), pad5:down and pad5:up hold and let go
    touch=400,300               the touchpad touched at x, y (0 to 1023) and let go
    shift:down, shift:up        a key only pressed or only let go
    testmode=on, testmode=off   the test mode (on a device only testmode=off, see docs/test-modus.md)
    release                     let go of every key and pad the computer holds (the device does it itself after 10 s)
Knobs, pads, the touchpad, a key held and the test mode need BLECHTRIBE 1.3.8; keys and the main dial also run on 1.3.7.
"""
import argparse
import re
import struct
import sys
import zlib
from pathlib import Path

from flash_dump import enc, dec
from led_show import emulator_ask, mido_ask
from screen_check import MANAGER_PTR, EDIT_PTR, PATTERN_PTR, DISPLAY, state

STUB_AT = 0xC1000000
CODES = ((0xC0150300, 0xC0170000),       # the runtime's code area, where its signature lies (MORE3_START),
         (0xC018D000, 0xC018FF00))       # and the second code area that held it up to 1.3.7
SIGN, SIGN2 = 0x544D4552, 0x32544D52     # "REMT", the address of the command word; "RMT2", the message and the test mode
MARK, KEY, ENCODER, MESSAGE, TEST, RELEASE = 0xA5000000, 1, 2, 3, 4, 5
TOUCH = 0x22
OS_WAIT = 0xC0000B78
INFO, READ, WRITE_BEGIN, WRITE_DATA, EXEC = 0x60, 0x61, 0x62, 0x63, 0x6F
READ_FLAG, WRITE_FLAG, EXEC_FLAG = 1, 2, 0x40


class Blech:
    """BLECH's own SysEx commands: the device search, INFO, READ, WRITE (BEGIN and DATA) and EXEC, each block with its CRC-32."""

    def __init__(self, ask):
        self.ask = ask
        found = ask([0xF0, 0x42, 0x50, 0x00, 0x00, 0xF7])
        if found[:4] != [0xF0, 0x42, 0x50, 0x01] or found[6] not in (0x23, 0x24):
            raise SystemExit(f"no Electribe answered the search: {bytes(found).hex()}")
        self.head = [0x42, 0x30 + (found[4] & 15), 0x00, 0x01, found[6]]
        func, body = self.talk(INFO)
        if func != 0x68:
            raise SystemExit("no answer to BLECH's INFO: a firmware without BLECH, or switched on with EXIT held (then the runtime is off too)")
        status, version, self.flags, self.largest = struct.unpack_from("<4I", body)
        if status or version != 1 or self.flags & READ_FLAG == 0:
            raise SystemExit(f"BLECH INFO: status {status}, version {version}, flags {self.flags:#x}")

    def talk(self, func, body=b""):
        reply = self.ask([0xF0, *self.head, func, *enc(body), 0xF7])
        if reply[:6] != [0xF0, *self.head]:
            raise SystemExit(f"an answer that is not for this device: {bytes(reply[:12]).hex()}")
        return reply[6], dec(reply[7:-1])

    def read(self, addr, length):
        out = b""
        while len(out) < length:
            n = min(self.largest, length - len(out), 4096)
            func, body = self.talk(READ, struct.pack("<II", addr + len(out), n))
            status, _, count, crc = struct.unpack_from("<4I", body)
            data = body[16:]
            if func != 0x69 or status or count != n or len(data) != n or zlib.crc32(data) != crc:
                raise SystemExit(f"read {addr + len(out):#x}: status {status}, {len(data)} of {n} bytes")
            out += data
        return out

    def write(self, addr, data, verify=True):
        if self.flags & WRITE_FLAG == 0:
            raise SystemExit("this firmware's BLECH refuses writes (the blue Electribe); nothing written")
        crc = zlib.crc32(data)
        func, body = self.talk(WRITE_BEGIN, struct.pack("<3I", addr, len(data), crc))
        if func != 0x6A or struct.unpack_from("<I", body)[0]:
            raise SystemExit(f"WRITE BEGIN {addr:#x} refused: {body[:4].hex()}")
        func, body = self.talk(WRITE_DATA, data)
        status, _, count, back = struct.unpack_from("<4I", body)
        if func != 0x6B or status or count != len(data) or back != crc:
            raise SystemExit(f"WRITE DATA {addr:#x}: status {status}")

    def execute(self, addr):
        if self.flags & EXEC_FLAG == 0:
            raise SystemExit("this firmware's BLECH has no EXEC; nothing run")
        func, body = self.talk(EXEC, struct.pack("<II", addr, 0))
        status, _, value = struct.unpack_from("<3I", body)
        if func != 0x70 or status:
            raise SystemExit(f"EXEC {addr:#x} refused: status {status}")
        return value
ALIASES = {"edit_next": "editRight", "edit_prev": "editLeft", "part_next": "partInc", "part_prev": "partDec"}


def panel_names():
    """{"buttons": {name: index}, "encoders": ..., "knobs": ...} from data/panel.mjs."""
    text = (Path(__file__).resolve().parents[2] / "data" / "panel.mjs").read_text()
    encoders = text[text.index("export const ENCODERS"):text.index("export const KNOBS")]
    knobs = text[text.index("export const KNOBS"):text.index("export const KNOB_MAX")]
    return {"buttons": {name: int(index, 16) for name, index in re.findall(r'button\("(\w+)", "[^"]*", (0x[0-9a-f]+)', text)},
            "encoders": {name: int(index) for name, index in re.findall(r'id: "(\w+)",[^}]*index: (\d+)', encoders)},
            "knobs": {name: int(index) for name, index in re.findall(r'id: "(\w+)",[^}]*index: (\d+)', knobs)}}


def keys():
    return panel_names()["buttons"]


def camel(name):
    name = ALIASES.get(name, name)
    return re.sub(r"_([a-z0-9])", lambda m: m.group(1).upper(), name)


WAIT = [0xE3A06032, 0xE3A0000A, None, 0xE12FFF3C, 0xE5940008, 0xE1500005, 0x1A000004, 0xE2566001, 0x1AFFFFF7, 0xE3A00000,
        0xE5840000, 0xE8BD8070, 0xE3A00001, 0xE8BD8070]


def stub(mailbox, word, os_wait=OS_WAIT):
    """The same words as stub() in src/remote.mjs: 1 when the runtime took the command, else 0 with the word taken back."""
    words = [0xE92D4070, 0xE59F4040, 0xE5945008, 0xE59F003C, 0xE5840000, *(w or 0xE59FC030 for w in WAIT),
             mailbox, word, os_wait]
    return b"".join(struct.pack("<I", w) for w in words)


def message_stub(mailbox, at, message, os_wait=OS_WAIT):
    """The same words as messageStub() in src/remote.mjs."""
    first, second = struct.unpack("<2I", bytes(message).ljust(8, b"\0"))
    words = [0xE92D4070, 0xE59F4050, 0xE5945008, 0xE59F104C, 0xE59F204C, 0xE59F304C, 0xE881000C, 0xE59F0048,
             0xE5840000, *(w or 0xE59FC03C for w in WAIT), mailbox, at, first, second, MARK | MESSAGE, os_wait]
    return b"".join(struct.pack("<I", w) for w in words)


def word(kind, index=0, value=0):
    return MARK | (value & 0xFF) << 16 | index << 8 | kind


def command(step, names):
    """A step -> a list of (label, command word, panel message or None)."""
    def named(table, name, what):
        key = camel(name)
        if key not in names[table]:
            raise SystemExit(f"unknown {what} {name!r}; {what}s: {', '.join(sorted(names[table]))}")
        return names[table][key]

    def delta(text):
        if not -128 <= int(text) <= 127:
            raise SystemExit(f"turn by -128 to 127, not {text}")
        return int(text)

    if step == "release":
        return [(step, word(RELEASE), None)]
    if re.fullmatch(r"[+-]\d+", step):
        return [(f"Rad {step}", word(ENCODER, 0, delta(step)), None)]
    if m := re.fullmatch(r"([a-z_]+)([+-]\d+)", step):
        return [(step, word(ENCODER, named("encoders", m[1], "encoder"), delta(m[2])), None)]
    if m := re.fullmatch(r"testmode=(on|off)", step):
        return [(step, word(TEST, 0, 1 if m[1] == "on" else 0), None)]
    if m := re.fullmatch(r"touch=(\d+),(\d+)", step):
        x, y = int(m[1]), int(m[2])
        if x > 1023 or y > 1023:
            raise SystemExit("touchpad 0 to 1023")
        return [("touch", None, [0, TOUCH, 1, 0, 0]), (step, None, [5, x >> 8, x & 0xFF, y >> 8, y & 0xFF]),
                ("touch up", None, [0, TOUCH, 0, 0, 0])]
    if m := re.fullmatch(r"([a-z_]+)=(\d+)", step):
        value = int(m[2])
        if value > 255:
            raise SystemExit("knob 0 to 255")
        return [(step, None, [2, named("knobs", m[1], "knob"), value >> 8, value & 0xFF, 0])]
    if m := re.fullmatch(r"pad(\d+)(?::(\d+|down|up))?", step):
        n = int(m[1]) - 1
        if not 0 <= n < 16:
            raise SystemExit("pads 1 to 16")
        how = m[2] or "100"
        if how == "up":
            return [(step, None, [4, n, 0, 0, 0])]
        velocity = 100 if how == "down" else int(how)
        if not 1 <= velocity <= 127:
            raise SystemExit("velocity 1 to 127")
        down = (step, None, [4, n, 0, velocity, 1])
        return [down] if how == "down" else [down, (f"pad{n + 1} up", None, [4, n, 0, 0, 0])]
    if m := re.fullmatch(r"([a-z_0-9]+):(down|up)", step):
        return [(step, None, [0, named("buttons", m[1], "key"), 1 if m[2] == "down" else 0, 0, 0])]
    return [(step, word(KEY, named("buttons", step, "key")), None)]


def remote_of(dev):
    """(command word, message, korg.system.testMode, the build's sleep); message and test mode None for a runtime up to 1.3.7."""
    for start, end in CODES:
        for page in range(start, end, 0xFE8):      # pages overlap by the 24 bytes of the signature
            code = dev.read(page, min(0x1000, end - page))
            for i in range(0, len(code) - 7, 4):
                if struct.unpack_from("<I", code, i)[0] != SIGN:
                    continue
                full = i + 24 <= len(code) and struct.unpack_from("<I", code, i + 8)[0] == SIGN2
                if full:
                    a, _, b, c, wait = struct.unpack_from("<5I", code, i + 4)
                    return a, b, c, wait
                return struct.unpack_from("<I", code, i + 4)[0], None, None, OS_WAIT
    return None


def mailbox_of(dev):
    found = remote_of(dev)
    return found and found[0]


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
    if not a.emu and "testmode=on" in a.steps:
        # testmode=on froze a red Electribe on 2026-10-31 (display stayed on, no SysEx answer, power cycle needed)
        raise SystemExit("testmode=on is refused on a device until the freeze on hardware is fixed; --emu still takes it")
    dev = Blech(emulator_ask(a.emu)[0] if a.emu else mido_ask())
    names = panel_names()
    steps = [part for s in a.steps for part in command(s, names)]
    print("vorher:", where(dev))
    found = None
    if steps:
        if dev.flags & (WRITE_FLAG | EXEC_FLAG) != WRITE_FLAG | EXEC_FLAG:
            raise SystemExit("this firmware's BLECH has no WRITE and EXEC (the blue Electribe refuses both); nothing written")
        found = remote_of(dev)
        if found is None:
            raise SystemExit("no BLECH runtime with the keys from the computer on this device; nothing written")
        mailbox, message_at, test_at, os_wait = found
        if message_at is None and any(m is not None or w & 0xFF in (TEST, RELEASE) for _, w, m in steps):
            raise SystemExit("this runtime takes keys and the main dial only (knobs, pads, touchpad and test mode need 1.3.8); nothing written")
        done = lambda: struct.unpack("<I", dev.read(mailbox + 8, 4))[0]
        original = dev.read(STUB_AT, len(message_stub(0, 0, [0] * 5)))
        print(f"Befehlswort bei {mailbox:#x}, {len(steps)} Schritt(e)")
        if a.dry_run:
            print("dry run: nothing written")
            return 0
        def run(w, message=None):
            before = done()
            dev.write(STUB_AT, message_stub(mailbox, message_at, message, os_wait) if message else stub(mailbox, w, os_wait), verify=False)
            return dev.execute(STUB_AT) == 1 and (done() - before) & 0xFFFFFFFF == 1

        finished = False
        try:
            for label, w, message in steps:
                ok = run(w, message)
                print(f"{label:12} {'ok' if ok else 'NICHT ausgeführt'} | {where(dev)}")
                if not ok:
                    return 1
            finished = True
        finally:
            if not finished and message_at is not None:      # nothing the steps pressed stays down
                try:
                    print("alles losgelassen" if run(word(RELEASE)) else "Loslassen NICHT ausgeführt (das Gerät lässt nach 10 s selbst los)")
                except SystemExit as failure:
                    print(f"Loslassen fehlgeschlagen ({failure}); das Gerät lässt nach 10 s selbst los")
            dev.write(STUB_AT, original)
            print("Originalbytes im Stub-Puffer zurück")
    found = found or remote_of(dev)
    if found and found[2] is not None:
        print("Test-Modus:", "an" if dev.read(found[2], 1)[0] == 1 else "aus")
    if a.screen:
        print(display(dev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
