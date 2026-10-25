# SPDX-License-Identifier: GPL-2.0-only
"""check.py overlaps(): a changed run counts only where no allowed span covers it, also across two adjacent spans."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import overlaps  # noqa: E402

EVERYWHERE = [(0, 1 << 40)]


class Overlaps(unittest.TestCase):
    def test_run_across_two_adjacent_spans_is_allowed(self):
        # pattern-switch: pad_replay and sync_hook sit next to each other, one changed run crosses the seam
        self.assertEqual(overlaps([(0x180bcf, 0x1f)], EVERYWHERE, [(0x180b7c, 0x5c), (0x180bd8, 0x20)]), [])

    def test_only_the_uncovered_parts_are_left(self):
        self.assertEqual(overlaps([(0x100, 8)], EVERYWHERE, [(0x102, 2)]), [[0x100, 2], [0x104, 4]])

    def test_without_allowance_the_whole_run_is_a_hit(self):
        self.assertEqual(overlaps([(0x100, 8)], EVERYWHERE), [[0x100, 8]])


if __name__ == "__main__":
    unittest.main()
