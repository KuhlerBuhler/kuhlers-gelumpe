# SPDX-License-Identifier: GPL-3.0-or-later
"""ROM API tests with generated instructions and register settings."""
import os
import struct
import unittest

from blackfin_backend import BlackfinBackend, BackendError
from blackfin_rom import SysControl

WORKER = os.environ.get('BFIN_WORKER')
ENTRY, DATA = 0x1000, 0x100000
MMRS = (0xFFC00008, 0xFFC00000, 0xFFC00004, 0xFFC00010, 0xFFC0000C)
FIELDS = (0x10, 0x100, 0x200, 0x400, 0x800)
VALUES = (0x30B0, 0x2A00, 5, 0x200, 0xA2)


@unittest.skipUnless(WORKER, 'build the GNU Blackfin worker and set BFIN_WORKER')
class SystemControl(unittest.TestCase):
    def setUp(self):
        self.rom = SysControl()
        self.backend = BlackfinBackend(WORKER, operating=True, rom=self.rom)
        self.addCleanup(self.backend.close)
        self.backend.write(DATA, struct.pack('<5H', *VALUES))

    def invoke(self, flags):
        backend = self.backend
        backend.write(ENTRY, struct.pack('<7H', 0xE108, 0x38, 0xE148, 0xEF00, 0x0060, 0x9308, 0x2000))
        for number, value in ((0, flags), (1, DATA), (2, 0), (9, DATA+32), (53, ENTRY)):
            backend.set_register(number, value)
        backend.write(DATA+32, bytes([255])*4)
        return backend.run(40, until=ENTRY+12)

    def settings(self):
        return struct.unpack('<5H', self.backend.read(DATA, 10))

    def mmrs(self):
        return tuple(struct.unpack('<H', self.backend.read(address, 2))[0] for address in MMRS)

    def registers(self, flags=0x711, **values):
        return dict(PC=0xEF000038, RETS=ENTRY, R0=flags, R1=DATA, R2=0, **values)

    def test_write_updates_selected_mmrs_and_returns_through_original_caller(self):
        before = self.mmrs()
        self.backend.set_register(7, 0x12345678)
        self.backend.set_register(13, 0x87654320)
        result = self.invoke(0x711)
        self.assertTrue(result['reached'])
        self.assertEqual(self.mmrs(), VALUES[:4]+before[4:])
        self.assertEqual(self.settings(), VALUES)
        self.assertEqual(self.backend.read(DATA+32, 4), bytes(4))
        self.assertEqual(self.backend.register(7), 0x12345678)
        self.assertEqual(self.backend.register(13), 0x87654320)
        self.assertEqual(self.rom.calls, 1)

    def test_read_updates_only_selected_halfwords_in_the_settings_structure(self):
        expected = self.mmrs()
        for mask in range(1, 32):
            with self.subTest(mask=mask):
                self.backend.write(DATA, struct.pack('<5H', *([0x1234]*5)))
                flags = sum(flag for index, flag in enumerate(FIELDS) if mask & (1 << index))
                self.invoke(flags)
                self.assertEqual(self.settings(), tuple(expected[i] if mask & (1 << i) else 0x1234 for i in range(5)))
                self.assertEqual(self.mmrs(), expected)

    def test_unsupported_requests_do_not_change_registers_or_settings(self):
        before = self.mmrs(), self.settings()
        for flags, reserved in ((0x713, 0), (0x751, 0), (0x811, 0), (0x711, 1), (0x10000, 0)):
            with self.subTest(flags=flags, reserved=reserved):
                registers = self.registers(flags)
                registers['R2'] = reserved
                with self.assertRaises(BackendError):
                    self.rom.handle(self.backend, registers)
                self.assertEqual((self.mmrs(), self.settings()), before)
                self.assertEqual(self.rom.calls, 0)

    def test_power_down_is_rejected_before_any_mmr_write(self):
        before = self.mmrs()
        for value in (0x2A02, 0x2A08, 0x2A20):
            self.backend.write(DATA+2, struct.pack('<H', value))
            with self.assertRaisesRegex(BackendError, 'power'):
                self.rom.handle(self.backend, self.registers())
            self.assertEqual(self.mmrs(), before)

    def test_return_into_rom_is_rejected_before_any_mmr_write(self):
        registers = self.registers()
        registers['RETS'] = 0xEF000038
        before = self.mmrs()
        with self.assertRaisesRegex(BackendError, 'return'):
            self.rom.handle(self.backend, registers)
        self.assertEqual(self.mmrs(), before)

    def test_unknown_rom_is_still_fatal_with_the_syscontrol_model(self):
        self.backend.set_register(53, 0xEF00007E)
        with self.assertRaisesRegex(BackendError, 'PC=0xef00007e'):
            self.backend.run(20)
        self.assertIsNone(self.backend.process)
