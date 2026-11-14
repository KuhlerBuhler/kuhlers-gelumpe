# SPDX-License-Identifier: GPL-3.0-or-later
"""Generated MDMA streams with unequal descriptor and row boundaries."""
import os
import struct
import unittest

from blackfin_backend import BlackfinBackend, BackendError

WORKER = os.environ.get('BFIN_WORKER')
SOURCE, DESTINATION = 0xFFC00F40, 0xFFC00F00
SRC, OTHER, DST = 0x30000, 0x31000, 0x40000


@unittest.skipUnless(WORKER, 'build the private GNU worker and set BFIN_WORKER')
class MemoryDMA(unittest.TestCase):
    def setUp(self):
        self.backend = BlackfinBackend(WORKER, operating=True)
        self.addCleanup(self.backend.close)
        self.backend.write(0x1000, struct.pack('<H', 0x2000))
        self.backend.set_register(53, 0x1000)
        self.backend.write(SRC, struct.pack('<4H', 0x1111, 0x2222, 0x3333, 0xDEAD))
        self.backend.write(OTHER, struct.pack('<H', 0xBBBB))
        self.backend.write(DST, b'\xA5' * 16)

    def write(self, address, value, size=2):
        self.backend.write(address, (value & ((1 << (8 * size)) - 1)).to_bytes(size, 'little'))

    def read(self, address, size=2):
        return int.from_bytes(self.backend.read(address, size), 'little')

    def configure(self, base, start, count, config, modify=2):
        self.write(base + 4, start, 4)
        self.write(base + 0x10, count)
        self.write(base + 0x14, modify)
        self.write(base + 8, config)

    def test_short_source_stalls_destination_and_resumes_only_after_rearming(self):
        self.configure(SOURCE, SRC, 1, 5)
        self.configure(DESTINATION, DST, 2, 7)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 4), struct.pack('<H', 0x1111) + b'\xA5\xA5')
        self.assertEqual(self.read(SOURCE + 0x30), 0)
        self.assertEqual(self.read(SOURCE + 0x28) & 9, 1)
        self.assertEqual(self.read(DESTINATION + 0x30), 1)
        self.assertEqual(self.read(DESTINATION + 0x28) & 9, 8)
        self.backend.run(2000)
        self.assertEqual(self.backend.read(DST + 2, 2), b'\xA5\xA5')
        self.write(SOURCE + 8, 0)
        self.write(SOURCE + 0x28, 1)
        self.configure(SOURCE, OTHER, 1, 5)
        self.backend.run(2000)
        self.assertEqual(self.backend.read(DST, 6), struct.pack('<2H', 0x1111, 0xBBBB) + b'\xA5\xA5')
        self.assertEqual(self.read(DESTINATION + 0x28) & 9, 1)

    def test_source_descriptor_boundary_uses_the_next_source_address(self):
        descriptors = 0x50000
        self.backend.write(descriptors, struct.pack('<IIHH', descriptors + 12, SRC, 0x7605, 1)
                           + struct.pack('<IIHH', 0, OTHER, 5, 1))
        self.write(SOURCE, descriptors, 4)
        self.write(SOURCE + 0x14, 2)
        self.write(SOURCE + 8, 0x7605)
        self.configure(DESTINATION, DST, 2, 7)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 6), struct.pack('<2H', 0x1111, 0xBBBB) + b'\xA5\xA5')
        self.assertEqual(self.read(SOURCE + 0x20, 4), descriptors + 24)

    def test_large_current_descriptor_points_past_fetched_words(self):
        descriptor, next_descriptor = 0x60000, 0x70000
        self.backend.write(descriptor, struct.pack('<IIHH', next_descriptor, SRC, 0x7605, 2))
        self.write(SOURCE, descriptor, 4)
        self.write(SOURCE + 0x14, 2)
        self.write(SOURCE + 8, 0x7605)
        self.configure(DESTINATION, DST, 1, 7)
        self.backend.watch_memory(SRC, 4)
        self.backend.advance(1)
        self.assertEqual(self.read(SOURCE + 0x20, 4), descriptor + 12)
        self.assertEqual(self.read(SOURCE, 4), next_descriptor)
        self.assertEqual(self.backend.memory_accesses()['dma_read']['descriptor'], descriptor)

    def test_disabled_destination_descriptor_does_not_start_data_transfer(self):
        descriptor = 0x60000
        self.backend.write(descriptor, struct.pack('<IIHH', 0, DST, 6, 2))
        self.configure(SOURCE, SRC, 2, 5)
        self.write(DESTINATION, descriptor, 4)
        self.write(DESTINATION + 0x14, 2)
        self.write(DESTINATION + 8, 0x7607)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 6), b'\xA5' * 6)
        self.assertEqual(self.read(DESTINATION + 0x28) & 8, 0)
        self.assertEqual(self.read(SOURCE + 0x30), 2)

    def test_disabled_linked_descriptor_stops_after_the_previous_block(self):
        descriptor = 0x60000
        self.backend.write(descriptor, struct.pack('<IIHH', descriptor + 12, DST, 0x7607, 1)
                           + struct.pack('<IIHH', 0, DST + 2, 6, 1))
        self.configure(SOURCE, SRC, 2, 5)
        self.write(DESTINATION, descriptor, 4)
        self.write(DESTINATION + 0x14, 2)
        self.write(DESTINATION + 8, 0x7607)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 6), struct.pack('<H', 0x1111) + b'\xA5' * 4)
        self.assertEqual(self.read(DESTINATION + 0x28) & 8, 0)
        self.assertEqual(self.read(SOURCE + 0x30), 1)

    def test_disabled_source_descriptor_does_not_supply_data(self):
        descriptor = 0x60000
        self.backend.write(descriptor, struct.pack('<IIHH', 0, SRC, 4, 2))
        self.write(SOURCE, descriptor, 4)
        self.write(SOURCE + 0x14, 2)
        self.write(SOURCE + 8, 0x7605)
        self.configure(DESTINATION, DST, 2, 7)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 6), b'\xA5' * 6)
        self.assertEqual(self.read(SOURCE + 0x28) & 8, 0)
        self.assertEqual(self.read(DESTINATION + 0x30), 2)

    def test_disabled_linked_source_keeps_the_destination_waiting(self):
        descriptor = 0x60000
        self.backend.write(descriptor, struct.pack('<IIHH', descriptor + 12, SRC, 0x7605, 1)
                           + struct.pack('<IIHH', 0, SRC + 2, 4, 1))
        self.write(SOURCE, descriptor, 4)
        self.write(SOURCE + 0x14, 2)
        self.write(SOURCE + 8, 0x7605)
        self.configure(DESTINATION, DST, 2, 7)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 6), struct.pack('<H', 0x1111) + b'\xA5' * 4)
        self.assertEqual(self.read(SOURCE + 0x28) & 8, 0)
        self.assertEqual(self.read(DESTINATION + 0x30), 1)

    def test_small_current_descriptor_preserves_the_pointer_page(self):
        descriptor, next_descriptor = 0x60000, 0x64000
        self.backend.write(descriptor, struct.pack('<HIHH', next_descriptor & 65535, SRC, 0x6505, 2))
        self.write(SOURCE, descriptor, 4)
        self.write(SOURCE + 0x14, 2)
        self.write(SOURCE + 8, 0x6505)
        self.configure(DESTINATION, DST, 1, 7)
        self.backend.watch_memory(SRC, 4)
        self.backend.advance(1)
        self.assertEqual(self.read(SOURCE + 0x20, 4), descriptor + 10)
        self.assertEqual(self.read(SOURCE, 4), next_descriptor)
        self.assertEqual(self.backend.memory_accesses()['dma_read']['descriptor'], descriptor)

    def test_array_descriptors_advance_from_current_pointer_and_ignore_next_pointer(self):
        descriptors = 0x60000
        self.backend.write(descriptors, struct.pack('<IHH', SRC, 0x4405, 1)
                           + struct.pack('<IHH', OTHER, 5, 1))
        self.write(SOURCE, 0x70000, 4)
        self.write(SOURCE + 0x20, descriptors, 4)
        self.write(SOURCE + 0x14, 2)
        self.write(SOURCE + 8, 0x4405)
        self.configure(DESTINATION, DST, 2, 7)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 6), struct.pack('<2H', 0x1111, 0xBBBB) + b'\xA5\xA5')
        self.assertEqual(self.read(SOURCE + 0x20, 4), descriptors + 16)
        self.assertEqual(self.read(SOURCE, 4), 0x70000)

    def test_source_row_boundary_applies_y_modify_before_the_next_read(self):
        self.backend.write(SRC + 10, struct.pack('<2H', 0x4444, 0x5555))
        self.write(SOURCE + 0x18, 2)
        self.write(SOURCE + 0x1C, 8)
        self.configure(SOURCE, SRC, 2, 0x15)
        self.configure(DESTINATION, DST, 4, 7)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 10), struct.pack('<4H', 0x1111, 0x2222, 0x4444, 0x5555) + b'\xA5\xA5')

    def test_descending_source_reads_each_element_at_its_actual_address(self):
        self.configure(SOURCE, SRC + 4, 3, 5, -2)
        self.configure(DESTINATION, DST, 3, 7)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 8), struct.pack('<3H', 0x3333, 0x2222, 0x1111) + b'\xA5\xA5')

    def test_descending_destination_keeps_its_existing_element_order(self):
        self.configure(SOURCE, SRC, 3, 5)
        self.configure(DESTINATION, DST + 4, 3, 7, -2)
        self.backend.run(20)
        self.assertEqual(self.backend.read(DST, 8), struct.pack('<3H', 0x3333, 0x2222, 0x1111) + b'\xA5\xA5')

    def test_different_mdma_word_sizes_fail_explicitly(self):
        self.configure(SOURCE, SRC, 1, 9, 4)
        self.configure(DESTINATION, DST, 2, 7)
        with self.assertRaisesRegex(BackendError, 'word size'):
            self.backend.run(20)

    def test_two_dimensional_single_element_rows_fail_explicitly(self):
        self.write(SOURCE + 0x18, 2)
        with self.assertRaisesRegex(BackendError, 'inner count'):
            self.configure(SOURCE, SRC, 1, 0x15)

    def reject_descriptor(self, config, address):
        self.write(SOURCE, address, 4)
        self.write(SOURCE + 0x20, address, 4)
        with self.assertRaisesRegex(BackendError, 'descriptor'):
            self.configure(SOURCE, SRC, 1, config)

    def test_unmapped_large_descriptor_fails_before_decoding(self):
        self.reject_descriptor(0x7205, 0x10000000)

    def test_unmapped_small_descriptor_fails_before_decoding(self):
        self.reject_descriptor(0x6105, 0x10000000)

    def test_unmapped_array_descriptor_fails_before_decoding(self):
        self.reject_descriptor(0x4105, 0x10000000)

    def test_partial_descriptor_fails_before_decoding(self):
        self.backend.write(0x03FFFFFC, b'head')
        self.reject_descriptor(0x7605, 0x03FFFFFC)

    def test_large_descriptor_without_both_pointer_halves_is_unsupported(self):
        self.backend.write(0x50000, bytes(2))
        self.reject_descriptor(0x7105, 0x50000)

    def test_unmapped_source_data_is_an_error_instead_of_an_empty_stream(self):
        self.configure(SOURCE, 0x10000000, 1, 5)
        self.configure(DESTINATION, DST, 1, 7)
        with self.assertRaisesRegex(BackendError, 'DMA data read'):
            self.backend.run(20)

    def test_unmapped_destination_data_is_an_error(self):
        self.configure(SOURCE, SRC, 1, 5)
        self.configure(DESTINATION, 0x10000000, 1, 7)
        with self.assertRaisesRegex(BackendError, 'DMA data write'):
            self.backend.run(20)

    def test_partial_source_data_cannot_be_reported_as_a_complete_transfer(self):
        self.backend.write(0x03FFFFFC, b'data')
        self.configure(SOURCE, 0x03FFFFFC, 2, 9, 4)
        self.configure(DESTINATION, DST, 2, 11, 4)
        with self.assertRaisesRegex(BackendError, 'DMA data read'):
            self.backend.run(20)

    def test_partial_destination_data_cannot_be_reported_as_a_complete_transfer(self):
        self.configure(SOURCE, SRC, 2, 9, 4)
        self.configure(DESTINATION, 0x03FFFFFC, 2, 11, 4)
        with self.assertRaisesRegex(BackendError, 'DMA data write'):
            self.backend.run(20)

    def first_interrupt_row(self, config):
        self.write(DESTINATION + 0x18, 2)
        self.write(DESTINATION + 0x1C, 2)
        self.configure(SOURCE, SRC, 2, 5)
        self.configure(DESTINATION, DST, 2, config)
        self.backend.advance(1)
        self.assertEqual(self.read(DESTINATION + 0x30), 2)
        self.assertEqual(self.read(DESTINATION + 0x38), 1)

    def finish_interrupt_row(self):
        self.backend.write(OTHER, struct.pack('<2H', 0xBBBB, 0xCCCC))
        self.write(SOURCE + 8, 0)
        self.write(SOURCE + 0x28, 1)
        self.configure(SOURCE, OTHER, 2, 5)
        self.backend.advance(1)
        self.assertEqual(self.backend.read(DST, 10), struct.pack('<4H', 0x1111, 0x2222, 0xBBBB, 0xCCCC) + b'\xA5\xA5')
        self.assertEqual(self.read(DESTINATION + 0x28) & 9, 1)
        self.assertTrue(self.read(0xFFC00160, 4) & 0x400)

    def test_2d_outer_interrupt_waits_for_the_final_row(self):
        self.first_interrupt_row(0x97)
        self.assertEqual(self.read(DESTINATION + 0x28) & 9, 8)
        self.assertFalse(self.read(0xFFC00160, 4) & 0x400)
        self.finish_interrupt_row()

    def test_2d_inner_interrupt_is_raised_for_each_row(self):
        self.first_interrupt_row(0xD7)
        self.assertEqual(self.read(DESTINATION + 0x28) & 9, 9)
        self.assertTrue(self.read(0xFFC00160, 4) & 0x400)
        self.write(DESTINATION + 0x28, 1)
        self.assertFalse(self.read(0xFFC00160, 4) & 0x400)
        self.finish_interrupt_row()

    def test_zero_inner_count_transfers_all_65536_elements(self):
        source, destination = 0x100000, 0x200000
        data = struct.pack('<65536H', *((i ^ 0x1234) for i in range(65536)))
        self.backend.write(source, data)
        self.backend.write(destination, b'\xA5' * (len(data) + 2))
        self.configure(SOURCE, source, 0, 5)
        self.configure(DESTINATION, destination, 0, 7)
        self.backend.run(100)
        self.assertEqual(self.backend.read(destination, len(data) + 2), data + b'\xA5\xA5')
        self.assertEqual(self.read(DESTINATION + 0x30), 0)
        self.assertEqual(self.read(DESTINATION + 0x28) & 9, 1)

    def test_zero_outer_count_transfers_all_65536_rows(self):
        destination = 0x200000
        length = 65536 * 4
        self.backend.write(destination, b'\xA5' * (length + 2))
        self.write(SOURCE + 0x18, 0)
        self.write(SOURCE + 0x1C, -2)
        self.write(DESTINATION + 0x18, 0)
        self.write(DESTINATION + 0x1C, 2)
        self.configure(SOURCE, SRC, 2, 0x15)
        self.configure(DESTINATION, destination, 2, 0x17)
        self.backend.run(100000)
        self.assertEqual(self.backend.read(destination, length + 2), struct.pack('<2H', 0x1111, 0x2222) * 65536 + b'\xA5\xA5')
        self.assertEqual(self.read(DESTINATION + 0x38), 1)
        self.assertEqual(self.read(DESTINATION + 0x28) & 9, 1)
