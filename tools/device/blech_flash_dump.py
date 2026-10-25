"""Read the whole flash of the own Electribe into one file with BLECH's FLASH READ (0x64), read only.

For a device that runs the BLECH SysEx patch (Sampler with Hacktribe or Korg's original, or the blue Electribe 2, the synth).
FLASH READ answers a flash address and a length of up to 4096 bytes with the CRC-32 of the bytes (docs/messungen/2026-10-15-blech-sysex.md).
The firmware refuses everything that reaches 0x1000000, and this tool never asks for it: a read at or above it leaves
a device without an answer until it is switched off and on (docs/speicherbereiche.md). There is no command that writes
or erases the flash. The tool reads from 0 up to 0x1000000 twice, checks every block against its CRC (a block with a wrong
CRC is asked again, three times in all), and writes the file only when both passes agree, so it is one state of the device and
not a mix of two. The first missing answer stops the run, there is no retry for a silence. The dump holds Korg data: the tool
refuses a path inside a git working tree, and the file belongs outside any repository.

    python3 blech_flash_dump.py --out ~/electribe-flash.bin                     # device on USB
    python3 blech_flash_dump.py --out x.bin --start 0x220000 --length 0x8000    # a part, for a first try
    python3 blech_flash_dump.py --emu VSB --out x.bin --start 0x220000 --length 0x8000

Reading the whole flash takes a few minutes. Switch nothing on the device during that time (no pattern change, no
WRITE, no SOFTWARE UPDATE): the second pass would then differ and nothing would be written.
"""
import argparse
import hashlib
import struct
import sys
import time
import zlib
from pathlib import Path

from flash_dump import dec, enc
from led_show import emulator_ask, mido_ask

FLASH_END = 0x1000000
INFO, FLASH, R_INFO, R_FLASH = 0x60, 0x64, 0x68, 0x6C
FLAG_FLASH = 8
STATUS = {0: "ok", 1: "bad crc", 2: "refused", 3: "out of range", 4: "the flash function did not report success", 5: "readback differs"}
TRIES = 3


def inside_a_repository(path):
    """Whether the file would land in a git working tree (a .git above it): Korg data never goes there."""
    for parent in [path.resolve().parent, *path.resolve().parents]:
        if (parent / ".git").exists():
            return parent
    return None


def search(ask):
    """Channel and model byte of the device that answers the device search (0x24 on the Sampler, the synth has its own)."""
    r = ask([0xF0, 0x42, 0x50, 0x00, 0x00, 0xF7])
    if len(r) < 13 or r[1:4] != [0x42, 0x50, 0x01]:
        raise SystemExit(f"no Electribe answered the search: {bytes(r).hex()}")
    return r[4] & 0x0F, r[6]


def talk(ask, channel, model, func, words=b""):
    r = ask([0xF0, 0x42, 0x30 + channel, 0x00, 0x01, model, func, *enc(words), 0xF7])
    if r[:6] != [0xF0, 0x42, 0x30 + channel, 0x00, 0x01, model]:
        raise SystemExit(f"an answer that is not for this device: {bytes(r[:12]).hex()}")
    return r[6], dec(r[7:-1])


def info(ask, channel, model):
    func, body = talk(ask, channel, model, INFO)
    if func != R_INFO:
        raise SystemExit(f"INFO got function {func:#x}: this firmware has no BLECH SysEx (or EXIT was held at power-on)")
    status, version, flags, _, _, flash_block = struct.unpack_from("<6I", body)
    if status or version != 1 or not flags & FLAG_FLASH or not 0 < flash_block <= 0x1000:
        raise SystemExit(f"INFO: status {status}, version {version}, flags {flags:#x}, flash block {flash_block}: this BLECH has no FLASH READ")
    return flash_block


def read_block(ask, channel, model, addr, length):
    if not 0 <= addr < addr + length <= FLASH_END:
        raise SystemExit(f"refusing a flash read at 0x{addr:x}+0x{length:x}: past 0x{FLASH_END:x}")
    for attempt in range(TRIES):
        func, body = talk(ask, channel, model, FLASH, struct.pack("<II", addr, length))
        status, a, n, crc = struct.unpack_from("<4I", body)
        data = body[16:]
        if func != R_FLASH or a != addr or n != length:
            raise SystemExit(f"unexpected answer at 0x{addr:x}: function {func:#x}, address 0x{a:x}, length {n}")
        if status:
            raise SystemExit(f"flash read at 0x{addr:x}+{length}: {STATUS.get(status, status)}; stopping")
        if len(data) == length and zlib.crc32(data) == crc:
            return data
        print(f"  0x{addr:x}: CRC does not match, asking again ({attempt + 1} of {TRIES})", flush=True)
    raise SystemExit(f"0x{addr:x}: the CRC did not match {TRIES} times; stopping")


def read_pass(ask, channel, model, start, length, block, label):
    out, t0 = bytearray(), time.monotonic()
    for addr in range(start, start + length, block):
        out += read_block(ask, channel, model, addr, min(block, start + length - addr))
        if len(out) % 0x100000 == 0:
            print(f"  {label}: {len(out) >> 20} MiB, {time.monotonic() - t0:.0f} s", flush=True)
    print(f"  {label}: {len(out)} bytes in {time.monotonic() - t0:.1f} s, sha256 {hashlib.sha256(out).hexdigest()}")
    return bytes(out)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--start", type=lambda x: int(x, 0), default=0)
    p.add_argument("--length", type=lambda x: int(x, 0), default=None)
    p.add_argument("--emu", metavar="VSB", help="read from the local emulator instead of the device")
    a = p.parse_args()
    length = FLASH_END - a.start if a.length is None else a.length
    if a.start < 0 or length <= 0 or a.start + length > FLASH_END:
        raise SystemExit(f"the range has to end at 0x{FLASH_END:x} at the latest")
    out = a.out.expanduser()
    if out.exists():
        raise SystemExit(f"{out} exists; not overwriting")
    repo = inside_a_repository(out)
    if repo:
        raise SystemExit(f"{out} lies inside the git working tree {repo}: a flash dump is Korg data, write it elsewhere")
    ask, m = emulator_ask(a.emu) if a.emu else (mido_ask(), None)
    channel, model = search(ask)
    block = info(ask, channel, model)
    print(f"Electribe on channel {channel + 1} (model byte 0x{model:02x}); FLASH READ in blocks of {block} bytes; reading 0x{a.start:x}..0x{a.start + length:x} twice")
    first = read_pass(ask, channel, model, a.start, length, block, "pass 1")
    second = read_pass(ask, channel, model, a.start, length, block, "pass 2")
    if first != second:
        diff = [hex(a.start + i) for i in range(0, len(first), block) if first[i:i + block] != second[i:i + block]]
        raise SystemExit(f"the passes differ in {len(diff)} block(s), first {diff[:8]}; the device changed its flash meanwhile, nothing written")
    out.write_bytes(first)
    print(f"written {out}")
    if m is not None and first != bytes(m.flash.mem[a.start:a.start + length]):
        raise SystemExit("emulator: the dump does not match the emulated flash")


if __name__ == "__main__":
    sys.exit(main())
