# SPDX-License-Identifier: GPL-2.0-only
"""devicetime.py: the base rate matches the emulator's, and the four timing_probe loops come out as measured
(docs/messungen/2026-10-16-emulator-timing.md, mean of three device runs)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import devicetime  # noqa: E402
import machine  # noqa: E402


class DeviceTime(unittest.TestCase):
    def test_base_rate_is_the_emulators(self):
        self.assertEqual(devicetime.ALU_NS_PER_INSN, machine.NS_PER_INSN)

    def test_probe_loops(self):
        est = devicetime.estimate_device_ns
        loop = lambda insns: insns * machine.NS_PER_INSN
        # measured per round: alu 20.15 ns, mul 26.82, memh 47.88, mem 143.43, memu 234.1
        self.assertAlmostEqual(est(loop(4)), 20.15, delta=1)
        self.assertAlmostEqual(est(loop(4), mul_insns=1), 26.82, delta=1)
        self.assertAlmostEqual(est(loop(8), read_hit_bytes=16), 47.88, delta=1.5)
        self.assertAlmostEqual(est(loop(7), read_stream_bytes=16), 143.43, delta=2)
        self.assertAlmostEqual(est(loop(7), read_uncached_bytes=16), 234.1, delta=2)

    def test_plain_code_is_unchanged(self):
        self.assertEqual(devicetime.estimate_device_ns(1234), 1234)


if __name__ == "__main__":
    unittest.main()
