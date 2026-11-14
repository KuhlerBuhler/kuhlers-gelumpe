# SPDX-License-Identifier: GPL-3.0-or-later
"""BF52x HOSTDP tests with generated values and instructions."""
import os
import struct
import unittest

from blackfin_backend import BlackfinBackend, BackendError

WORKER = os.environ.get('BFIN_WORKER')
CONTROL, STATUS, TIMEOUT = 0xFFC03400, 0xFFC03404, 0xFFC03408
SIC_ISR1 = 0xFFC00160


@unittest.skipUnless(WORKER, 'build the GNU Blackfin worker and set BFIN_WORKER')
class HostPort(unittest.TestCase):
    def setUp(self):
        self.backend = BlackfinBackend(WORKER, operating=True)
        self.addCleanup(self.backend.close)

    def read(self, address):
        return struct.unpack('<H', self.backend.read(address, 2))[0]

    def write(self, address, value):
        self.backend.write(address, struct.pack('<H', value))

    def pending(self):
        return struct.unpack('<I', self.backend.read(SIC_ISR1, 4))[0]

    def test_reset_values_are_device_state_not_unmapped_memory(self):
        self.assertEqual([self.read(a) for a in (CONTROL, STATUS, TIMEOUT)], [0x400, 0xC, 0])

    def test_status_has_read_only_set_and_clear_bits(self):
        self.write(STATUS, 0xFFFF)
        self.assertEqual(self.read(STATUS), 0x1C)
        self.write(STATUS, 0)
        self.assertEqual(self.read(STATUS), 0xC)

    def test_enable_override_and_timeout_enable_update_status(self):
        self.write(CONTROL, 0x345)
        self.assertEqual(self.read(STATUS), 0x8C)
        self.write(CONTROL, 0x3E5)
        self.assertEqual(self.read(STATUS), 0x20C)
        self.write(CONTROL, 0x3C5)
        self.assertEqual(self.read(STATUS), 0x28C)

    def test_soft_reset_preserves_control_and_timeout(self):
        self.write(TIMEOUT, 0xFFFF)
        self.write(CONTROL, 0x488)
        self.assertEqual(self.read(CONTROL), 0x480)
        self.assertEqual(self.read(STATUS), 0x20C)
        self.assertEqual(self.read(TIMEOUT), 0x7FF)

    def test_native_halfword_store_uses_the_device_semantics(self):
        # LDSTpmod: store low halfword, P0 as pointer and index, R0 as data.
        instruction = 0x8000 | (1 << 11) | (1 << 9)
        self.backend.write(0x1000, struct.pack('<2H', instruction, 0x2000))
        for number, value in ((8, STATUS), (0, 0x10), (53, 0x1000)):
            self.backend.set_register(number, value)
        self.backend.run(1)
        self.assertEqual(self.read(STATUS), 0x1C)
        self.assertEqual(self.backend.register(47) & 63, 0)

    def test_status_interrupt_stays_asserted_until_all_sources_are_cleared(self):
        self.write(CONTROL, 0x3C5)
        self.backend.host_event(1)
        self.backend.host_event(2)
        self.assertEqual(self.read(STATUS) & 0x60, 0x60)
        self.assertTrue(self.pending() & (1 << 17))
        self.write(STATUS, 0x40)
        self.assertEqual(self.read(STATUS) & 0x60, 0x20)
        self.assertTrue(self.pending() & (1 << 17))
        self.write(STATUS, 0x20)
        self.assertFalse(self.pending() & (1 << 17))

    def test_read_done_interrupt_is_cleared_by_its_status_bit(self):
        self.write(CONTROL, 0x345)
        self.backend.host_event(3)
        self.assertTrue(self.pending() & (1 << 18))
        self.assertEqual(self.read(STATUS) & 0x8000, 0x8000)
        self.write(STATUS, 0x8000)
        self.assertFalse(self.pending() & (1 << 18))

    def test_unsupported_event_closes_the_session(self):
        with self.assertRaises(BackendError):
            self.backend.host_event(4)
        self.assertIsNone(self.backend.process)

    def test_reset_clears_latched_interrupts(self):
        self.write(CONTROL, 0x3C5)
        for event in (1, 2, 3):
            self.backend.host_event(event)
        self.assertTrue(self.pending() & (3 << 17))
        self.write(CONTROL, 0x3CD)
        self.assertEqual(self.read(CONTROL), 0x3C5)
        self.assertEqual(self.read(STATUS), 0x20C)
        self.assertFalse(self.pending() & (3 << 17))

    def test_word_writes_are_rejected_instead_of_truncating(self):
        with self.assertRaises(BackendError):
            self.backend.write(CONTROL, struct.pack('<I', 0x345))

    def test_word_reads_zero_extend_the_register(self):
        self.assertEqual(self.backend.read(CONTROL, 4), struct.pack('<I', 0x400))

    def test_route_change_recomputes_an_already_pending_source(self):
        self.backend.write(0xFFC00158, struct.pack('<I', 2 << 4))
        self.backend.write(0xFFC0014C, struct.pack('<I', 1 << 17))
        self.write(CONTROL, 0x345)
        self.backend.host_event(1)
        latched = lambda: struct.unpack('<I', self.backend.read(0xFFE0210C, 4))[0]
        self.assertTrue(latched() & (1 << 9))
        self.backend.write(0xFFC00158, struct.pack('<I', 3 << 4))
        self.assertTrue(latched() & (1 << 10))

    def test_native_interrupt_handler_acknowledges_host_irq(self):
        entry, main, handler, count = 0x1000, 0x1100, 0x1200, 0x1300
        code = (0xE108, count, 0xE148, 0, 0x6008, 0x9300,
                0xE108, STATUS & 65535, 0xE148, STATUS >> 16,
                0xE120, 0x40, 0x8A00, 0x0011)
        self.backend.write(handler, struct.pack('<14H', *code))
        self.backend.write(entry, struct.pack('<H', 0x0011))
        self.backend.write(main, struct.pack('<H', 0x2000))
        self.backend.write(count, bytes(4))
        for address, value in ((0xFFE02024, handler), (0xFFC00158, 2 << 4),
                               (0xFFC0014C, 1 << 17), (0xFFE02104, 1 << 9)):
            self.backend.write(address, struct.pack('<I', value))
        self.backend.set_register(49, main)
        self.backend.set_register(53, entry)
        self.write(CONTROL, 0x345)
        self.backend.host_event(1)
        result = self.backend.run(200, until=main)
        self.assertTrue(result['reached'])
        self.assertEqual(self.backend.read(count, 4), struct.pack('<I', 1))
        self.assertFalse(self.pending() & (1 << 17))
        self.assertFalse(self.read(STATUS) & 0x40)
