# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe generated CPU and DMA accesses without changing memory or time."""
import struct
import unittest

from blackfin_backend import BlackfinBackend
from test_blackfin_backend import WORKER, ENTRY, DATA, program


@unittest.skipUnless(WORKER, 'build the private GNU worker and set BFIN_WORKER')
class MemoryWatch(unittest.TestCase):
    def setUp(self):
        self.backend = BlackfinBackend(WORKER, operating=True)
        self.addCleanup(self.backend.close)
        self.backend.write(ENTRY, program()[:-2] + struct.pack('<2H', 0x9100, 0x2000))
        self.backend.set_register(53, ENTRY)

    def write(self, address, value, size=2):
        self.backend.write(address, value.to_bytes(size, 'little'))

    def test_cpu_accesses_overlap_the_window_and_debug_reads_are_excluded(self):
        self.backend.watch_memory(DATA + 1, 2)
        self.backend.run(7)
        clock = self.backend.clock_status()
        report = self.backend.memory_accesses()
        self.backend.read(DATA, 4)
        self.assertEqual(self.backend.memory_accesses(), report)
        self.assertEqual(self.backend.clock_status(), clock)
        for kind in ('cpu_read', 'cpu_write'):
            self.assertEqual(report[kind]['accesses'], 1)
            self.assertEqual(report[kind]['bytes'], 2)
            self.assertEqual(report[kind]['address'], DATA)
            self.assertEqual(report[kind]['width'], 4)
        self.assertEqual(report['dma_read']['accesses'], 0)
        self.assertEqual(report['dma_write']['accesses'], 0)

    def test_reconfiguration_resets_counters_and_zero_length_disables_them(self):
        self.backend.watch_memory(DATA, 4)
        self.backend.run(7)
        self.backend.watch_memory(DATA, 0)
        self.backend.set_register(53, ENTRY)
        self.backend.run(7)
        self.assertTrue(all(row['accesses'] == 0 for row in self.backend.memory_accesses().values()))

    def test_unmapped_cpu_write_does_not_count_as_committed_data(self):
        address = 0x10000000
        self.backend.write(ENTRY, program(address))
        self.backend.watch_memory(address, 4)
        self.backend.run(6)
        self.assertNotEqual(self.backend.register(47), 0)
        self.assertEqual(self.backend.memory_accesses()['cpu_write']['accesses'], 0)

    def test_mdma_overlap_records_both_halves_of_a_crossing_store(self):
        self.backend.write(ENTRY, struct.pack('<H', 0x2000))
        source, destination = 0x30000, DATA - 2
        self.backend.write(source, bytes(4))
        self.backend.write(destination, b'\xA5' * 6)
        self.backend.watch_memory(DATA, 2)
        for base, start, config in ((0xFFC00F40, source, 5), (0xFFC00F00, destination, 7)):
            self.write(base + 4, start, 4)
            self.write(base + 0x10, 2)
            self.write(base + 0x14, 2)
            self.write(base + 8, config)
        self.backend.run(10)
        self.assertEqual(self.backend.read(destination, 6), bytes(4) + b'\xA5\xA5')
        row = self.backend.memory_accesses()['dma_write']
        self.assertEqual((row['accesses'], row['bytes'], row['address'], row['width']), (1, 2, destination, 4))
        self.assertEqual(row['origin'], 0xFFC00F00)

    def test_hostdp_dma_writes_and_reads_are_observed(self):
        self.backend.write(ENTRY, struct.pack('<H', 0x2000))
        self.write(0xFFC03400, 0x345)
        self.backend.watch_memory(DATA, 32)
        for word in (0xAB, DATA & 65535, DATA >> 16, 16, 2, 0, 0):
            self.backend.host_control(word)
        self.backend.run(3)
        for word in range(16):
            self.backend.host_write(word)
        self.backend.run(20)
        self.write(0xFFC00C68, 1)
        self.write(0xFFC03404, 8)
        for word in (0xA9, DATA & 65535, DATA >> 16, 16, 2, 0, 0):
            self.backend.host_control(word)
        self.backend.run(20)
        self.assertEqual([self.backend.host_read() for _ in range(16)], list(range(16)))
        report = self.backend.memory_accesses()
        self.assertEqual(report['dma_read']['bytes'], 32)
        self.assertEqual(report['dma_write']['bytes'], 32)
        self.assertEqual(report['cpu_read']['accesses'], 0)
        self.assertEqual(report['cpu_write']['accesses'], 0)

    def test_invalid_windows_fail_before_contacting_worker(self):
        for address, size in ((-1, 2), (0xFFFFFFFF, 2), (DATA, -1), (DATA, 1 << 32)):
            with self.subTest(address=address, size=size):
                with self.assertRaises(ValueError):
                    self.backend.watch_memory(address, size)
