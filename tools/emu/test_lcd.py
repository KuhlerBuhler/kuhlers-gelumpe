# SPDX-License-Identifier: GPL-2.0-only
"""LCD response: levels from the firmware's on/off display, no firmware needed."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lcd import LcdResponse, LEVELS, TAU_OFF, TAU_ON, WIDTH, taus  # noqa: E402

TOP = LEVELS - 1
STEP_NS = 20_000_000


def display(lit=False):
    """All dark or all clear, in the machine's page layout."""
    return [[0xFF if lit else 0] * WIDTH for _ in range(8)]


def run(lcd, fb, seconds, step_ns=STEP_NS):
    """Hold fb for the given time, in steps; returns the pixel (0, 0) level after each step."""
    levels = []
    for _ in range(round(seconds * 1e9 / step_ns)):
        lcd.update(fb, lcd.t + step_ns)
        levels.append(lcd.out[0])
    return levels


class LcdResponseTest(unittest.TestCase):
    def test_the_first_display_is_shown_as_it_is(self):
        lcd = LcdResponse()
        self.assertTrue(lcd.update([[1] + [0] * (WIDTH - 1)] + [[0] * WIDTH] * 7, 5))
        self.assertEqual((lcd.out[0], lcd.out[1], lcd.out[WIDTH]), (TOP, 0, 0))
        self.assertEqual(lcd.moving, {})

    def test_a_reversed_controller_shows_every_pixel_the_other_way_round(self):
        """0xA7 swaps dark and clear for the whole display; the pixels then follow with their lag like any other change."""
        lcd = LcdResponse()
        lcd.update(display(), 0)
        self.assertEqual((lcd.out[0], lcd.out[WIDTH * 63 + 127]), (0, 0))
        lcd.update(display(), lcd.t + STEP_NS, True)
        self.assertTrue(0 < lcd.out[0] < TOP, "reversing is a switch, the pixel follows with its lag")
        for _ in range(75):
            lcd.update(display(), lcd.t + STEP_NS, True)
        self.assertEqual(set(lcd.out), {TOP})
        settled = LcdResponse()
        settled.settle(display(), True)
        self.assertEqual(set(settled.out), {TOP})

    def test_a_pixel_follows_its_switching_and_ends_at_the_target(self):
        lcd = LcdResponse()
        lcd.update(display(), 0)
        dark = run(lcd, display(True), 1.5)
        self.assertEqual(dark[-1], TOP)
        self.assertEqual(lcd.moving, {})
        self.assertGreater(dark[0], 0, "it starts to move at once")
        self.assertLess(dark[0], TOP / 2, "but one step is far from done")
        self.assertEqual(dark, sorted(dark), "and never goes back")
        clear = run(lcd, display(), 2.5)
        self.assertEqual(clear[-1], 0)
        self.assertEqual(clear, sorted(clear, reverse=True))

    def test_clearing_is_slower_than_darkening(self):
        """The owner's estimate by eye (2026-10-27): a pixel turns dark fast, clear only in about 0.3 s (a walking figure
        drags a smear). The slow-motion video of 2026-10-13 had it the other way round, its clearing value was too low."""
        lcd = LcdResponse()
        lcd.update(display(), 0)
        on = run(lcd, display(True), 0.06)[-1]
        lcd = LcdResponse()
        lcd.update(display(True), 0)
        off = TOP - run(lcd, display(), 0.06)[-1]
        self.assertGreater(on, off)

    def test_text_blinking_every_280_ms_fades_in_and_out(self):
        """What the firmware does to the pattern name while the next pattern waits: 280 ms dark, 280 ms clear.
        It reaches full dark; with clearing as slow as estimated (TAU_OFF) it does not get fully clear in 280 ms."""
        lcd = LcdResponse()
        lcd.update(display(), 0)
        for cycle in range(4):
            dark = run(lcd, display(True), 0.28)
            clear = run(lcd, display(), 0.28)
        self.assertEqual(dark[-1], TOP, "fully dark before the next switch")
        self.assertTrue(0 < clear[-1] < TOP, "not fully clear before the next switch")
        self.assertTrue(any(0 < v < TOP for v in dark), "the edge is a fade, not a jump")
        self.assertTrue(any(0 < v < TOP for v in clear))

    def test_the_time_constants_come_from_the_arguments_then_the_environment_then_the_defaults(self):
        self.assertEqual(taus(env={}), (TAU_ON, TAU_OFF))
        self.assertEqual(taus(env={"E2_LCD_TAU_ON": "0.3", "E2_LCD_TAU_OFF": "0.5"}), (0.3, 0.5))
        self.assertEqual(taus(0.05, env={"E2_LCD_TAU_ON": "0.3"}), (0.05, TAU_OFF))
        self.assertEqual(LcdResponse(0.4, 0.6).tau_on, 0.4)
        for bad in ({"E2_LCD_TAU_ON": "fast"}, {"E2_LCD_TAU_OFF": "0"}, {"E2_LCD_TAU_ON": "-1"}, {"E2_LCD_TAU_OFF": "99"}):
            with self.assertRaises(ValueError):
                taus(env=bad)

    def test_slower_time_constants_dim_the_blink_more(self):
        def low(on, off):
            lcd = LcdResponse(on, off)
            lcd.update(display(), 0)
            for _ in range(8):
                run(lcd, display(True), 0.28)
                last = min(run(lcd, display(), 0.28))
            return last
        self.assertGreater(low(0.1, 0.4), low(0.1, 0.2))
        self.assertLess(low(0.05, 0.05), low(0.1, 0.2))

    def test_the_constants_follow_from_the_extremes_of_the_280_ms_blink(self):
        """The formulas in docs/messungen/2026-10-12-lcd-helligkeit.md, checked against the model."""
        import math
        for tau_on, tau_off in ((0.10, 0.20), (0.15, 0.35), (0.12, 0.30)):
            lcd = LcdResponse(tau_on, tau_off)
            lcd.update(display(), 0)
            for _ in range(10):
                high = max(run(lcd, display(True), 0.28, 10_000_000)) / TOP
                low = min(run(lcd, display(), 0.28, 10_000_000)) / TOP
            a = (1 - high) / (1 - low)
            b = low / high
            self.assertAlmostEqual(-0.28 / math.log(a), tau_on, delta=0.02 + 0.1 * tau_on)
            self.assertAlmostEqual(-0.28 / math.log(b), tau_off, delta=0.02 + 0.1 * tau_off)

    def test_a_still_display_costs_nothing_and_reports_no_change(self):
        lcd = LcdResponse()
        lcd.update(display(True), 0)
        self.assertFalse(lcd.update(display(True), STEP_NS))
        self.assertEqual(lcd.moving, {})

    def test_the_step_length_hardly_matters(self):
        coarse, fine = LcdResponse(), LcdResponse()
        for lcd in (coarse, fine):
            lcd.update(display(), 0)
        a = run(coarse, display(True), 0.2, 40_000_000)[-1]
        b = run(fine, display(True), 0.2, 5_000_000)[-1]
        self.assertLessEqual(abs(a - b), 1)

    def test_only_the_changed_pixels_move(self):
        lcd = LcdResponse()
        lcd.update(display(), 0)
        fb = display()
        fb[3][10] = 0b0000_0101         # two pixels of one column in page 3
        lcd.update(fb, STEP_NS)
        self.assertEqual(sorted(lcd.moving), [24 * WIDTH + 10, 26 * WIDTH + 10])

    def test_settle_shows_a_display_at_once(self):
        lcd = LcdResponse()
        lcd.update(display(), 0)
        lcd.update(display(True), STEP_NS)
        lcd.settle(display())
        self.assertEqual((set(lcd.shades()), lcd.moving), ({0}, {}))


if __name__ == "__main__":
    unittest.main()
