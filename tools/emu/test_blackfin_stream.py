# SPDX-License-Identifier: GPL-3.0-or-later
import struct
import unittest
from types import SimpleNamespace

from blackfin_backend import BackendError, boot_blocks
from dsp_model import DspModel


def header(flags, address=0x1000, size=0, argument=0):
    data = bytearray(struct.pack('<IIII', 0xAD000000 | flags, address, size, argument))
    checksum = 0
    for byte in data:
        checksum ^= byte
    data[2] = checksum
    return bytes(data)


class Stream(unittest.TestCase):
    def test_normal_fill_init_and_final_blocks_preserve_their_meaning(self):
        data = header(0x800, size=2) + b'ab' + header(0x100, size=4096, argument=0x12345678)
        data += header(0x8000, size=2) + b'cd'
        blocks = boot_blocks(data)
        self.assertEqual([b[0] for b in blocks], [0x800, 0x100, 0x8000])
        self.assertEqual(blocks[1][2:], (4096, 0x12345678, b''))
        self.assertEqual(blocks[2][-1], b'cd')

    def test_bad_checksums_sizes_and_missing_final_are_rejected(self):
        for data in (b'', header(0), header(0x8000)[:-1], header(0x8000, size=1),
                     header(0x8000, address=0xFFFFFFFE, size=4)+b'abcd',
                     header(0x8100, size=1 << 27), bytes(16)):
            with self.subTest(length=len(data)), self.assertRaises(BackendError):
                boot_blocks(data)

    def test_model_cannot_silently_replace_a_real_backend(self):
        machine = SimpleNamespace(dsp_backend=object())
        with self.assertRaisesRegex(ValueError, 'Blackfin'):
            DspModel.attach(machine)
        with self.assertRaisesRegex(ValueError, 'Blackfin'):
            DspModel(machine)

    def test_boot_failure_does_not_publish_cpu_success(self):
        from machine import Machine
        class Failed:
            def boot(self, _):
                raise BackendError('DSP not ready')
        machine = Machine.__new__(Machine)
        registers = {0: 0, 1: 0xC0100000, 2: 16, 14: 0xC0000100}
        machine.A = SimpleNamespace(UC_ARM_REG_R0=0, UC_ARM_REG_R1=1, UC_ARM_REG_R2=2,
                                    UC_ARM_REG_LR=14, UC_ARM_REG_PC=15)
        machine.uc = SimpleNamespace(reg_read=registers.__getitem__, reg_write=registers.__setitem__,
                                     mem_read=lambda *_: bytes(16))
        machine.dsp_backend = Failed()
        machine.dsp_uploads, machine.time_ns = [], 0
        with self.assertRaisesRegex(BackendError, 'not ready'):
            machine._dsp_upload()
        self.assertEqual(registers[0], 0)
        self.assertNotIn(15, registers)
        self.assertEqual(machine.dsp_uploads, [])


if __name__ == '__main__':
    unittest.main()
