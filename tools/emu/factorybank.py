# SPDX-License-Identifier: GPL-2.0-only
"""A minimal factory sample bank for the emulated flash, made here and holding no Korg data.

The device keeps its factory samples at flash 0x800000 (docs/messungen/2026-10-07-werks-sample-flash.md):
a header "KORGelec2PCM" with the addresses of seven sections, each a tag, its size in bytes and a record count.
At start the firmware reads the tables of it (not the audio) to set up the 411 factory entries. With an erased flash
none of that exists, every factory slot then points at the same table entry, and the second sample that
e2sSample.all brings for a factory slot is refused as "slot in use" (the firmware's "Unknown Error.").

This bank has the layout of the real one and the same counts, with names, numbers and flags that are plain
formulas (entry n is called "Fac" and n, its numbers count up). There is no audio: the sample section holds
the header and its entries, and where the audio would start the flash stays erased. That is all the start reads.
"""

import struct

BASE = 0x800000
COUNT = 411                     # factory entries: 403 reference samples, eight of them stereo with two waveforms each
END = 0x7500                    # the tables end here, the audio would follow
HEAD = b"KORGelec2PCM" + bytes([1, 1, 0xFF, 0xFF])

# the sections and where the real bank puts them (offset from BASE), in the order of the header
DRMP, DRUM, MSPR, MSRL, SMPR, SMPL, MSVS = 0x40, 0x80, 0xC0, 0x1A90, 0x5B10, 0x74E0, 0x2790


def section(tag, size, count, fill=b""):
    """tag, size, count, then 20 erased bytes; `fill` follows (the records)."""
    return tag + struct.pack("<II", size, count) + b"\xff" * 20 + fill


def build():
    """The bytes of [0x800000, 0x807500) of an emulated flash."""
    mem = bytearray(b"\xff" * END)
    names = b"".join(b"Fac%03d  " % (i + 1) + struct.pack("<II", i, 0) for i in range(COUNT))
    msrl = b"".join(struct.pack("<BBHHH", 0x7F, 0, i, 0x4100, 0xFFFF) for i in range(COUNT))
    msvs = b"".join(b"M       " + b"\x7f" + b"\xff" * 7 + struct.pack("<H", i) + b"\xff" * 6 + struct.pack("<H", 0x8000) + b"\xff" * 6 for i in range(COUNT))
    pcm, smpr = 0, b""
    for i in range(COUNT):
        smpr += struct.pack("<IIIHH", pcm, 0x400, 0x400, 0x4E, 1)
        pcm += 0x402
    mem[0:0x10] = HEAD
    mem[0x10:0x40] = struct.pack("<12I", DRMP, DRUM, MSPR, MSRL, SMPR, SMPL, MSVS, 0xFFFFFFFF, pcm, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
    mem[DRMP:DRMP + 0x40] = section(b"DRMP", 0x34, 1, b"FacDrum\0" + bytes(4) + struct.pack("<I", 30) + b"\xff" * 4)
    mem[DRUM:DRUM + 0x40] = section(b"DRUM", 0xFFFFFFFF, 0x10, b"\xff" * 32)
    mem[MSPR:MSPR + 0x20 + len(names)] = section(b"MSPR", 0x20 + len(names), COUNT, names)
    mem[MSRL:MSRL + 0x20 + len(msrl)] = section(b"MSRL", 0x20 + len(msrl), COUNT, msrl)
    mem[MSVS:MSVS + 0x20 + len(msvs)] = section(b"MSVS", 0x20 + len(msvs), COUNT, msvs)
    mem[MSVS + 0x10:MSVS + 0x14] = struct.pack("<I", 1)       # the one header of the velocity split section that is not erased
    mem[SMPR:SMPR + 0x20 + len(smpr)] = section(b"SMPR", 0x20 + len(smpr), COUNT, smpr)
    mem[SMPL:SMPL + 0x20] = b"SMPL" + b"\xff" * 28
    return bytes(mem)
