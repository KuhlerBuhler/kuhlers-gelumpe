# SPDX-License-Identifier: GPL-2.0-only
"""Importing check.py leaves the emulator's slice (machine.SLICE) as it is: the start scenarios of a check in this process
measure the same start phase as in a worker that imports only bootmap.py (parallel.py, with and without the task cache)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import machine  # noqa: E402

DEFAULT = machine.SLICE

import check  # noqa: E402,F401
import seq_timing_probe  # noqa: E402


class SliceScope(unittest.TestCase):
    def test_importing_check_keeps_the_slice(self):
        self.assertEqual(machine.SLICE, DEFAULT)

    def test_the_probe_sets_its_slice_only_inside_its_block(self):
        with seq_timing_probe.fine_slices():
            self.assertEqual(machine.SLICE, seq_timing_probe.FINE_SLICE)
        self.assertEqual(machine.SLICE, DEFAULT)

    def test_the_slice_comes_back_after_an_error(self):
        with self.assertRaises(RuntimeError), seq_timing_probe.fine_slices():
            raise RuntimeError("case failed")
        self.assertEqual(machine.SLICE, DEFAULT)


if __name__ == "__main__":
    unittest.main()
