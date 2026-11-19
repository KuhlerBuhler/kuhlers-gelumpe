# SPDX-License-Identifier: GPL-2.0-only
"""The level arithmetic of fx_level_cases on generated frames; no DSP worker."""
import array
import unittest

import fx_level_cases as fx


def frames(gain=1.0, gap=None, loops=2):
    words = array.array('i')
    words.frombytes(fx.test_signal())
    out = []
    for n in range(fx.LOOP * loops):
        value = words[(n % fx.LOOP) * fx.WORDS] / 2 ** 31 * gain
        if gap and gap[0] <= n % fx.LOOP < gap[1]:
            value = 0.0
        out.append((value, value))
    return out


class Levels(unittest.TestCase):
    def test_signal_is_a_sine_then_a_louder_burst(self):
        dry = fx.measure(frames(), 0)
        self.assertAlmostEqual(fx.db(dry['sine_ms'], 1), -15.05, places=1)       # -12 dBFS peak sine
        self.assertAlmostEqual(fx.db(dry['burst_ms'], 1), -6.0, delta=0.5)
        self.assertGreater(dry['tone'] / dry['sine_ms'], 0.99)
        self.assertEqual(dry['dips'], 0)

    def test_half_gain_is_six_db_down_everywhere(self):
        row = fx.compare(fx.measure(frames(0.5), 0), fx.measure(frames(), 0))
        for key in ('rms_db', 'peak_db', 'sine_db', 'burst_db'):
            self.assertAlmostEqual(row[key], -6.02, places=1)

    def test_a_gap_in_the_sine_counts_as_dips(self):
        row = fx.compare(fx.measure(frames(gap=(3000, 3480)), 0), fx.measure(frames(), 0))
        self.assertEqual(row['dips'], 2 * 4)          # a 10 ms gap holds 4 whole 2 ms blocks per loop
        self.assertEqual(row['dry_dips'], 0)

    def test_window_start_inside_the_loop_keeps_the_phase(self):
        whole = frames()
        late = fx.measure(whole[777:], 777)
        self.assertAlmostEqual(fx.db(late['sine_ms'], 1), -15.05, places=1)

    def test_an_exact_match_is_near(self):
        self.assertTrue(fx.near(0.0))
        self.assertFalse(fx.near(None))
        self.assertFalse(fx.near(-0.6))


if __name__ == '__main__':
    unittest.main()
