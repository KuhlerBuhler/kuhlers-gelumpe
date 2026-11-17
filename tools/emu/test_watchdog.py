# SPDX-License-Identifier: GPL-2.0-only
"""The watchdog of Timer64P1 in machine.py (docs/messungen/2026-11-16-watchdog-neustart.md) and the stub of
tools/device/watchdog_restart.py. The model cases run on a bare machine with a few instructions of its own, no firmware; the
boot case needs the firmware (E2_VSB) and checks that it never arms the watchdog."""

import os
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent / "device"))     # after this folder: tools/device has a backlight.py of its own
sys.path.append(str(HERE.parent / "patch"))

import machine  # noqa: E402
from machine import WD_TIMER, WDTCR, WDEN  # noqa: E402

VSB = os.environ.get("E2_VSB")
REQUIRED = os.environ.get("E2_EMU_REQUIRED") == "1"
TIMER_REGS = range(WD_TIMER, WD_TIMER + 0x80)
STUB_AT = 0xC1000000
RESULT = 0xC0F00000
# Places no code of the bare machine reaches: the four entries the model stops at, and a screen manager pointer that reads 0.
PROFILE = SimpleNamespace(build="bare", assert_handler=0xC7F00000, flash_read=0xC7F00010, dsp_upload=0xC7F00020,
                          tx_full=0xC7F00030, user_mark=machine.SAMPLER_USER_MARK, screens=0xC0F00100)


def unicorn_or_skip(case):
    try:
        import unicorn  # noqa: F401
    except ImportError:
        if REQUIRED:
            case.fail("Unicorn is not installed in this Python")
        case.skipTest("Unicorn not installed")


def bare(code_at_start, extra=()):
    """A machine whose image starts at 0xC0000070 with `code_at_start` (words), more (address, bytes) placed by `extra`;
    Timer 1 as the firmware leaves it: TGCR 0xB (watchdog mode), PRD12 1 s, TCR 0x80."""
    payload = bytearray(0x1000)
    payload[0x70:0x70 + 4 * len(code_at_start)] = struct.pack(f"<{len(code_at_start)}I", *code_at_start)
    m = machine.Machine(bytes(payload), None, PROFILE)
    for at, data in extra:
        m.uc.mem_write(at, data)
    m.regs.update({WD_TIMER + 0x24: 0xB, WD_TIMER + 0x18: 24_000_000, WD_TIMER + 0x20: 0x80})
    return m


WFI_LOOP = [0xEE070F90, 0xEAFFFFFD]                 # mcr p15, 0, r0, c7, c0, 4 (wait for interrupt); b back


def call_stub():
    """blx STUB_AT, keep r0 at RESULT, then wait for interrupts for ever."""
    return [0xE59FC010, 0xE12FFF3C, 0xE59F100C, 0xE5810000] + WFI_LOOP + [STUB_AT, RESULT]


class WatchdogModelTest(unittest.TestCase):
    def setUp(self):
        unicorn_or_skip(self)

    def armed(self, period_ticks):
        m = bare(WFI_LOOP)
        m.regs[WD_TIMER + 0x18] = period_ticks
        m.write(WDTCR, 0xA5C60000 | WDEN)
        self.assertEqual(m.wd_state, "pre")
        m.write(WDTCR, 0xDA7E0000 | WDEN)
        self.assertEqual(m.wd_state, "active")
        return m

    def test_the_counter_runs_once_armed_and_resets_the_chip_at_the_period(self):
        m = self.armed(2_400_000)                   # 100 ms at 24 MHz
        m.run_until(0.05)
        self.assertIsNone(m.reset)
        self.assertAlmostEqual(m.read(WD_TIMER + 0x10), 1_200_000, delta=2400)
        self.assertEqual(m.read(WDTCR), WDEN, "WDKEY reads 0, WDEN set")
        m.run_until(1.0)
        self.assertEqual(m.reset["cause"], "timeout")
        self.assertAlmostEqual(m.reset["ms"], 100, delta=0.1)
        self.assertLess(m.time_ns, 101e6, "the run ends at the reset")

    def test_a_wrong_key_while_active_resets_at_once(self):
        m = self.armed(24_000_000)
        m.write(WDTCR, 0x12340000 | WDEN)
        self.assertEqual(m.reset, {"cause": "key", "ms": 0.0})
        m.run_until(1.0)
        self.assertEqual(m.time_ns, 0, "nothing runs after the reset")

    def test_serving_puts_the_counter_back(self):
        m = self.armed(2_400_000)
        m.run_until(0.08)
        m.write(WDTCR, 0xA5C60000 | WDEN)
        m.write(WDTCR, 0xDA7E0000 | WDEN)
        m.run_until(0.15)
        self.assertIsNone(m.reset, "served at 80 ms: no reset at 100 ms")
        m.run_until(1.0)
        self.assertAlmostEqual(m.reset["ms"], 180, delta=0.1)

    def test_keys_outside_watchdog_mode_and_before_the_first_key_do_nothing(self):
        m = bare(WFI_LOOP)
        m.regs[WD_TIMER + 0x24] = 0x7               # timer mode 1: no watchdog
        m.write(WDTCR, 0xA5C60000 | WDEN)
        m.write(WDTCR, 0xDA7E0000 | WDEN)
        self.assertEqual(m.wd_state, "off")
        m.regs[WD_TIMER + 0x24] = 0xB
        m.write(WDTCR, 0xDA7E0000 | WDEN)           # the second key first
        m.write(WDTCR, 0xA5C60000)                  # the first key without WDEN
        self.assertEqual(m.wd_state, "off")
        m.run_until(0.5)
        self.assertIsNone(m.reset)
        self.assertEqual(m.read(WD_TIMER + 0x10), 0, "the counter of the unarmed watchdog stays 0, as on the device")

    def test_reboot_starts_from_the_flash_with_the_same_card(self):
        m = self.armed(240_000)
        m.run_until(0.1)
        self.assertIsNotNone(m.reset)
        again = m.reboot()
        self.assertIsNot(again, m)
        self.assertIsNone(again.reset)
        self.assertEqual(again.wd_state, "off")
        self.assertEqual(bytes(again.flash.mem), bytes(m.flash.mem))


class WatchdogStubTest(unittest.TestCase):
    """The stub as watchdog_restart.py sends it, run by a call as BLECH EXEC makes it."""

    def setUp(self):
        unicorn_or_skip(self)
        import watchdog_restart
        self.tool = watchdog_restart

    def test_the_stub_arms_the_watchdog_returns_and_the_chip_resets_after_100_ms(self):
        m = bare(call_stub(), [(STUB_AT, self.tool.stub(100))])
        m.run_until(1.0)
        self.assertEqual(m.u32(RESULT), self.tool.ARMED)
        self.assertEqual(m.reset["cause"], "timeout")
        self.assertAlmostEqual(m.reset["ms"], 100, delta=0.5)
        touched = set(m.recent)
        self.assertTrue(touched and touched <= set(TIMER_REGS), f"registers outside Timer 1: {sorted(map(hex, touched - set(TIMER_REGS)))}")
        self.assertEqual(sorted(touched), [WD_TIMER + o for o in (0x10, 0x14, 0x18, 0x1C, 0x24, 0x28)])

    def test_the_stub_writes_nothing_when_the_timer_is_not_in_watchdog_mode(self):
        m = bare(call_stub(), [(STUB_AT, self.tool.stub(100))])
        m.regs[WD_TIMER + 0x24] = 0x5
        m.run_until(0.5)
        self.assertEqual(m.u32(RESULT), self.tool.NOT_WATCHDOG | 0x5)
        self.assertIsNone(m.reset)
        self.assertEqual(set(m.recent), {WD_TIMER + 0x24}, "only TGCR read")

    def test_the_period_is_checked_and_built_in(self):
        for ms in (49, 2001):
            with self.assertRaises(ValueError):
                self.tool.stub(ms)
        self.assertIn(struct.pack("<I", 250 * 24_000), self.tool.stub(250))
        self.assertEqual(len(self.tool.stub()), 84)


class WatchdogFirmwareTest(unittest.TestCase):
    def setUp(self):
        if not VSB:
            if REQUIRED:
                self.fail("E2_VSB is not set")
            self.skipTest("E2_VSB not set")
        unicorn_or_skip(self)

    def test_the_firmware_never_arms_the_watchdog(self):
        """Boot and idle: the firmware sets TGCR 0xB but never writes WDTCR, so no reset comes (measured as 'no WDTCR write' in
        docs/hintergrund/skript-laufzeit.md, here held for the model)."""
        m = machine.Machine(Path(VSB).read_bytes()[0x100:], None)
        m.run_until(8.0)
        self.assertTrue(m.booted)
        self.assertIsNone(m.reset)
        self.assertEqual(m.wd_state, "off")
        self.assertEqual(m.regs.get(WD_TIMER + 0x24), 0xB, "the firmware leaves Timer 1 in watchdog mode")
        self.assertGreaterEqual(m.time_ns, 8e9)


if __name__ == "__main__":
    unittest.main()
