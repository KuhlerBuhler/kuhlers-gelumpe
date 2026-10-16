"""Measure BLECH's own SysEx commands on the own device (docs/messungen/2026-10-15-blech-sysex.md). Read only:
the device search, INFO and READ with their CRC-32, nothing is written, nothing is executed.

    python3 blech_sysex_probe.py                  # on the laptop, device on USB, firmware with BLECH
    python3 blech_sysex_probe.py --emu VSB        # the same against the emulator (blocks up to 4096 bytes: its line is DIN)
    python3 blech_sysex_probe.py --repeat 10      # ten reads per block size

It asks INFO, then reads RAM at 0xC0000100 in blocks of 256 to the largest size the device names, checks every
block against the CRC the device sent, and prints milliseconds and KiB/s per size (mean, fastest, slowest). A block that
fails stops the run: the size above it is then the limit to report, with the line it was printed on.
"""
import argparse
import struct
import time
import zlib

from flash_dump import enc, dec
from led_show import emulator_ask, mido_ask

INFO, READ, R_INFO, R_READ = 0x60, 0x61, 0x68, 0x69
ADDR = 0xC0000100
SIZES = (256, 1024, 4096, 8192, 16384, 24576, 32768)


MODEL = [0x24]     # the model byte: the device search says it (0x24 Sampler, 0x23 the blue Electribe 2)


def talk(ask, channel, func, words=b""):
    reply = ask([0xF0, 0x42, 0x30 + channel, 0, 1, MODEL[0], func, *enc(words), 0xF7])
    if reply[:6] != [0xF0, 0x42, 0x30 + channel, 0, 1, MODEL[0]]:
        raise SystemExit(f"an answer that is not for this device: {bytes(reply[:12]).hex()}")
    return reply[6], dec(reply[7:-1])


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--emu", metavar="VSB")
    p.add_argument("--repeat", type=int, default=5)
    a = p.parse_args()
    ask = emulator_ask(a.emu)[0] if a.emu else mido_ask()
    found = ask([0xF0, 0x42, 0x50, 0x00, 0x00, 0xF7])
    if found[:4] != [0xF0, 0x42, 0x50, 0x01] or found[6] not in (0x23, 0x24):
        raise SystemExit(f"no Electribe answered the search: {bytes(found).hex()}")
    MODEL[0] = found[6]
    channel = found[4] & 15
    func, body = talk(ask, channel, INFO)
    if func != R_INFO:
        raise SystemExit(f"INFO got function {func:#x}: this firmware has no BLECH SysEx")
    status, version, flags, largest, table_crc, _ = struct.unpack_from("<6I", body)
    print(f"INFO: status {status}, version {version}, flags {flags:#x}, largest block {largest}, table CRC {table_crc:#010x}")
    if status or version != 1 or flags & 3 != 3:
        raise SystemExit("not a version 1 device with read and write; stopping")
    for size in (s for s in SIZES if s <= largest and (not a.emu or s <= 4096)):
        times = []
        for _ in range(a.repeat):
            start = time.perf_counter()
            func, body = talk(ask, channel, READ, struct.pack("<II", ADDR, size))
            times.append((time.perf_counter() - start) * 1000)
            status, addr, length, crc = struct.unpack_from("<4I", body)
            data = body[16:]
            if func != R_READ or status or length != size or len(data) != size or zlib.crc32(data) != crc:
                raise SystemExit(f"{size} bytes: status {status}, {len(data)} bytes, CRC {'ok' if zlib.crc32(data) == crc else 'WRONG'}; the limit is below {size}")
        mean = sum(times) / len(times)
        print(f"{size:6d} bytes: {mean:8.1f} ms mean, {min(times):8.1f} fastest, {max(times):8.1f} slowest, {size / 1024 / (mean / 1000):8.1f} KiB/s")


if __name__ == "__main__":
    main()
