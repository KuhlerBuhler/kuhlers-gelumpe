# SPDX-License-Identifier: GPL-2.0-only
"""The display light as the eye sees it, from the pin changes the firmware makes (backlight.py)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlight import Backlight  # noqa: E402

MS = 1_000_000
R, G, B = 0x08, 0x10, 0x20


def pwm(light, start_ms, periods, edges, period_ms=8):
    """Drive `light` with the same period again and again: `edges` is [(ms into the period, pins)]."""
    for n in range(periods):
        for at, pins in edges:
            light.write(int((start_ms + n * period_ms + at) * MS), pins)
    return int((start_ms + periods * period_ms) * MS)


class BacklightTest(unittest.TestCase):
    def test_nothing_is_known_before_the_firmware_drives_the_pins(self):
        self.assertIsNone(Backlight().levels(5 * MS))

    def test_plain_pins_are_full_or_dark(self):
        light = Backlight()
        light.write(0, R | G | B)
        self.assertEqual(light.levels(500 * MS), [255, 255, 255], "stock: white")
        light.write(500 * MS, G)
        self.assertEqual(light.levels(510 * MS), [0, 255, 0])

    def test_a_pwm_level_is_its_share_of_the_period(self):
        """Red at 5 of 16 as the emulator runs it: on 5.5 ms into each 8 ms period, off at its end (2.5 ms lit)."""
        light = Backlight()
        light.write(0, 0)
        end = pwm(light, 0, 10, [(5.5, R), (8, 0)])
        self.assertEqual(light.levels(end), [80, 0, 0], "5/16 of 255, a dimmer red")

    def test_a_mix_of_three_levels(self):
        """3, 8 and 12 of 16: blue rises 2 ms into the period, green 4 ms, red 6.5 ms, all go dark at 8 ms."""
        light = Backlight()
        light.write(0, 0)
        end = pwm(light, 0, 10, [(2, B), (4, B | G), (6.5, R | G | B), (8, 0)])
        self.assertEqual(light.levels(end), [round(1.5 / 8 * 255), round(4 / 8 * 255), round(6 / 8 * 255)])

    def test_a_pin_that_stops_switching_is_plain_again(self):
        light = Backlight()
        light.write(0, 0)
        end = pwm(light, 0, 10, [(5.5, R), (8, 0)])
        light.write(end, R)
        self.assertEqual(light.levels(end + 200 * MS), [255, 0, 0])

    def test_power_off_is_dark(self):
        light = Backlight()
        light.write(0, R | G | B)
        light.off(10 * MS)
        self.assertEqual(light.levels(20 * MS), [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
