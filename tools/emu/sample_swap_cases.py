# SPDX-License-Identifier: GPL-2.0-only
"""Run native Sampler allocation and deletion with synthetic, isolated tables."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

import firmware
import sampleset

BASE, HEADER = 0xC0000000, 0x100
NAMES, PLAYBACK, META = 0xC047B080, 0xC0362EE8, 0xC036AD88
STRIDE, CURSOR = 0x45C, 0xC00F9C80
RESERVE, DELETE, FREE = 0xC004EDF0, 0xC004E558, 0xC004E218
FACTORY_END, LIMIT = 0x00365EC0, 0x01C65EC0
SCRATCH, STACK, RETURN = 0xC3000000, 0xC3010000, 0xC3011000


class Allocation:
    def __init__(self, payload):
        import unicorn
        from unicorn import arm_const as reg

        self.reg = reg
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.cpu.mem_map(BASE, 0x500000)
        self.cpu.mem_write(BASE, payload)
        self.cpu.mem_map(SCRATCH, 0x20000)
        self.word(CURSOR, FACTORY_END)
        for index in range(500, 503):
            self.cpu.mem_write(NAMES + index * 32 + 30, struct.pack('<H', index + 50))
            self.cpu.mem_write(0xC035738C + index * 32 + 16, struct.pack('<H', index))
            self.cpu.mem_write(0xC035F06C + index * 16 + 8, struct.pack('<H', index))
            self.cpu.mem_write(0xC0350644 + index * 8 + 2, struct.pack('<H', index))
            self.cpu.mem_write(META + index * STRIDE + 22, struct.pack('<H', index))

    def word(self, address, value=None):
        if value is not None:
            self.cpu.mem_write(address, struct.pack('<I', value))
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def call(self, address, arg=0):
        self.cpu.reg_write(self.reg.UC_ARM_REG_CPSR, 0x13)
        self.cpu.reg_write(self.reg.UC_ARM_REG_SP, STACK)
        self.cpu.reg_write(self.reg.UC_ARM_REG_LR, RETURN)
        self.cpu.reg_write(self.reg.UC_ARM_REG_R0, arg)
        self.cpu.emu_start(address, RETURN, timeout=2_000_000, count=100_000)
        if self.cpu.reg_read(self.reg.UC_ARM_REG_PC) != RETURN:
            raise RuntimeError(f'{address:#x} did not return')
        return self.cpu.reg_read(self.reg.UC_ARM_REG_R0)

    def reserve(self, index, length):
        descriptor = bytearray(sampleset.esli(index, f'synthetic{index}', length // 2))
        struct.pack_into('<H', descriptor, 20, index + 50)
        self.cpu.mem_write(SCRATCH, bytes(descriptor))
        result = self.call(RESERVE, SCRATCH)
        return result, self.word(SCRATCH + 0x38)

    def active(self, index):
        return self.cpu.mem_read(META + index * STRIDE + 11, 1)[0]


def run(path):
    data = path.read_bytes()
    if len(data) != HEADER + 0x200000:
        raise ValueError('Expected a 0x100-byte header and 2-MiB payload')
    payload = data[HEADER:]
    profile = firmware.identify(payload)
    if profile.build not in ('stock', 'hacktribe') or profile.moved:
        raise ValueError('Only the measured Sampler 2.02 addresses are supported')
    m = Allocation(payload)
    checks = []

    def check(name, ok, **values):
        checks.append(dict(id=name, ok=bool(ok), **values))
        if not ok:
            raise AssertionError(json.dumps(checks))

    result, offset = m.reserve(500, 1024)
    check('first-appends', result == 1 and offset == FACTORY_END and m.active(500) == 1
          and m.word(PLAYBACK + 500 * 16) == offset, offset=offset)
    result, offset = m.reserve(501, 2048)
    check('second-appends', result == 1 and offset == FACTORY_END + 1024
          and m.word(CURSOR) == FACTORY_END + 3072, offset=offset)
    before = bytes(m.cpu.mem_read(META + 501 * STRIDE, STRIDE))
    result, _ = m.reserve(501, 512)
    check('occupied-refused', result == 0 and m.word(CURSOR) == FACTORY_END + 3072
          and bytes(m.cpu.mem_read(META + 501 * STRIDE, STRIDE)) == before)
    result = m.call(DELETE, 500)
    check('interior-delete-keeps-cursor', result == 1 and m.active(500) == 0
          and m.word(CURSOR) == FACTORY_END + 3072, cursor=m.word(CURSOR))
    result, offset = m.reserve(500, 512)
    check('hole-not-reused', result == 1 and offset == FACTORY_END + 3072
          and m.word(CURSOR) == FACTORY_END + 3584, offset=offset)
    result = m.call(DELETE, 500)
    check('tail-delete-rewinds', result == 1 and m.word(CURSOR) == FACTORY_END + 3072)
    result = m.call(DELETE, 501)
    check('old-hole-still-lost', result == 1 and m.word(CURSOR) == FACTORY_END + 1024
          and m.active(500) == m.active(501) == 0, cursor=m.word(CURSOR))
    m = Allocation(payload)
    m.word(CURSOR, LIMIT - 1024)
    full, _ = m.reserve(500, 1024)
    free = m.call(FREE)
    refused, _ = m.reserve(501, 32)
    check('software-boundary', full == 1 and free == 0 and refused == 0 and m.word(CURSOR) == LIMIT,
          limit=LIMIT, free=free)
    return dict(hardware_contact=False, build=profile.build, dsp_model='not used',
                fixture='synthetic identity mappings, no boot, no PCM transfers',
                firmware_sha256=hashlib.sha256(data).hexdigest(), checks=checks)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vsb', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.vsb), indent=2))
