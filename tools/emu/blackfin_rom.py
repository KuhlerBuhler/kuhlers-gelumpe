# SPDX-License-Identifier: GPL-3.0-or-later
"""BF52x ROM API models, limited to normal clock control and healthy OTP.

BF52x Hardware Reference 18-31 to 18-33 and 4-25; Linux asm/bfrom.h.
PLL settling time, reset, sleep and OTP faults are not modeled.
"""
from collections import deque
import struct

from blackfin_backend import BackendError

SYSCONTROL = 0xEF000038
FIELDS = ((0x10, 0xFFC00008), (0x100, 0xFFC00000), (0x200, 0xFFC00004),
          (0x400, 0xFFC00010), (0x800, 0xFFC0000C))


class SysControl:
    def __init__(self):
        self.calls = 0
        self.events = deque(maxlen=64)

    def handle(self, backend, registers):
        flags, pointer = registers['R0'], registers['R1']
        target = registers['RETS']
        if registers['PC'] != SYSCONTROL:
            raise BackendError('unknown Blackfin ROM entry')
        if (flags & ~0xF31 or not flags & 0xF10 or registers['R2']
                or pointer & 1 or pointer + 10 > 1 << 32):
            raise BackendError('unsupported SysControl arguments')
        if target & 1 or 0xEF000000 <= target < 0xF0000000:
            raise BackendError('unsupported SysControl return address')
        writing = bool(flags & 1)
        if writing and flags & 0x800:
            raise BackendError('SysControl PLL_STAT is read-only')
        values = struct.unpack('<5H', backend.read(pointer, 10))
        if writing and ((flags & 0x100 and values[1] & 0x2A)
                        or (flags & 0x10 and values[0] & 0x3000 != 0x3000)):
            raise BackendError('SysControl power mode is not implemented')
        updates = []
        for index, (flag, address) in enumerate(FIELDS):
            if not flags & flag:
                continue
            if writing:
                value = values[index]
                backend.write(address, struct.pack('<H', value))
                if backend.read(address, 2) != struct.pack('<H', value):
                    raise BackendError('SysControl MMR write did not take effect')
            else:
                value, = struct.unpack('<H', backend.read(address, 2))
                backend.write(pointer+index*2, struct.pack('<H', value))
            updates.append(dict(address=address, value=value))
        backend.set_register(0, 0)
        backend.set_register(53, target)
        self.calls += 1
        self.events.append(dict(function='bfrom_SysControl', flags=flags, settings=pointer,
                                writing=writing, mmrs=updates, result=0, otp='modeled success'))

    def report(self):
        return dict(calls=self.calls, events=list(self.events), otp='modeled success',
                    atomic_transitions=True, hardware_timing=False)
