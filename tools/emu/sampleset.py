# SPDX-License-Identifier: GPL-2.0-only
"""Build an e2sSample.all out of synthetic samples, for tests of the sample loader.

The layout is the one the firmware writes with EXPORT ALL SAMPLE and reads at start
(docs/hintergrund/virtuelle-sd.md): 16 bytes "e2s sample all", 0x1A, 0; 1020 little-endian
file offsets, one per slot, 0 for an empty slot; then one RIFF/WAVE file per sample (fmt, data and
the "korg" chunk with the 1172-byte "esli" record that holds name, loop and rate). Slots 0 to 499
are the factory bank and not in the file, the firmware loads slot 500 (shown as 501) to 998 (999).
The audio is a made-up formula and never a Korg sample.
"""

import struct

SLOTS = 1020
HEADER = 4096
FIRST_USER, LAST_USER = 500, 998        # zero-based slot indices of 501 to 999
ESLI = 1172
FIXED = 1232                            # file bytes a sample adds to its PCM: RIFF/fmt/data headers and the korg chunk


def esli(index, name, frames, rate=48000, width=2):
    """The 1172-byte sample record. Fields as measured against the firmware's own export
    (docs/messungen/2026-10-07-sample-metadaten-ram.md); everything not named is zero."""
    data = frames * width
    out = bytearray(ESLI)
    struct.pack_into("<H", out, 0, index)
    out[2:18] = name.encode("ascii")[:15].ljust(16, b"\0")
    struct.pack_into("<H", out, 18, 2)                  # category
    struct.pack_into("<H", out, 20, 0x226 + index % 100)
    out[25], out[27] = 0x7F, 1
    struct.pack_into("<H", out, 34, 0x42E6)             # playback period
    struct.pack_into("<H", out, 36, 0xFFFF)
    struct.pack_into("<I", out, 44, max(data - 2, 0))   # loop
    struct.pack_into("<I", out, 48, max(data - 2, 0))   # end
    out[52] = 1                                         # one shot
    struct.pack_into("<I", out, 60, data)
    out[64], out[67] = 1, 1
    struct.pack_into("<H", out, 68, 0x04B0)
    struct.pack_into("<I", out, 72, rate)
    struct.pack_into("<H", out, 78, index)
    return bytes(out)


def pcm(frames, seed=0):
    """16-bit mono audio from an integer formula; cheap to make for tens of megabytes."""
    block = struct.pack("<256h", *((37 * i - 400 + 91 * seed) % 20001 - 10000 for i in range(256)))
    return (block * (frames // 256 + 1))[:frames * 2]


# Sample formats the loader is tested with: (format tag, channels, bits). pcm16 is what the firmware itself writes.
FORMATS = {"pcm16": (1, 1, 16), "pcm24": (1, 1, 24), "pcm8": (1, 1, 8), "pcm32": (1, 1, 32), "float32": (3, 1, 32), "stereo16": (1, 2, 16)}


def audio(frames, seed, tag, channels, bits):
    """The same made-up formula as pcm(), in the sample format asked for (never a recording)."""
    base = struct.unpack(f"<{frames}h", pcm(frames, seed))
    out = bytearray()
    for v in base:
        for _ in range(channels):
            if tag == 3:
                out += struct.pack("<f", v / 32768)
            elif bits == 8:
                out += bytes([(v >> 8) + 128])
            elif bits == 24:
                out += (v << 8 & 0xFFFFFF).to_bytes(3, "little")
            elif bits == 32:
                out += struct.pack("<i", v << 16)
            else:
                out += struct.pack("<h", v)
    return bytes(out)


def wav(index, name, frames, rate=48000, kind="pcm16"):
    """`kind` is a key of FORMATS; with an L behind it (pcm24L) the record holds the length in bytes of that format, not of 16-bit audio.
    "junk" is 64 zero bytes, a sample the loader cannot even start to read."""
    if kind == "junk":
        return bytes(64)
    literal = kind.endswith("L")
    kind = kind.rstrip("L")
    tag, channels, bits = FORMATS[kind]
    data = pcm(frames, index) if kind == "pcm16" else audio(frames, index, tag, channels, bits)
    width = channels * bits // 8
    fmt = struct.pack("<HHIIHH", tag, channels, rate, rate * width, width, bits)
    korg = b"esli" + struct.pack("<I", ESLI) + esli(index, name, frames, rate, width if literal else 2)
    body = (b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data
            + b"korg" + struct.pack("<I", len(korg)) + korg)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def build(samples):
    """`samples`: {zero-based slot: (name, frames)}, (name, frames, rate) or (name, frames, rate, kind) with kind one of FORMATS or "junk", and a fifth item to put another slot into the record. The file as bytes."""
    table = [0] * SLOTS
    body = bytearray()
    for slot in sorted(samples):
        name, frames, *rest = samples[slot]
        index = rest[2] if len(rest) > 2 else slot          # the slot the record says it belongs to, the table slot by default
        table[slot] = HEADER + len(body)
        body += wav(index, name, frames, *rest[:2])
    head = b"e2s sample all\x1a\0" + struct.pack(f"<{SLOTS}I", *table)
    return head.ljust(HEADER, b"\0") + bytes(body)


def sized(count, total_frames, first=FIRST_USER, names="t"):
    """`count` samples from slot `first`, together `total_frames` frames long, as even as whole frames allow."""
    base, extra = divmod(total_frames, count)
    return {first + i: (f"{names}{first + i + 1}", base + (1 if i < extra else 0)) for i in range(count)}
