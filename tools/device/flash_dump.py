"""Read the whole flash of the own Electribe into one file, read only.

Hacktribe's flash read (0x55) in blocks of 0x4000 bytes from 0 up to, never
past, 0x1000000: a read at or above it leaves the device without an answer
until it is switched off and on (docs/speicherbereiche.md). The flash is read
twice; the file is written only when both passes agree, so it is one state of
the device and not a mix of two. The first missing answer stops the run, there
is no retry. The dump holds Korg data and stays outside the repository.

    python3 flash_dump.py --out ~/electribe-flash.bin          # device on USB
    python3 flash_dump.py --emu VSB --start 0x220000 --length 0x8000 --out x.bin
"""
import argparse
import hashlib
import sys
import time
from pathlib import Path

from led_show import emulator_ask, mido_ask

FLASH_END = 0x1000000
BLOCK = 0x4000


def enc(data):
    out = []
    for i in range(0, len(data), 7):
        chunk = data[i:i + 7]
        out.append(sum(1 << j for j, b in enumerate(chunk) if b & 0x80))
        out += [b & 0x7F for b in chunk]
    return out


def dec(data):
    out = []
    for i in range(0, len(data), 8):
        msb = data[i]
        out += [b | (0x80 if msb >> j & 1 else 0) for j, b in enumerate(data[i + 1:i + 8])]
    return bytes(out)


def search(ask):
    r = ask([0xF0, 0x42, 0x50, 0x00, 0x00, 0xF7])
    if len(r) < 13 or r[1:4] != [0x42, 0x50, 0x01] or r[6] != 0x24:
        raise SystemExit(f"no Electribe Sampler answered the search: {bytes(r).hex()}")
    if (r[10], r[11]) != (2, 2):
        raise SystemExit(f"device reports {r[10]}.{r[11]}, measured only on 2.2; stopping")
    return r[4] & 0x0F


def read_block(ask, channel, addr, length):
    if not 0 <= addr < addr + length <= FLASH_END:
        raise SystemExit(f"refusing a flash read at 0x{addr:x}+0x{length:x}: past 0x{FLASH_END:x}")
    body = list(addr.to_bytes(4, "little")) + list(length.to_bytes(4, "little"))
    r = ask([0xF0, 0x42, 0x30 + channel, 0x00, 0x01, 0x24, 0x55, *enc(body), 0xF7])
    if r[1:9] != [0x42, 0x30 + channel, 0x00, 0x01, 0x24, 0x54, 0x55, 0x00]:
        raise SystemExit(f"unexpected answer at 0x{addr:x}: {bytes(r[:12]).hex()}")
    data = dec(r[9:-1])[:length]
    if len(data) != length:
        raise SystemExit(f"short answer at 0x{addr:x}: {len(data)} of {length} bytes")
    return data


def read_pass(ask, channel, start, length, label):
    out, t0 = bytearray(), time.monotonic()
    for addr in range(start, start + length, BLOCK):
        out += read_block(ask, channel, addr, min(BLOCK, start + length - addr))
        done = addr + BLOCK - start
        if done % 0x100000 == 0:
            print(f"  {label}: {done >> 20} MiB, {time.monotonic() - t0:.0f} s", flush=True)
    print(f"  {label}: {len(out)} bytes in {time.monotonic() - t0:.1f} s, sha256 {hashlib.sha256(out).hexdigest()}")
    return bytes(out)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--start", type=lambda x: int(x, 0), default=0)
    p.add_argument("--length", type=lambda x: int(x, 0), default=FLASH_END)
    p.add_argument("--emu", metavar="VSB", help="read from the local emulator instead of the device")
    a = p.parse_args()
    if a.start % BLOCK or a.length <= 0 or a.start + a.length > FLASH_END:
        raise SystemExit(f"start must be a multiple of 0x{BLOCK:x} and the range end at 0x{FLASH_END:x} at most")
    if a.out.exists():
        raise SystemExit(f"{a.out} exists; not overwriting")
    ask, m = emulator_ask(a.emu) if a.emu else (mido_ask(), None)
    channel = search(ask)
    print(f"Electribe on channel {channel + 1}; reading 0x{a.start:x}..0x{a.start + a.length:x} twice")
    first = read_pass(ask, channel, a.start, a.length, "pass 1")
    second = read_pass(ask, channel, a.start, a.length, "pass 2")
    if first != second:
        diff = [hex(a.start + i) for i in range(0, len(first), BLOCK) if first[i:i + BLOCK] != second[i:i + BLOCK]]
        raise SystemExit(f"the passes differ in {len(diff)} block(s), first {diff[:8]}; the device changed its flash meanwhile, nothing written")
    a.out.write_bytes(first)
    print(f"written {a.out}")
    if m is not None and first != bytes(m.flash.mem[a.start:a.start + a.length]):
        raise SystemExit("emulator: the dump does not match the emulated flash")


if __name__ == "__main__":
    sys.exit(main())
