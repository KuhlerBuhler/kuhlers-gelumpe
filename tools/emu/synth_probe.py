# SPDX-License-Identifier: GPL-2.0-only
"""Probe for the PCM waves and the oscillators of the blue Electribe 2 (the synth, 2.02).

What the synth's firmware does with its PCM bank, measured in the emulator and read off the code
(docs/messungen/2026-10-15-synth-samples.md). Everything here is made of structure and numbers: the
firmware and every bank come from the user's own files and stay outside the repository, and the banks
the tool builds are made-up sines, no Korg data.

    python synth_probe.py bank FILE                    structure of a PCM bank: a 16 MiB flash dump, an 8 MiB bank or a PCM.VSB
    python synth_probe.py osc VSB                      the oscillator table and the places in the code that limit it
    python synth_probe.py boot VSB [--bank FILE | --synthetic] [--seconds S] [--voice INDEX]
    python synth_probe.py fatfs VSB [--synthetic]      the card functions at the end of the PCM load (made-up card)
    python synth_probe.py selftest                     the builder and the readers on made-up data, no firmware

`boot` starts the firmware on a flash that carries the bank (its own flash is blank, with the synth's user-data
mark), lists what it reads from the flash and writes to the DSP, reads its wave tables out of RAM and, with
`--voice`, selects the oscillator, presses a pad and lists what goes to the DSP for the voice.
"""

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = 0xC0000000
HEADER = 0x100                     # a VSB file starts with a head of this size
PAYLOAD = 0x200000

# ---- the PCM bank: flash 0x800000 to 0xFFFFFF, and a PCM.VSB carries it behind a VSB head ----------------
BANK_FLASH = 0x800000
BANK_SIZE = 0x800000
FLASH_SIZE = 0x1000000
MAGIC = b"KORG"
KINDS = (b"elec2PCM", b"X11100PC")  # what the firmware accepts behind the magic (both strings are in its code)
CORRECTION = 0x0E                  # u16 in the head, makes the 16-bit sum of the whole bank 0
SECTION_AT = {"DRMP": 0x10, "DRUM": 0x14, "MSPR": 0x18, "MSRL": 0x1C, "SMPR": 0x20, "SMPL": 0x24, "MSVS": 0x28}
RECORD = {"DRMP": 0x14, "MSPR": 16, "MSRL": 8, "SMPR": 16, "MSVS": 32}
SECTION_HEAD = 0x20                # tag, size (or ffffffff for a stream), count (stream: number of values), checksum, ffs
MODE_RAW = 7                       # block mode: 12-bit values, most significant bit first, no coding
BLOCK_VALUES = 2048
DSP_BASE = 0x365AE0                # DSP byte address of the first decoded value (the DRUM block, 16 values)
LEAD_IN = 0x20                     # bytes of the DRUM block; the first wave starts behind them
ONE_SHOT = 0x10000                 # flag bit 16 of an SMPR record: no loop (loop = end)

# ---- the places in the 2.02 image of the synth (docs/messungen/2026-10-15-synth-samples.md) --------------------
OSC_BASE = 0xC00BEB48              # first name of the oscillator table, records of OSC_STRIDE bytes
OSC_STRIDE = 0x20
OSC_COUNT = 409
OSC_BOUND = 0x198                  # largest index the code accepts
OSC_SAW = 325                      # index of SAW, the oscillator a new pattern starts with
PCM_FIRST_WAVE = 0x32              # wave ids from here on are PCM instruments (id - 0x32 = instrument), below are DSP waves
RAM = {
    "count_instruments": 0xC0353E68, "count_mspr": 0xC0353E6C, "count_msrl": 0xC0359E74, "count_smpr": 0xC034DE64,
    "count_drmp": 0xC0353E70,
    "drmp": 0xC034B664, "mspr": 0xC0351E68, "msrl": 0xC0348664, "smpr": 0xC0353E74, "msvs": 0xC034DE68,
}
PITCH_ADDED_AT_LOAD = 375          # the firmware adds this to the pitch word of every MSRL record while it loads the bank
DSP_RATE = 48000
FUNCS = {
    "param_write": 0xC000E924,     # (index, value): one parameter of the DSP's voice block
    "osc_set": 0xC0086C50,         # (timbre, oscillator index)
    "osc_apply": 0xC0086E1C,       # (timbre): sends the wave of the oscillator to the DSP
    "wave_to_dsp": 0xC00816C0,     # (voice, wave id, start, loop start, loop length on the stack, pitch word on the stack)
    "resolve": 0xC0086B18,         # (instrument, velocity, key, out*): the MSRL record of a note
    "pcm_loaded": 0xC00473D0,      # `mov r0, r6` at the end of the PCM load, r6 = success
    "f_open": 0xC008A6B8, "f_read": 0xC008A8CC, "f_write": 0xC008AB10, "f_close": 0xC008AF34, "f_lseek": 0xC008AF5C,
    "f_opendir": 0xC008B1B8, "f_closedir": 0xC008B280, "f_readdir": 0xC008B298,
    "dsp_port": 0xC0011554,        # () -> the object of the DSP host port
    "dsp_write": 0xC00105A4,       # (port, DSP byte address, source, count of 16-bit words): rounds the count up to a multiple of 16
    "dsp_write_exact": 0xC00104F0, # the same, a count that is no multiple of 16 is written as two transfers
    "work_buffer": 0xC0032A04, "work_buffer_release": 0xC0032A1C,
    "tick": 0xC00623F0,            # the screen manager's tick, a safe place to call firmware functions from
}
WORK_BUFFER = (0xC0B6BD00, 0x00C00100)
FREE_RUN = (0xC01217F4, 0xC01FFFF0)  # erased in the image, never written in any run
TRAP = 0xC07FF000                  # return address for calls, never executed
VOICE_STRIDE = 0x1A
VOICE_PARAMS = {"start": 0xB4, "loop_start": 0xAF, "loop_length": 0xB0, "pitch": 0xBE}
VOICE_BASE = 0x4300
DSP_PARAM_MAILBOX = 0xFF900A34
PAD_NOISE = 0x4C3B                 # a housekeeping parameter that is written all the time


# ---- 12-bit blocks ---------------------------------------------------------------------------------------
def pack12(values):
    """Signed 12-bit values as bytes, the first value in the high bits."""
    out, acc, bits = bytearray(), 0, 0
    for v in values:
        acc = (acc << 12) | (v & 0xFFF)
        bits += 12
        while bits >= 8:
            out.append((acc >> (bits - 8)) & 0xFF)
            bits -= 8
            acc &= (1 << bits) - 1
    if bits:
        out.append((acc << (8 - bits)) & 0xFF)
    return bytes(out)


def unpack12(data, count):
    out, acc, bits = [], 0, 0
    it = iter(data)
    while len(out) < count:
        acc = (acc << 8) | next(it)
        bits += 8
        while bits >= 12 and len(out) < count:
            v = (acc >> (bits - 12)) & 0xFFF
            out.append(v - 0x1000 if v >= 0x800 else v)
            bits -= 12
            acc &= (1 << bits) - 1
    return out


def stream(values):
    """The values as raw blocks: u16 (mode 7 in the top 3 bits, count below), then the packed values."""
    body = bytearray()
    for i in range(0, len(values), BLOCK_VALUES):
        part = values[i:i + BLOCK_VALUES]
        body += struct.pack(">H", (MODE_RAW << 13) | len(part)) + pack12(part)
    return bytes(body)


def checksum(values):
    """What a stream section keeps in its head: the sum of the 16-bit words the DSP will get (value * 16)."""
    return sum((v & 0xFFF) << 4 for v in values) & 0xFFFFFFFF


def walk_stream(data, at, limit=None):
    """Values, blocks and the count per block mode of a stream, by the block heads alone (nothing is decoded).
    Modes 0 to 4 carry a u16 length of the coded part, mode 7 is raw. Stops at the number of values the section names."""
    total = struct.unpack_from("<I", data, at + 8)[0]
    pos, values, blocks, modes = at + SECTION_HEAD, 0, 0, {}
    while values < total and (limit is None or blocks < limit):
        head = struct.unpack_from(">H", data, pos)[0]
        mode, count = head >> 13, head & 0x1FFF
        if mode == MODE_RAW:
            pos += 2 + (count * 12 + 7) // 8
        elif mode <= 4:
            pos += 4 + struct.unpack_from(">H", data, pos + 2)[0]
        else:
            raise ValueError(f"unknown block mode {mode} at {pos:#x}")
        values += count
        blocks += 1
        modes[mode] = modes.get(mode, 0) + 1
    return {"values": values, "named": total, "blocks": blocks, "modes": dict(sorted(modes.items())), "end": pos}


# ---- a made-up bank ---------------------------------------------------------------------------------------
def sine(length, cycles, amplitude=1500):
    return [int(round(amplitude * math.sin(2 * math.pi * cycles * i / length))) for i in range(length)]


def section(tag, count, records, third=0, fourth=0xFFFFFFFF):
    """A table section: tag, size with the head, count, then two words (a sum for SMPR, a format word for MSVS) and ffs."""
    body = b"".join(records)
    return tag + struct.pack("<IIII", SECTION_HEAD + len(body), count, third, fourth) + b"\xff" * 12 + body


def build_bank(waves, pitch_word=0x4800, kind=b"elec2PCM"):
    """A bank of one instrument per wave, in the layout the firmware reads (every number measured on its own
    bank and accepted by the firmware in the emulator): `waves` is a list of (name, list of signed 12-bit values).
    Returns the 8 MiB the flash holds at 0x800000, with the correction word that makes its 16-bit sum 0."""
    n = len(waves)
    starts, pos = [], 0
    for _, values in waves:
        starts.append(pos)
        pos += 2 * len(values)
    everything = [v for _, values in waves for v in values]
    impulse = [0x400] + [0] * 15
    parts = {
        "DRMP": section(b"DRMP", 1, [b"TESTIMP1" + struct.pack("<IIi", 0, 0x1E, -1796)]),
        "DRUM": b"DRUM" + struct.pack("<III", 0xFFFFFFFF, len(impulse), checksum(impulse)) + b"\xff" * 16 + stream(impulse),
        "MSPR": section(b"MSPR", n, [name.ljust(8)[:8].encode("latin1") + struct.pack("<II", i, 0) for i, (name, _) in enumerate(waves)]),
        "MSRL": section(b"MSRL", n, [bytes([0x7F, 0]) + struct.pack("<HHH", i, pitch_word, 0xFFFF) for i in range(n)]),
        "SMPR": section(b"SMPR", n, [struct.pack("<IIII", starts[i], 2 * len(v) - 2, 2 * len(v) - 2, ONE_SHOT | 0x34) for i, (_, v) in enumerate(waves)]),
        "SMPL": b"SMPL" + struct.pack("<III", 0xFFFFFFFF, len(everything), checksum(everything)) + b"\xff" * 16 + stream(everything),
        # format word 1 in the head: the records are the final ones and the firmware copies them as they are
        "MSVS": section(b"MSVS", n, [b"M       " + bytes([0x7F] + [255] * 7) + struct.pack("<4H", i, 0xFFFF, 0xFFFF, 0xFFFF)
                                      + struct.pack("<4H", 0x8000, 0xFFFF, 0xFFFF, 0xFFFF) for i in range(n)], 0xFFFFFFFF, 1),
    }
    order = ["DRMP", "DRUM", "MSPR", "MSRL", "MSVS", "SMPR", "SMPL"]
    head = bytearray(b"\xff" * 0x40)
    head[0:4], head[4:12], head[12:14] = MAGIC, kind, b"\x01\x01"
    head[CORRECTION:CORRECTION + 2] = b"\0\0"
    body, at = bytearray(), 0x40
    for name in order:
        struct.pack_into("<I", head, SECTION_AT[name], at)
        piece = parts[name] + b"\xff" * (-len(parts[name]) % 16)
        body += piece
        at += len(piece)
    bank = bytearray(bytes(head) + bytes(body))
    if len(bank) > BANK_SIZE:
        raise ValueError("the waves do not fit into 8 MiB")
    bank += b"\xff" * (BANK_SIZE - len(bank))
    struct.pack_into("<H", bank, CORRECTION, (-sum16(bank)) & 0xFFFF)
    return bytes(bank)


def sum16(data):
    return sum(struct.unpack_from(f"<{len(data) // 2}H", data, 0)) & 0xFFFF


def pitch_word(root_key, rate):
    """The 16-bit word the DSP gets for a wave (1/256 semitone): the key at which it plays one sample per output sample,
    which is the root key moved by the difference between the sample rate and the DSP's 48 kHz. As the firmware
    keeps it in RAM, after it has added PITCH_ADDED_AT_LOAD to the word the bank carries."""
    return round(256 * (root_key + 12 * math.log2(DSP_RATE / rate)))


def synthetic_waves():
    return [("SYNA", sine(200, 2)), ("SYNB", sine(300, 3)), ("SYNC", sine(1000, 10, 1000)), ("SYND", sine(64, 1))]


def expected_dsp(waves):
    """The DSP memory a made-up bank must produce from DSP_BASE on: the 16 values of the DRUM block, then every wave,
    each value as the 16-bit word value * 16 (little endian in the transfer), padded to a multiple of 16 words."""
    values = [0x400] + [0] * 15 + [v for _, w in waves for v in w]
    data = b"".join(struct.pack("<H", (v << 4) & 0xFFFF) for v in values)
    return data + bytes(-len(data) % 32)


# ---- reading a bank ---------------------------------------------------------------------------------------
def bank_of(data):
    """The 8 MiB of the bank in a file: a 16 MiB flash dump, a PCM.VSB (head 0x100, tag PCM) or the bank alone."""
    if len(data) == FLASH_SIZE:
        return data[BANK_FLASH:]
    if len(data) == HEADER + BANK_SIZE and data[0x20:0x23] == b"PCM":
        return data[HEADER:]
    if len(data) == BANK_SIZE:
        return data
    raise ValueError(f"{len(data)} bytes: neither a flash dump, a PCM.VSB nor a bank")


def parse_bank(bank):
    """The structure of a bank, counts and sizes only. Nothing of the audio and no name is returned."""
    if len(bank) != BANK_SIZE or bank[:4] != MAGIC or bank[4:12] not in KINDS:
        raise ValueError("not a PCM bank")
    out = {"kind": bank[4:12].decode(), "version": list(bank[12:14]), "correction": struct.unpack_from("<H", bank, CORRECTION)[0],
           "sum16": sum16(bank), "sections": {}}
    u = lambda o: struct.unpack_from("<I", bank, o)[0]
    for name, field in SECTION_AT.items():
        at = u(field)
        if at == 0xFFFFFFFF:
            out["sections"][name] = None
            continue
        if bank[at:at + 4] != name.encode():
            raise ValueError(f"{name} is not at {at:#x}")
        out["sections"][name] = {"at": at, "size_field": u(at + 4), "count": u(at + 8), "check": u(at + 12)}
    s = out["sections"]
    for name in ("DRUM", "SMPL"):
        if s[name]:
            s[name]["stream"] = walk_stream(bank, s[name]["at"])
    smpr = s["SMPR"]
    if smpr:
        at = smpr["at"] + SECTION_HEAD
        rows = [struct.unpack_from("<4I", bank, at + 16 * i) for i in range(smpr["count"])]
        lengths = sorted(end + 2 for _, _, end, _ in rows)
        out["waves"] = {"count": len(rows), "one_shot": sum(1 for _, loop, end, flags in rows if loop == end and flags & ONE_SHOT),
                        "looped": sum(1 for _, loop, end, _ in rows if loop != end),
                        "length_min": lengths[0], "length_median": lengths[len(lengths) // 2], "length_max": lengths[-1],
                        "bytes": sum(lengths), "last_end": max(start + end + 2 for start, _, end, _ in rows),
                        "dsp_end": DSP_BASE + LEAD_IN + max(start + end + 2 for start, _, end, _ in rows)}
    counts = {n: s[n]["count"] for n in ("MSPR", "MSRL", "SMPR", "MSVS") if s[n]}
    out["counts_equal"] = len(set(counts.values())) == 1
    return out


# ---- the oscillator table in the image --------------------------------------------------------------------
def osc_table(payload):
    """The oscillator records: name, group, wave id, range of the two edit values and their defaults."""
    out = []
    for i in range(OSC_COUNT):
        r = payload[OSC_BASE - BASE + i * OSC_STRIDE:][:OSC_STRIDE]
        out.append({"index": i, "name": r[:16].split(b"\0")[0].decode("latin1"), "group": r[0x10], "wave": struct.unpack_from("<H", r, 0x12)[0],
                    "low": struct.unpack_from("<b", r, 0x16)[0], "high": struct.unpack_from("<b", r, 0x17)[0],
                    "default_a": r[0x18], "flag_a": r[0x19], "default_b": r[0x1C], "flag_b": r[0x1D]})
    return out


def check_osc(payload):
    """Whether the table is where this tool expects it: SAW with wave id 1 at its index, the table ends at 'Audio In'."""
    table = osc_table(payload)
    return table[OSC_SAW]["name"] == "SAW" and table[OSC_SAW]["wave"] == 1 and table[OSC_COUNT - 1]["name"] == "Audio In"


def words(payload):
    return struct.unpack(f"<{len(payload) // 4}I", payload[:len(payload) // 4 * 4])


def arm_immediate(value):
    """The 12-bit field (rotation and 8 bits) that makes `value` an immediate of a data-processing instruction."""
    for rot in range(0, 32, 2):
        v = ((value << rot) | (value >> (32 - rot))) & 0xFFFFFFFF if rot else value
        if v < 256:
            return (rot // 2) << 8 | v
    raise ValueError(f"{value:#x} is not an ARM immediate")


def compare_sites(payload, limit=OSC_BOUND, end=0x100000):
    """Addresses of `cmp Rn, #limit` (any condition, any register) in the code."""
    imm = arm_immediate(limit)
    w = words(payload[:end])
    return [BASE + 4 * i for i, x in enumerate(w) if (x >> 20) & 0xFF == 0x35 and x & 0xFFF == imm]


def literal_users(payload, value, end=0x100000):
    """Addresses of the `ldr Rd, [pc, #n]` that load `value` out of a literal pool."""
    w = words(payload)
    out = []
    for i, x in enumerate(w[:end // 4]):
        if x & 0x0F7F0000 != 0x051F0000:
            continue
        target = i * 4 + 8 + (x & 0xFFF if (x >> 23) & 1 else -(x & 0xFFF))
        if 0 <= target < len(payload) - 3 and w[target // 4] == value:
            out.append(BASE + 4 * i)
    return out


def flatten(table):
    return {t["name"]: t for t in table}


# ---- the firmware in the emulator ---------------------------------------------------------------------------
class Probe:
    """The synth firmware in the emulator with the DSP host port and the flash reads logged."""

    def __init__(self, payload, flash=None, keep_words=16, card=None):
        import machine
        self.machine = machine
        self.m = machine.Machine(bytes(payload), flash)
        if self.m.profile.build != "synth":
            raise ValueError(f"this is the {self.m.profile.build} build, not the synth")
        self.uc, self.A = self.m.uc, self.m.A
        self.keep = keep_words
        self.tx, self.flash_reads, self._ctl = [], [], []
        self.mmc_first_ms = None
        original, flash_read = self.m.write, self.m._flash_read
        port = machine.DSP_CTRL, machine.DSP_DATA

        def write(a, v):
            if a == port[0]:
                self._ctl.append(v & 0xFFFF)
                if len(self._ctl) == 7 and self._ctl[0] in (0xA9, 0xAB):
                    c = self._ctl
                    address = (c[2] << 16) | c[1]
                    self.tx.append({"ms": round(self.m.time_ns / 1e6, 2), "cmd": c[0], "address": address, "words": c[3], "data": []})
                    self._ctl = []
                elif len(self._ctl) == 1 and self._ctl[0] == 0x2C:
                    self._ctl = []
            elif a == port[1] and self.tx:
                t = self.tx[-1]
                if t["address"] < 0xFF000000 or len(t["data"]) < self.keep:
                    t["data"].append(v & 0xFFFF)
            return original(a, v)

        def flash_reader():
            r = [self.m.reg(x) for x in (self.A.UC_ARM_REG_R1, self.A.UC_ARM_REG_R2, self.A.UC_ARM_REG_R3)]
            self.flash_reads.append({"ms": round(self.m.time_ns / 1e6, 2), "flash": r[0], "bytes": r[1], "ram": r[2]})
            return flash_read()

        self.m.write = write
        self.m._flash_read = flash_reader
        self.log = []
        if card is not None:
            self.m.insert_card(card)
            mmc = self.m.mmc
            read, put = mmc.read, mmc.write

            def seen(f):
                def wrapped(*a, **k):
                    if self.mmc_first_ms is None:
                        self.mmc_first_ms = round(self.m.time_ns / 1e6, 2)
                    return f(*a, **k)
                return wrapped
            mmc.read, mmc.write = seen(read), seen(put)

    # -- running and looking
    def run_to(self, seconds):
        self.m.run_until(seconds)

    def run(self, seconds):
        self.m.run_until(self.m.time_ns / 1e9 + seconds)

    def u32(self, address):
        return struct.unpack("<I", bytes(self.uc.mem_read(address, 4)))[0]

    def u16(self, address):
        return struct.unpack("<H", bytes(self.uc.mem_read(address, 2)))[0]

    def read(self, address, length):
        return bytes(self.uc.mem_read(address, length))

    def reg(self, n):
        return self.uc.reg_read(self.A.UC_ARM_REG_R0 + n)

    def hook(self, address, callback):
        import unicorn
        handle = self.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, a, s, d: callback(), begin=address, end=address)
        self.uc.ctl_flush_tb()
        return handle

    def unhook(self, handle):
        self.uc.hook_del(handle)
        self.uc.ctl_flush_tb()

    # -- the DSP
    def dsp_segments(self):
        """What was written to the DSP's sample memory, adjacent writes joined: [(start, bytes)]."""
        out = []
        for t in self.tx:
            if t["cmd"] != 0xAB or t["address"] >= 0xFF000000:
                continue
            data = b"".join(struct.pack("<H", w) for w in t["data"])
            if out and out[-1][0] + len(out[-1][1]) == t["address"]:
                out[-1] = (out[-1][0], out[-1][1] + data)
            else:
                out.append((t["address"], data))
        return out

    def dsp_bytes(self, address, length):
        """`length` bytes of what was written to DSP memory at `address`, or None when a part of it was never written."""
        for start, data in self.dsp_segments():
            if start <= address and address + length <= start + len(data):
                return data[address - start:address - start + length]
        return None

    # -- tables
    def tables(self, rows=2):
        r = RAM
        counts = {k: self.u32(v) for k, v in r.items() if k.startswith("count")}
        sizes = {"drmp": RECORD["DRMP"], "mspr": 16, "msrl": 8, "smpr": 16, "msvs": 32}
        first = {k: [self.read(r[k] + i * sizes[k], sizes[k]).hex() for i in range(rows)] for k in sizes}
        return {"counts": counts, "first_records": first}

    def chain(self, wave):
        """Instrument, zone, MSRL record and SMPR record of a wave id, as the firmware resolves a note."""
        instrument = wave - PCM_FIRST_WAVE
        zone = self.u16(RAM["msvs"] + instrument * 32 + 0x10)
        layer = self.u32(RAM["mspr"] + zone * 16 + 8)
        sample = self.u16(RAM["msrl"] + layer * 8 + 2)
        return {"instrument": instrument, "zone": zone, "layer": layer, "sample": sample,
                "pitch_word": self.u16(RAM["msrl"] + layer * 8 + 4),
                "smpr": list(struct.unpack("<4I", self.read(RAM["smpr"] + sample * 16, 16)))}

    def set_smpr(self, sample, start=None, loop=None, end=None, flags=None):
        cur = list(struct.unpack("<4I", self.read(RAM["smpr"] + sample * 16, 16)))
        for i, v in enumerate((start, loop, end, flags)):
            if v is not None:
                cur[i] = v
        self.uc.mem_write(RAM["smpr"] + sample * 16, struct.pack("<4I", *cur))

    def set_pitch_word(self, layer, word):
        self.uc.mem_write(RAM["msrl"] + layer * 8 + 4, struct.pack("<H", word))

    # -- the panel and the voice
    def encoder_osc(self, delta=1):
        self.m.send([0x01, 0x01, 0x00, delta & 0xFF, 0])

    def select_osc(self, index, step=0.1):
        """Turn the SAMPLE / OSC encoder from the oscillator a new pattern starts with (SAW) to `index`, one step
        per message. The firmware takes the oscillator over into the timbre when a note starts, so the result is
        read from what the voice sends (press_pad), not from here. Returns the number of steps."""
        steps = index - OSC_SAW
        for _ in range(abs(steps)):
            self.encoder_osc(1 if steps > 0 else -1)
            self.run(step)
        self.run(0.3)
        return {"steps": steps}

    def press_pad(self, pad=0, hold=0.4, after=0.4):
        """Press a pad and let go; what the firmware sends to the DSP for the voice in between:
        the `wave_to_dsp` call and every `param_write` except the housekeeping one."""
        params, calls = {}, []

        def on_param():
            if self.reg(0) != PAD_NOISE:
                params[self.reg(0)] = self.reg(1)

        def on_wave():
            sp = self.uc.reg_read(self.A.UC_ARM_REG_SP)
            extra = struct.unpack("<2I", self.read(sp, 8))
            calls.append({"voice": self.reg(0), "wave": self.reg(1), "start": self.reg(2), "loop_start": self.reg(3),
                          "loop_length": extra[0], "pitch_word": extra[1]})

        handles = [self.hook(FUNCS["param_write"], on_param), self.hook(FUNCS["wave_to_dsp"], on_wave)]
        try:
            self.m.send([0x04, pad, 0x00, 0x64, 1])
            self.run(hold)
            self.m.send([0x04, pad, 0x00, 0x00, 0])
            self.run(after)
        finally:
            for h in handles:
                self.unhook(h)
        voice = calls[0]["voice"] if calls else 0
        names = {k: VOICE_BASE + VOICE_STRIDE * voice + off for k, off in VOICE_PARAMS.items()}
        return {"call": calls[0] if calls else None, "params": {hex(k): hex(v) for k, v in params.items()},
                "voice_params": {k: hex(params[a]) if a in params else None for k, a in names.items()}}

    # -- calling firmware functions from inside the tick of the screen manager
    def call(self, function, *args, limit_s=3.0):
        import unicorn
        m, uc, A = self.m, self.uc, self.A
        hit = []
        hook = uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: (hit.append(1), u.emu_stop()), begin=FUNCS["tick"], end=FUNCS["tick"])
        uc.ctl_flush_tb()
        end = m.time_ns / 1e9 + limit_s
        while not hit and m.time_ns / 1e9 < end:
            m.run_slice()
            if not hit:
                m.lines()
                m.irq()
        uc.hook_del(hook)
        uc.ctl_flush_tb()
        if not hit:
            raise RuntimeError("the screen tick did not come")
        return self._call_here(function, args, limit_s)

    def run_to_pc(self, address, limit_s=3.0):
        """Run until the CPU stands in front of `address` (True), or the limit passes (False). The CPU is left there,
        with the exit still in place; `leave` carries on."""
        m, uc, A = self.m, self.uc, self.A
        uc.ctl_set_exits([address, *m.ENTRIES])
        end = m.time_ns / 1e9 + limit_s
        while uc.reg_read(A.UC_ARM_REG_PC) != address and m.time_ns / 1e9 < end and not m.asserts:
            m.run_slice()
            if uc.reg_read(A.UC_ARM_REG_PC) != address:
                m.lines()
                m.irq()
        return uc.reg_read(A.UC_ARM_REG_PC) == address

    def leave(self):
        """Carry on from the address `run_to_pc` stopped at."""
        m, uc, A = self.m, self.uc, self.A
        uc.ctl_set_exits(list(m.ENTRIES))
        m.step_over(uc.reg_read(A.UC_ARM_REG_PC))

    def call_here(self, function, *args, limit_s=3.0):
        return self._call_here(function, args, limit_s)

    def _call_here(self, function, args, limit_s=3.0):
        m, uc, A = self.m, self.uc, self.A
        regs = [A.UC_ARM_REG_R0 + i for i in range(13)] + [A.UC_ARM_REG_SP, A.UC_ARM_REG_LR, A.UC_ARM_REG_PC, A.UC_ARM_REG_CPSR]
        saved = [uc.reg_read(r) for r in regs]
        for i, value in enumerate(args):
            uc.reg_write(A.UC_ARM_REG_R0 + i, value & 0xFFFFFFFF)
        uc.reg_write(A.UC_ARM_REG_SP, (saved[13] - 0x400) & ~7)
        uc.reg_write(A.UC_ARM_REG_LR, TRAP)
        uc.reg_write(A.UC_ARM_REG_PC, function)
        end = m.time_ns + int(limit_s * 1e9)
        uc.ctl_set_exits([TRAP, *m.ENTRIES])
        try:
            while uc.reg_read(A.UC_ARM_REG_PC) != TRAP and m.time_ns < end and not m.asserts:
                m.run_slice(limit=end)
                if uc.reg_read(A.UC_ARM_REG_PC) != TRAP:
                    m.lines()
                    m.irq()
        finally:
            uc.ctl_set_exits(list(m.ENTRIES))
        result, returned = uc.reg_read(A.UC_ARM_REG_R0), uc.reg_read(A.UC_ARM_REG_PC) == TRAP
        for r, value in zip(regs, saved):
            uc.reg_write(r, value)
        if not returned:
            raise RuntimeError(f"{function:#x} did not return")
        return result

    def ram_runs(self, low=0xC0200000, high=0xC8000000):
        """Runs of 4 KiB pages above the image that hold anything but zeros, joined across gaps of 16 pages."""
        import ramwatch
        return [{"start": hex(a), "end": hex(b), "kib": (b - a) // 1024} for a, b in ramwatch.page_runs(ramwatch.non_zero_pages(self.m, low, high), gap=16)]


def blank_synth_flash(machine, bank=None):
    flash = machine.blank_flash(b"KORGelec2USR")
    if bank is not None:
        flash[BANK_FLASH:BANK_FLASH + BANK_SIZE] = bank
    return bytes(flash)


def load_payload(path):
    raw = Path(path).read_bytes()
    if len(raw) != HEADER + PAYLOAD:
        raise ValueError("a VSB has a 0x100 byte head and 0x200000 bytes of code")
    return raw[HEADER:]


# ---- commands ---------------------------------------------------------------------------------------------
def cmd_bank(a):
    print(json.dumps(parse_bank(bank_of(Path(a.file).read_bytes())), indent=1))


def cmd_osc(a):
    payload = load_payload(a.vsb)
    if not check_osc(payload):
        raise SystemExit("this is not the synth's 2.02 image: the oscillator table is not where it was measured")
    table = osc_table(payload)
    groups = {}
    for t in table:
        groups.setdefault(t["group"], []).append(t)
    waves = [t["wave"] for t in table]
    users = literal_users(payload, OSC_BASE)
    print(json.dumps({
        "table": {"base": hex(OSC_BASE), "stride": OSC_STRIDE, "records": len(table), "bound_in_code": OSC_BOUND},
        "groups": {hex(g): {"records": len(t), "first": t[0]["index"], "waves": [min(x["wave"] for x in t), max(x["wave"] for x in t)]} for g, t in sorted(groups.items())},
        "wave_ids": {"min": min(waves), "max": max(waves), "distinct": len(set(waves)), "dsp_synth_records": sum(1 for w in waves if w < PCM_FIRST_WAVE),
                     "pcm_records": sum(1 for w in waves if w >= PCM_FIRST_WAVE), "missing_below_max": [i for i in range(1, max(waves)) if i not in set(waves)]},
        "compare_with_bound": [hex(x) for x in compare_sites(payload)],
        "users_of_table": [hex(x) for x in users],
        "sha256_of_table": hashlib.sha256(payload[OSC_BASE - BASE:OSC_BASE - BASE + OSC_COUNT * OSC_STRIDE]).hexdigest()[:16],
    }, indent=1))


def boot_probe(vsb, bank, seconds, voice, relocate, card=None, expected=None, held=0):
    import machine
    payload = load_payload(vsb)
    probe = Probe(payload, blank_synth_flash(machine, bank), card=card)
    probe.m.held = held
    tail = None
    if probe.run_to_pc(FUNCS["pcm_loaded"], seconds):
        panel = probe.u32(probe.m.profile.values["panel"])
        tail = {"ms": round(probe.m.time_ns / 1e6, 2), "r6_success": probe.reg(6), "panel_held_word": hex(probe.u32(panel + 0x18)),
                "exit_held": bool(probe.u32(panel + 0x18) & 0x2000)}
        probe.leave()
    probe.run_to(seconds)
    m = probe.m
    segs = probe.dsp_segments()
    report = {"build": m.profile.build, "screen": m.screen(), "booted_ms": m.boot_ms, "asserts": m.asserts, "at_the_end_of_the_pcm_load": tail,
              "flash_reads": probe.flash_reads, "tables": probe.tables(),
              "dsp_memory_writes": {"transactions": sum(1 for t in probe.tx if t["cmd"] == 0xAB and t["address"] < 0xFF000000),
                                    "segments": [{"start": hex(s), "bytes": len(d), "end": hex(s + len(d))} for s, d in segs]},
              "dsp_mailbox_transactions": sum(1 for t in probe.tx if t["address"] >= 0xFF000000), "ram_runs": probe.ram_runs()}
    if expected is not None:
        got = dict(segs).get(DSP_BASE, b"")
        report["dsp_memory_writes"]["equals_made_up_waves"] = got == expected
        report["dsp_memory_writes"]["expected_bytes"] = len(expected)
    if voice is not None:
        reached = probe.select_osc(voice)
        first = probe.press_pad()
        wave = first["call"]["wave"] if first["call"] else None
        report["voice"] = {"selected": reached, "first_note": first}
        if relocate and wave and wave >= PCM_FIRST_WAVE:
            c = probe.chain(wave)
            free = max(s + len(d) for s, d in segs) if segs else DSP_BASE
            moved = (free + 0x1F) & ~0x1F
            probe.set_smpr(c["sample"], start=moved)
            second = probe.press_pad()
            changed = {k: [first["voice_params"][k], second["voice_params"][k]] for k in first["voice_params"] if first["voice_params"][k] != second["voice_params"][k]}
            report["voice"]["relocated"] = {"chain": c, "new_start": hex(moved), "second_note": second, "voice_params_changed": changed,
                                            "wave_call_changed": {k: [first["call"][k], second["call"][k]] for k in first["call"] if first["call"][k] != second["call"][k]}}
    return report


def cmd_boot(a):
    import machine
    bank = expected = None
    if a.bank:
        bank = bank_of(Path(a.bank).read_bytes())
    elif a.synthetic:
        bank = build_bank(synthetic_waves())
        expected = expected_dsp(synthetic_waves())
    print(json.dumps(boot_probe(a.vsb, bank, a.seconds, a.voice, a.relocate, expected=expected, held=a.held), indent=1))


def cmd_fatfs(a):
    """The firmware's own card functions at the end of the PCM load and later, on a made-up card."""
    import fat32
    from sdcard import MemoryMedium, SDCard
    import machine
    wav = wav_file(sine(1000, 5, 1000), 44100)
    img = fat32.format_image(128 * 1024 * 1024)
    volume = fat32.Volume(img)
    volume.write("/KORG/blechtribe/Wave/test.wav", wav)
    volume.close()
    bank = build_bank(synthetic_waves()) if a.synthetic else None
    probe = Probe(load_payload(a.vsb), blank_synth_flash(machine, bank), card=SDCard(MemoryMedium(img)))
    fil, path, buf, br = 0xC0130000, 0xC0131000, 0xC0132000, 0xC0131800

    def read_file(call):
        touched = probe.mmc_first_ms
        probe.uc.mem_write(path, b"SD:KORG/blechtribe/Wave/test.wav\0")
        probe.uc.mem_write(fil, bytes(0x400))
        opened = call(FUNCS["f_open"], fil, path, 1)
        read = call(FUNCS["f_read"], fil, buf, len(wav), br) if opened == 0 else None
        got = probe.u32(br)
        equal = probe.read(buf, len(wav)) == wav if read == 0 else False
        closed = call(FUNCS["f_close"], fil) if opened == 0 else None
        return {"f_open": opened, "f_read": read, "bytes_read": got, "content_equal": equal, "f_close": closed,
                "at_ms": round(probe.m.time_ns / 1e6, 2), "card_touched_before_the_call_ms": touched}

    def write_file(call):
        """f_open for writing (create always), f_write, f_close; the file is then read back out of the card image."""
        out = b"WRITE-TEST" * 100
        probe.uc.mem_write(path, b"SD:KORG/blechtribe/Wave/out.bin\0")
        probe.uc.mem_write(fil, bytes(0x400))
        probe.uc.mem_write(buf, out)
        opened = call(FUNCS["f_open"], fil, path, 0x0A)
        wrote = call(FUNCS["f_write"], fil, buf, len(out), br) if opened == 0 else None
        closed = call(FUNCS["f_close"], fil) if opened == 0 else None
        return {"f_open": opened, "f_write": wrote, "bytes_written": probe.u32(br), "f_close": closed}, out

    def list_folder(call):
        """f_opendir and f_readdir over the made-up folder: the short names the firmware's FILINFO holds at +9."""
        dirobj, info = 0xC0133000, 0xC0133200
        probe.uc.mem_write(path, b"SD:KORG/blechtribe/Wave\0")
        probe.uc.mem_write(dirobj, bytes(0x100))
        opened = call(FUNCS["f_opendir"], dirobj, path)
        names = []
        while opened == 0 and len(names) < 8:
            probe.uc.mem_write(info, bytes(0x80))
            if call(FUNCS["f_readdir"], dirobj, info) != 0 or probe.read(info + 9, 1) == b"\0":
                break
            names.append(probe.read(info + 9, 13).split(b"\0")[0].decode("latin1"))
        closed = call(FUNCS["f_closedir"], dirobj) if opened == 0 else None
        return {"f_opendir": opened, "names": names, "f_closedir": closed}

    stopped = probe.run_to_pc(FUNCS["pcm_loaded"], a.seconds)
    report = {"file_size": len(wav), "pcm_loaded_reached": stopped}
    if stopped:
        report["at_the_end_of_the_pcm_load"] = read_file(probe.call_here)
        probe.leave()
    probe.run_to(a.seconds)
    report["later"] = read_file(probe.call)
    report["folder"] = list_folder(probe.call)
    written, out = write_file(probe.call)
    probe.run(1.5)
    volume = fat32.Volume(img)
    try:
        written["content_equal_on_the_card"] = volume.read("/KORG/blechtribe/Wave/out.bin") == out
    except Exception as error:
        written["content_equal_on_the_card"] = f"not readable: {error}"
    volume.close()
    report["write"] = written
    report["booted_ms"] = probe.m.boot_ms
    report["asserts"] = probe.m.asserts
    print(json.dumps(report, indent=1))


def append_instrument(probe, name, start, loop, end, flags, pitch, template=0):
    """Add one instrument to the firmware's tables in RAM, after the last one: an MSVS record with one zone, an MSPR
    record, one MSRL layer and one SMPR record, and the four counts. Returns the instrument index (the wave id is
    PCM_FIRST_WAVE + index). The tables hold up to 512 instruments and 1536 samples, the limits the loader checks."""
    n = probe.u32(RAM["count_instruments"])
    if n >= 0x200:
        raise ValueError("the instrument table is full")
    for key in ("count_mspr", "count_msrl", "count_smpr"):
        if probe.u32(RAM[key]) != n:
            raise ValueError(f"{key} differs from the instrument count")
    msvs = bytearray(probe.read(RAM["msvs"] + template * 32, 32))
    struct.pack_into("<H", msvs, 0x10, n)
    probe.uc.mem_write(RAM["msvs"] + n * 32, bytes(msvs))
    probe.uc.mem_write(RAM["mspr"] + n * 16, name.encode("latin1")[:8].ljust(8) + struct.pack("<II", n, 0))
    layer = bytearray(probe.read(RAM["msrl"] + template * 8, 8))
    struct.pack_into("<HH", layer, 2, n, pitch)
    probe.uc.mem_write(RAM["msrl"] + n * 8, bytes(layer))
    probe.uc.mem_write(RAM["smpr"] + n * 16, struct.pack("<4I", start, loop, end, flags))
    for key in ("count_instruments", "count_mspr", "count_msrl", "count_smpr"):
        probe.uc.mem_write(RAM[key], struct.pack("<I", n + 1))
    return n


def repoint_osc(probe, osc, name, instrument, template=0):
    """Make oscillator record `osc` play instrument `instrument`: the name, the wave id, and the edit ranges and defaults of a
    PCM record (`template`), whose group and A/B values the new sound should behave like."""
    at = OSC_BASE + osc * OSC_STRIDE
    record = bytearray(probe.read(at, OSC_STRIDE))
    reference = probe.read(OSC_BASE + template * OSC_STRIDE, OSC_STRIDE)
    text = name.encode("latin1")[:15]
    record[:16] = text + bytes(16 - len(text))
    struct.pack_into("<H", record, 0x12, PCM_FIRST_WAVE + instrument)
    record[0x16:0x18] = reference[0x16:0x18]
    record[0x18:0x1E] = reference[0x18:0x1E]
    probe.uc.mem_write(at, bytes(record))


def cmd_demo(a):
    """An import, made by the probe from outside the firmware: at the end of the PCM load, a made-up 16-bit wave goes
    into free DSP memory with the firmware's own write function, the tables get an instrument (appended, or `--replace`
    an existing one), an oscillator record gets its name, and a pad plays it. What the voice sends is listed."""
    import machine
    waves = synthetic_waves()
    probe = Probe(load_payload(a.vsb), blank_synth_flash(machine, build_bank(waves)))
    if not probe.run_to_pc(FUNCS["pcm_loaded"], 3.0):
        raise SystemExit("the PCM load did not end")
    rate, root, length = 32000, 60, 1500
    pcm = [int(round(12000 * math.sin(2 * math.pi * 11 * i / length))) for i in range(length)]
    data = b"".join(struct.pack("<h", v) for v in pcm)
    data += bytes(-len(data) % 32)
    count = probe.u32(RAM["count_instruments"])
    end_of_data = max(r[0] + r[2] + 2 for r in (probe.chain(PCM_FIRST_WAVE + i)["smpr"] for i in range(count)))
    target = (end_of_data + 0x1F) & ~0x1F
    buffer = 0xC0140000
    probe.uc.mem_write(buffer, data)
    port = probe.call_here(FUNCS["dsp_port"])
    probe.call_here(FUNCS["dsp_write"], port, target, buffer, len(data) // 2)
    word = pitch_word(root, rate)
    end = 2 * length - 2
    if a.replace is not None:
        instrument = a.replace
        c = probe.chain(PCM_FIRST_WAVE + instrument)
        probe.set_smpr(c["sample"], start=target, loop=end, end=end, flags=ONE_SHOT | 0x34)
        probe.set_pitch_word(c["layer"], word)
        osc = instrument                       # in the made-up bank, instrument n is the n-th record of the table
    else:
        instrument = append_instrument(probe, "IMPORT1", target, end, end, ONE_SHOT | 0x34, word)
        osc = a.osc
    repoint_osc(probe, osc, a.name, instrument)
    probe.leave()
    probe.run_to(3.0)
    probe.select_osc(osc)
    note = probe.press_pad()
    wave_id = PCM_FIRST_WAVE + instrument
    report = {"mode": "replace" if a.replace is not None else "append", "instrument": instrument, "osc": osc, "wave": wave_id,
              "counts_after": probe.tables()["counts"], "chain_after": probe.chain(wave_id), "target": hex(target),
              "pitch_word_written": hex(word), "dsp_wave_bytes": len(data), "dsp_has_the_wave": probe.dsp_bytes(target, len(data)) == data,
              "voice": note}
    if a.png:
        probe.m.png(a.png)
    print(json.dumps(report, indent=1))


def wav_file(values, rate):
    data = b"".join(struct.pack("<h", v * 16) for v in values)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


def cmd_selftest(a):
    values = sine(333, 7)
    assert unpack12(pack12(values), len(values)) == values
    bank = build_bank(synthetic_waves())
    info = parse_bank(bank)
    assert info["sum16"] == 0 and info["counts_equal"] and info["waves"]["count"] == 4
    print(json.dumps({"ok": True, "waves": info["waves"], "sections": {k: v["at"] for k, v in info["sections"].items()}}, indent=1))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("bank")
    s.add_argument("file")
    s.set_defaults(fn=cmd_bank)
    s = sub.add_parser("osc")
    s.add_argument("vsb")
    s.set_defaults(fn=cmd_osc)
    s = sub.add_parser("boot")
    s.add_argument("vsb")
    s.add_argument("--bank", help="own bank: a flash dump, a PCM.VSB or an 8 MiB bank")
    s.add_argument("--synthetic", action="store_true", help="a made-up bank of four sines instead")
    s.add_argument("--seconds", type=float, default=7.0)
    s.add_argument("--held", type=lambda x: int(x, 0), default=0, help="buttons held at power-on as a bit mask, 0x2000 is EXIT")
    s.add_argument("--voice", type=int, help="oscillator index to select before the pad is pressed")
    s.add_argument("--relocate", action="store_true", help="after the voice: move the wave to the end of the DSP data, press again, list what changed")
    s.set_defaults(fn=cmd_boot)
    s = sub.add_parser("fatfs")
    s.add_argument("vsb")
    s.add_argument("--synthetic", action="store_true")
    s.add_argument("--seconds", type=float, default=3.0)
    s.set_defaults(fn=cmd_fatfs)
    s = sub.add_parser("demo")
    s.add_argument("vsb")
    s.add_argument("--osc", type=int, default=334, help="oscillator record to repoint when appending (334 is OCT-SAW, a twin of DUAL-SAW)")
    s.add_argument("--replace", type=int, help="instead of appending, replace this instrument (0 to 3 are the made-up ones)")
    s.add_argument("--name", default="IMPORT 1")
    s.add_argument("--png")
    s.set_defaults(fn=cmd_demo)
    s = sub.add_parser("selftest")
    s.set_defaults(fn=cmd_selftest)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
