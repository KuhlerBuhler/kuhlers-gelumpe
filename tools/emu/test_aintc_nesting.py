# SPDX-License-Identifier: GPL-2.0-only
"""The interrupt controller holds back an IRQ at or below the global nesting level (GNLR) that Korg's IRQ dispatcher sets
to the channel of the line it serves, so only a higher priority line nests (machine.Machine.highest). Needs no firmware."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import machine  # noqa: E402

UART1, TICK, CARD = 53, 21, 68     # the synth's channels: CMR 6, 8 and 5 (measured in the emulator, 2026-11-15)


def controller(level=machine.GNLR_NONE):
    m = machine.Machine.__new__(machine.Machine)       # only the controller's state, no firmware
    m.raw, m.enabled = {UART1, TICK, CARD}, {UART1, TICK, CARD}
    m.cmr = {UART1: 6, TICK: 8, CARD: 5}
    m.nest_level = level
    return m


class Nesting(unittest.TestCase):
    def test_without_a_level_the_highest_priority_line_comes_first(self):
        self.assertEqual(controller().highest(), CARD)

    def test_a_line_at_the_level_or_below_is_held_back(self):
        m = controller(5)                               # the dispatcher serves the CMR 5 line
        self.assertEqual(m.highest(), 0x80000000)
        m.nest_level = 7                                # it serves a CMR 7 line: CMR 5 and 6 nest, CMR 8 waits
        self.assertEqual(m.highest(), CARD)
        m.raw.discard(CARD)
        self.assertEqual(m.highest(), UART1)
        m.raw.discard(UART1)
        self.assertEqual(m.highest(), 0x80000000)

    def test_fiq_lines_are_not_held_back(self):
        m = controller(0)
        m.raw.add(1)
        m.enabled.add(1)
        m.cmr[1] = 1
        self.assertEqual(m.highest(fiq=True), 1)


class SliceLength(unittest.TestCase):
    """With IRQs masked and a line pending the next slice is short, so the line is taken as soon as the mask drops."""

    def machine(self, cpsr, raw):
        m = controller()
        m.raw = set(raw)
        m.time_ns, m.ns_per_insn = 0, 5.0
        m.next_event = lambda: 1e9
        m.A = type("A", (), {"UC_ARM_REG_CPSR": 0})
        m.reg = lambda _reg: cpsr
        return m

    def test_masked_with_a_pending_line_is_short(self):
        self.assertEqual(self.machine(0xD3, {TICK}).slice_length(False), machine.ISR_STEP)

    def test_masked_without_a_pending_line_is_long(self):
        self.assertEqual(self.machine(0xD3, set()).slice_length(False), machine.SLICE)

    def test_unmasked_is_long(self):
        self.assertEqual(self.machine(0x53, {TICK}).slice_length(False), machine.SLICE)


if __name__ == "__main__":
    unittest.main()
