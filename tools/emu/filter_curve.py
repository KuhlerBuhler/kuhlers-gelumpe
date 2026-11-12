# SPDX-License-Identifier: GPL-2.0-only
"""The filter coefficients the CPU sends with command 0x30, recomputed outside the running machine
(docs/messungen/2026-11-12-dsp-modell.md).

The cutoff dispatcher (Hacktribe and red 0xC0094A6C, blue 0xC00825DC) maps the part's filter type byte through the mapper's
byte table to a kind 0..20 and jumps through a table of 20 blocks; each block calls one coefficient function
f(cutoff, resonance, out) with both positions in 8.8 (knob << 8 with filter EG and MOD at 0) and three 1.31 words in out.
OFF (type 0) lands on the default block, which calls none: Hacktribe and red then send zeros, blue returns without command
0x30 (its default block is the epilogue, add sp, sp; pop), so the DSP keeps the last words. Everything is found by pattern, so the same code
serves all three builds; the tables stay in the firmware.

coefficients() runs the chosen function on a separate Unicorn holding only the payload. lpf() is the LPF function
(Hacktribe 0xC0093EB4) written out in Python, to check that run against the algorithm as read.
"""
import re
import struct

from unicorn import UC_ARCH_ARM, UC_MODE_ARM, Uc
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP

BASE = 0xC0000000
# the filter-type mapper: cmp r0, #0x10; ldrle r3, [pc, #8]; ldrble r0, [r3, r0]; movgt r0, #0x14; bx lr; its table follows
MAPPER = bytes.fromhex("100050e308309fd50000d3d71400a0c31eff2fe1")
SWITCH = bytes.fromhex("130050e300f19f97")      # cmp r0, #0x13; ldrls pc, [pc, r0, lsl #2]
# the LPF function's first instructions: cmp r0, #0; push {r4, lr}; beq; cmp r0, #0x7f00; its literal pool sits at +0x78:
# value at the top, cutoff table (u32), value at 0, resonance table (u32), resonance compensation table (s16)
LPF_START = bytes.fromhex("000050e310402de90e00000a7f0c50e3")
LPF_POOL = 0x78
TOP = 0x7F00
STACK, OUT, STOP = 0x17000, 0x18000, 0x10000


def _branch(payload, at):
    w = struct.unpack_from("<I", payload, at - BASE)[0]
    assert w >> 24 in (0xEA, 0xEB), hex(at)
    return at + 8 + (((w & 0xFFFFFF) ^ 0x800000) - 0x800000) * 4


def _is_bl(payload, at, target):
    return payload[at - BASE + 3] == 0xEB and _branch(payload, at) == target


class FilterCurve:
    def __init__(self, payload):
        self.payload = bytes(payload)
        off = payload.find(MAPPER)
        assert off >= 0 and payload.find(MAPPER, off + 1) < 0, "filter-type mapper not found once"
        mapper = BASE + off
        table = struct.unpack_from("<I", payload, off + len(MAPPER))[0]
        self.kinds = bytes(payload[table - BASE:table - BASE + 17])
        switch = [BASE + m.start() for m in re.finditer(re.escape(SWITCH), payload)
                  if any(_is_bl(payload, BASE + m.start() - 4 * k, mapper) for k in range(1, 4))]
        assert len(switch) == 1, "cutoff dispatcher not found once"
        self.switch = switch[0]
        jump, default = self.switch + 12, _branch(payload, self.switch + 8)
        self.sends_off = struct.unpack_from("<I", payload, default - BASE)[0] >> 12 != 0xE28DD    # not add sp, sp, #n
        self.functions = {}
        for kind in range(20):
            block = struct.unpack_from("<I", payload, jump + 4 * kind - BASE)[0]
            calls = [block + 4 * k for k in range(6) if payload[block + 4 * k - BASE + 3] == 0xEB]
            self.functions[kind] = _branch(payload, calls[0]) if block != default and calls else None
        lpf = payload.find(LPF_START)
        self.lpf_at = BASE + lpf if lpf >= 0 else None
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(BASE, (len(payload) + 0xFFFF) & ~0xFFFF)
        self.uc.mem_write(BASE, self.payload)
        self.uc.mem_map(STOP, 0x10000)

    def function(self, filter_type):
        """The coefficient function for a filter type byte (0..16), None for OFF."""
        return self.functions.get(self.kinds[filter_type] if filter_type <= 16 else 20)

    def coefficients(self, filter_type, cutoff, resonance):
        """The three words of command 0x30 for positions in 8.8; for OFF (0, 0, 0), or None where OFF sends no 0x30."""
        fn = self.function(filter_type)
        if fn is None:
            return (0, 0, 0) if self.sends_off else None
        uc = self.uc
        uc.mem_write(OUT, bytes(12))
        for reg, v in ((UC_ARM_REG_R0, cutoff), (UC_ARM_REG_R1, resonance), (UC_ARM_REG_R2, OUT),
                       (UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, STOP)):
            uc.reg_write(reg, v)
        uc.emu_start(fn, STOP, count=10000)
        return struct.unpack("<3I", uc.mem_read(OUT, 12))

    def _u32(self, at):
        return struct.unpack_from("<I", self.payload, at - BASE)[0]

    def lpf(self, cutoff, resonance):
        """The LPF function's three words, computed here: the cutoff table interpolated in 1/256 steps, the resonance word
        from its table, the compensation word as a signed half-word shifted up by 14."""
        top, table, bottom, res, comp = (self._u32(self.lpf_at + LPF_POOL + 4 * i) for i in range(5))
        if cutoff == 0:
            c = bottom
        elif cutoff >= TOP:
            c = top
        else:
            i, f = cutoff >> 8, cutoff & 0xFF
            lo = self._u32(table + 4 * i)
            c = lo if f == 0 else (lo + (((self._u32(table + 4 * i + 4) - lo) & 0xFFFFFFFF) >> 8) * f) & 0xFFFFFFFF
        r = resonance >> 8
        half = struct.unpack_from("<h", self.payload, comp + 2 * r - BASE)[0]
        return (c, self._u32(res + 4 * r), (half << 14) & 0xFFFFFFFF)
