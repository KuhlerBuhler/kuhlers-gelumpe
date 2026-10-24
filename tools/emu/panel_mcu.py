# SPDX-License-Identifier: GPL-2.0-only
"""Find the panel controller firmware in a Sampler VSB and run the panel update against a fake boot ROM.

    tools/emu/.venv/bin/python tools/emu/panel_mcu.py --vsb SYSTEM.VSB [--flash dump.bin] [--simulate] [--corrupt PAGE]

Facts: docs/hintergrund/panel-controller.md. Prints offsets, sizes, hashes and the protocol steps, never
firmware bytes. The image is found by its shape, not by address: a Cortex-M vector table (stack pointer
0x20004000, odd reset vector below 64 KiB), followed directly by a u32 holding the image's own length; the
RAM loader's u32 length sits 0x28 bytes after that word, the loader right behind it.

With --simulate the emulator boots with panel version 0x95, so the firmware starts its 12-step panel update,
and this script answers like the FM3 boot ROM and the RAM loader would (sync, RAM write, run, erase, pages,
read back). The pages and the loader it receives are compared with the ones in the VSB.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from machine import UART0, Machine, load_flash  # noqa: E402

HEADER = 0x100
SP = 0x20004000
LOADER_GAP = 0x28           # from the image's length word to the loader's length word


def find(payload):
    """(image offset, image length, loader offset, loader length) in the payload, or None."""
    needle = struct.pack("<I", SP)
    at = payload.find(needle)
    while at >= 0:
        reset = struct.unpack_from("<I", payload, at + 4)[0]
        if at % 4 == 0 and reset & 1 and reset < 0x10000:
            for size in range(0x1000, 0x10001, 0x100):
                end = at + size
                if end + 4 <= len(payload) and struct.unpack_from("<I", payload, end)[0] == size:
                    lsize = struct.unpack_from("<I", payload, end + LOADER_GAP)[0]
                    if 0 < lsize <= 0x2000:
                        return at, size, end + LOADER_GAP + 4, lsize
        at = payload.find(needle, at + 1)
    return None


def describe(payload):
    hit = find(payload)
    if not hit:
        return None
    at, size, lat, lsize = hit
    img = payload[at:at + size]
    vec = struct.unpack_from("<48I", img, 0)
    used = {i - 16: hex(v) for i, v in enumerate(vec) if i >= 16 and v and v != vec[2]}
    return {
        "image_vsb_offset": hex(at + HEADER), "image_ram": hex(0xC0000000 + at), "image_size": hex(size),
        "image_sha256": hashlib.sha256(img).hexdigest(),
        "loader_vsb_offset": hex(lat + HEADER), "loader_size": hex(lsize),
        "loader_sha256": hashlib.sha256(payload[lat:lat + lsize]).hexdigest(),
        "initial_sp": hex(vec[0]), "reset": hex(vec[1]), "irq_handlers": used,
    }


class FakePanel(Machine):
    """The panel side during an update: FM3 serial boot ROM, then Korg's RAM loader."""

    def panel(self, msg):
        if not self.updating:
            super().panel(msg)


def simulate(payload, flash, corrupt=None, limit=40.0):
    at, size, lat, lsize = find(payload)
    img, loader = payload[at:at + size], payload[lat:lat + lsize]
    m = FakePanel(payload, flash)
    m.updating, m.panel_version = False, 0x95
    tx = m.uart[UART0]["tx"]
    steps, pos, state, pages, back = [], 0, 0, 0, 0
    quiet_since, last_len = 0, 0

    def take(n):
        nonlocal pos
        if len(tx) - pos < n:
            return None
        pos += n
        return bytes(tx[pos - n:pos])

    def note(*what):
        steps.append([round(m.time_ns / 1e6, 1), *what])

    def answer(b):
        m.receive(UART0, bytes(b))

    while m.time_ns < limit * 1e9 and not m.asserts and m.powered:
        m.run_until(m.time_ns / 1e9 + 0.002)
        if not m.updating:
            if len(tx) != last_len:
                if len(tx) == last_len + 1 and tx[-1] == 0x18 and m.time_ns - quiet_since > 0.5e9:
                    m.updating, pos = True, len(tx) - 1
                    note("start: lone 0x18 after a quiet line")
                last_len, quiet_since = len(tx), m.time_ns
            continue
        if state == 0 and (c := take(1)):
            note("sync", c.hex()); answer([0x11]); state = 1
        elif state == 1 and (c := take(10)):
            note("RAM write header", c.hex(), "sum ok" if sum(c[:9]) & 0xFF == c[9] else "sum BAD"); answer([0x01]); state = 2
        elif state == 2 and (c := take(lsize + 1)):
            note(f"loader {lsize:#x} bytes", "equals VSB" if c[:lsize] == loader else "DIFFERS",
                 "sum ok" if sum(c[:lsize]) & 0xFF == c[lsize] else "sum BAD"); answer([0x01]); state = 3
        elif state == 3 and (c := take(1)):
            note("sync", c.hex()); answer([0x11]); state = 4
        elif state == 4 and (c := take(10)):
            note("run command", c.hex()); answer([0x7E]); state = 5
        elif state == 5 and (c := take(1)):
            note("loader command", c.hex()); answer([0x00]); state = 6
        elif state == 6 and (c := take(1)):
            note("loader command", c.hex()); answer([0x80]); state = 7
        elif state == 7 and (c := take(6)):
            note("length command", c.hex()); answer([0x1A]); state = 8
        elif state == 8 and (c := take(257)):
            if c[:256] != img[pages * 256:(pages + 1) * 256] or sum(c[:256]) & 0xFF != c[256]:
                note("page differs", pages)
            pages += 1
            answer([0x1A])
            if pages * 256 >= size:
                note("pages written", pages); state = 9
        elif state == 9 and (c := take(1)):
            note("loader command", c.hex()); answer([0x1A]); state = 10
        elif state == 10 and (c := take(1)):
            if c[0] != 0xC8:
                note("read back ends after pages", back, "next byte", c.hex()); break
            if back == 0:
                note("read back starts (0xC8 per page)")
            page = bytearray(img[back * 256:(back + 1) * 256])
            if corrupt == back:
                page[5] ^= 1
            answer(page); back += 1
            if back * 256 >= size:
                note("read back of every page"); break
    m.run_until(m.time_ns / 1e9 + 6)     # the firmware waits 1.5 s and more before it resets the panel
    return steps, m


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--simulate", action="store_true")
    p.add_argument("--corrupt", type=int, help="with --simulate: flip one bit in this read-back page")
    p.add_argument("--png", type=Path, help="with --simulate: the display at the end")
    a = p.parse_args()
    payload = a.vsb.read_bytes()[HEADER:]
    info = describe(payload)
    if not info:
        raise SystemExit("no panel image found")
    print(json.dumps(info, indent=1))
    if a.simulate:
        steps, m = simulate(payload, load_flash(a.flash) if a.flash else None, a.corrupt)
        for s in steps:
            print(*s)
        print("asserts", m.asserts)
        if a.png:
            m.png(a.png, scale=2)


if __name__ == "__main__":
    main()
