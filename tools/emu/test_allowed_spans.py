"""Start-phase permissions cover their union and leave every gap visible."""
import unittest

from check import IMAGE, overlaps


class AllowedSpans(unittest.TestCase):
    def test_adjacent_permissions_cover_a_contiguous_executed_run(self):
        self.assertEqual(overlaps([(0x100, 16)], [(IMAGE, IMAGE + 16)], [(0x108, 8), (0x100, 8)]), [])

    def test_overlapping_permissions_cover_a_contiguous_executed_run(self):
        self.assertEqual(overlaps([(0x100, 16)], [(IMAGE, IMAGE + 16)], [(0x100, 10), (0x108, 8)]), [])

    def test_a_gap_between_permissions_remains_an_error(self):
        self.assertEqual(overlaps([(0x100, 16)], [(IMAGE, IMAGE + 16)], [(0x100, 6), (0x108, 8)]), [[0x106, 2]])

    def test_permissions_and_execution_are_clipped_to_the_changed_run(self):
        self.assertEqual(overlaps([(0x100, 16)], [(IMAGE + 2, IMAGE + 14)],
                                  [(0xF0, 20), (0x10A, 20)]), [[0x104, 6]])

    def test_no_permission_keeps_the_whole_intersection(self):
        self.assertEqual(overlaps([(0x100, 16)], [(IMAGE + 2, IMAGE + 14)]), [[0x102, 12]])


if __name__ == "__main__":
    unittest.main()
