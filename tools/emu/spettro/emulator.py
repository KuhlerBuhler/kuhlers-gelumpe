"""Offline harness for the ARM scope core. This module has no MIDI or device access."""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.patch.spettro import HERE as SOURCE, source
from tools.patch.arm import assemble
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_CPSR, UC_ARM_REG_PC

ORIGIN, CTX, FB, STACK, STOP = 0xC1000000, 0xC1200100, 0xC1210100, 0xC1221000, 0xC1230000
MAGIC, DSP_STATE, RING, RING_BYTES, TICKS = 0x53434F50, 0xFF9031D0, 0x01C722A0, 19200, 0xC06A292C
READ, BEGIN, END = 0xC00141F8, 0xC0014368, 0xC00143E4
OK, OFF, BUSY, FILLING, LOST, STALE, BAD_ARG = range(7)
PCM, FRAME_A, FRAME_B, SIZE = 128, 4224, 5248, 6784


def build():
    return assemble(source(), origin=ORIGIN)


def pack(samples, other=None):
    other = other if other is not None else samples
    return b"".join(struct.pack("<I", (a & 65535) | ((b & 65535) << 16)) for a, b in zip(samples, other))


class ScopeMachine:
    """Execute our ARM, substituting only the native DSP transfer and control calls."""
    def __init__(self):
        self.code = build()
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        for address, size in [(0xC0000000, 0x800000), (ORIGIN, 0x10000),
                              (0xC1200000, 0x40000)]:
            self.uc.mem_map(address, size)
        for address, data in self.code.sections:
            self.uc.mem_write(address, data)
        self.uc.mem_write(CTX - 16, b"\xA6" * 16 + bytes(SIZE) + b"\xB7" * 16)
        self.uc.mem_write(FB - 16, b"\xC8" * 16 + bytes(1024) + b"\xD9" * 16)
        self.state = [0, RING_BYTES, RING, 0] + [0] * 7
        self.ring = bytearray(RING_BYTES)
        self.calls, self.writes = [], []
        self.after_pcm = None
        self.cycles = 0
        self.tick(1000)
        self.uc.hook_add(UC_HOOK_CODE, self._step)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self._write)

    def word(self, address, value=None):
        if value is not None:
            self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))
        return struct.unpack("<I", bytes(self.uc.mem_read(address, 4)))[0]

    def tick(self, value):
        self.word(TICKS, value)

    def _write(self, uc, access, address, size, value, data):
        self.writes.append((address, size))

    def _step(self, uc, address, size, data):
        self.cycles += 1
        if address not in (READ, BEGIN, END):
            return
        args = [uc.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]
        if address == READ:
            source, destination, count, width = args
            self.calls.append(("read", source, count * 2))
            if width != 2:
                raise AssertionError("DSP transfer width changed")
            if source == DSP_STATE and count == 22:
                payload = struct.pack("<11I", *self.state)
            else:
                offset, amount = source - RING, count * 2
                if not (0 <= offset < RING_BYTES and 0 < amount <= RING_BYTES - offset):
                    raise AssertionError("DSP read escaped the circular buffer")
                payload = bytes(self.ring[offset:offset + amount])
            uc.mem_write(destination, payload)
            if source != DSP_STATE and self.after_pcm:
                self.after_pcm(self)
        elif address == BEGIN:
            selector = args[0]
            if not 1 <= selector <= 24:
                raise AssertionError("invalid native source")
            self.calls.append(("begin", selector))
            self.state[0], self.state[2] = 1, RING
            self.state[3] = (0xFF90197C + (selector - 1) * 0x118 if selector <= 16
                             else 0xFF901A98 + (selector - 17) * 0x230)
        elif address == END:
            self.calls.append(("end",))
            self.state[0] = 0
        else:
            return
        # Return values from the original void wrappers are deliberately unspecified.
        for i in range(4):
            uc.reg_write(UC_ARM_REG_R0 + i, 0xBAD)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def call(self, symbol, *args):
        self.cycles = 0
        self.uc.reg_write(UC_ARM_REG_CPSR, 0x13)
        for i, value in enumerate(args):
            self.uc.reg_write(UC_ARM_REG_R0 + i, value & 0xFFFFFFFF)
        self.uc.reg_write(UC_ARM_REG_SP, STACK)
        self.uc.reg_write(UC_ARM_REG_LR, STOP)
        self.uc.emu_start(self.code.symbols[symbol], STOP, count=300000)
        if self.uc.reg_read(UC_ARM_REG_PC) != STOP:
            raise AssertionError(f"{symbol} did not finish within the instruction bound")
        if self.uc.reg_read(UC_ARM_REG_SP) != STACK:
            raise AssertionError("unbalanced stack")
        return self.uc.reg_read(UC_ARM_REG_R0)

    def request(self, enabled=1, part=0, stereo=0, channel=0, shift=11, freeze=0):
        for offset, value in [(36, enabled), (40, part), (44, stereo), (48, channel), (52, shift), (60, freeze)]:
            self.word(CTX + offset, value)

    def service(self):
        return self.call("scope_service", CTX)
