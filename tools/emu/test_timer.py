# SPDX-License-Identifier: GPL-2.0-only
"""Emulated time: the firmware gets 1000 timer interrupts and 25 screen ticks per
emulated second, whatever the slice length. Needs E2_VSB; skipped without it,
a failure when E2_EMU_REQUIRED=1. E2_FLASH (parts joined by os.pathsep) is optional.

Measured in docs/messungen/2026-10-12-emulator-takt.md."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import machine  # noqa: E402

VSB = os.environ.get("E2_VSB")
REQUIRED = os.environ.get("E2_EMU_REQUIRED") == "1"
TIMER_INT = 21                  # TIMER64P0 12, the 1 kHz system tick (machine.TIMERS)
AINTC_SICR = machine.AINTC + 0x24
SCREEN_TICK = 0xC006F178        # UiTask, once per 40 ms; start of the function in firmware 2.02
START, WINDOW = 2.0, 1.0        # seconds of device time before counting, and counted


class Counting(machine.Machine):
    """Counts the timer interrupts the firmware's handler acknowledged."""

    def __init__(self, *args):
        super().__init__(*args)
        self.handled = 0
        self.ticks = 0
        import unicorn
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self._tick, begin=SCREEN_TICK, end=SCREEN_TICK)

    def _tick(self, uc, addr, size, user):
        self.ticks += 1

    def write(self, a, v):
        if a == AINTC_SICR and v & 0x7F == TIMER_INT:
            self.handled += 1
        return super().write(a, v)


def rates(slice_length):
    old = machine.SLICE
    machine.SLICE = slice_length
    try:
        flash = machine.load_flash(os.environ["E2_FLASH"].split(os.pathsep)) if os.environ.get("E2_FLASH") else None
        m = Counting(Path(VSB).read_bytes()[0x100:], flash)
        m.run_until(START)
        handled, ticks, t0 = m.handled, m.ticks, m.time_ns
        m.run_until(START + WINDOW)
        seconds = (m.time_ns - t0) / 1e9
        assert not m.asserts, m.asserts
        return (m.handled - handled) / seconds, (m.ticks - ticks) / seconds
    finally:
        machine.SLICE = old


class TimerTest(unittest.TestCase):
    def setUp(self):
        if not VSB:
            if REQUIRED:
                self.fail("E2_VSB is not set")
            self.skipTest("E2_VSB not set")
        try:
            import unicorn  # noqa: F401
        except ImportError:
            if REQUIRED:
                self.fail("Unicorn is not installed in this Python")
            self.skipTest("Unicorn not installed")

    def check(self, slice_length):
        interrupts, ticks = rates(slice_length)
        self.assertAlmostEqual(interrupts, 1000, delta=10, msg=f"timer interrupts per second, slice {slice_length}")
        self.assertAlmostEqual(ticks, 25, delta=0.25, msg=f"screen ticks per second, slice {slice_length}")

    def test_default_slice(self):
        self.check(machine.SLICE)

    def test_long_slice(self):
        self.check(10 * machine.SLICE)

    def test_short_slice(self):
        self.check(500)


if __name__ == "__main__":
    unittest.main()
