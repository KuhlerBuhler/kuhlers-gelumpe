"""Knob memory checks use generated rows, including incomplete original layouts."""
import unittest

import preset_cases as p


class KnobMemory(unittest.TestCase):
    def test_consistent_rows_preserve_values_and_initialize_added_columns(self):
        before = bytes(range(4)) * 16
        after = (bytes(range(4)) + bytes([64, 64])) * 16
        self.assertTrue(p.knob_memory_kept(before, 4, 4, after, 6))
        changed = bytearray(after)
        changed[10 * 6 + 2] = 17
        self.assertFalse(p.knob_memory_kept(before, 4, 4, changed, 6))

    def test_a_fully_initialized_table_repairs_an_incomplete_original(self):
        before = bytes([64]) * (16 * 49) + bytes([255]) * (16 * (64 - 49))
        after = bytes([64]) * (16 * 74)
        self.assertTrue(p.knob_memory_kept(before, 49, 64, after, 74))

    def test_an_incomplete_new_table_is_rejected_even_for_an_inconsistent_original(self):
        before = bytes([255]) * (16 * 64)
        after = bytearray([64]) * (16 * 74)
        after[-1] = 255
        self.assertFalse(p.knob_memory_kept(before, 49, 64, after, 74))

    def test_added_columns_are_not_arbitrary_initialized_values(self):
        before = bytes([64]) * (16 * 4)
        after = bytearray([64]) * (16 * 6)
        after[-1] = 3
        self.assertFalse(p.knob_memory_kept(before, 4, 4, after, 6))

    def test_an_incomplete_original_still_requires_default_values_in_new_columns(self):
        before = bytes([255]) * (16 * 64)
        after = bytearray([64]) * (16 * 74)
        after[-1] = 3
        self.assertFalse(p.knob_memory_kept(before, 49, 64, after, 74))


if __name__ == "__main__":
    unittest.main()
