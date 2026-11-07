# SPDX-License-Identifier: GPL-2.0-only
"""The start phase ends at the main screen, not at the end of bootmap's poll slice: code that first runs on the main
screen (the script runtime's frame path behind its gate) is not start phase, however long the last slice runs past it.
Needs E2_VSB; skipped without it, a failure when E2_EMU_REQUIRED=1. E2_FLASH is optional."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootmap  # noqa: E402

VSB = os.environ.get("E2_VSB")
REQUIRED = os.environ.get("E2_EMU_REQUIRED") == "1"
LONG_SLICE_S = 0.3


class StartPhaseEnd(unittest.TestCase):
    def setUp(self):
        if not VSB:
            if REQUIRED:
                self.fail("E2_VSB is not set")
            self.skipTest("E2_VSB not set")
        try:
            import unicorn  # noqa: F401
        except ImportError:
            if REQUIRED:
                raise
            self.skipTest("Unicorn not installed")
        from machine import load_flash
        self.payload = Path(VSB).read_bytes()[0x100:]
        self.flash = load_flash(os.environ["E2_FLASH"].split(os.pathsep)) if os.environ.get("E2_FLASH") else None

    def boot(self, slice_s):
        default = bootmap.SLICE_S
        bootmap.SLICE_S = slice_s
        try:
            return bootmap.run(self.payload, self.flash)
        finally:
            bootmap.SLICE_S = default

    def test_a_longer_slice_measures_the_same_start_phase(self):
        short, long = self.boot(bootmap.SLICE_S), self.boot(LONG_SLICE_S)
        self.assertEqual(short.screen(), 1)
        self.assertGreater(long.time_ns - short.time_ns, 0.1e9, "the long slice ran on past the main screen")
        self.assertEqual([hex(pc) for pc in sorted(long.blocks.keys() - short.blocks.keys())], [])
        self.assertEqual(long.blocks, short.blocks)
        self.assertEqual(long.image_read, short.image_read)


if __name__ == "__main__":
    unittest.main()
