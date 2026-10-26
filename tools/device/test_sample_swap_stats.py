"""The swap watcher against a link that answers from memory made here; no device."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "patch"))

import sample_swap
import sample_swap_stats as stats


class Link:
    def __init__(self, states):
        self.states = list(states)
        self.reads = 0
        self.writes = 0

    def read(self, address, count):
        assert address == sample_swap.STATE
        self.reads += 1
        state = self.states[min(self.reads - 1, len(self.states) - 1)]
        raw = bytearray(count)
        for name, value in state.items():
            struct.pack_into("<I", raw, sample_swap.OFF[name], value)
        return bytes(raw)


class Watch(unittest.TestCase):
    def run_watch(self, states):
        t = [0.0]
        return stats.watch(Link(states), 2.0, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s))

    def test_reports_each_new_load_with_its_source_and_speed(self):
        on = dict(MODE=1, STAT_COUNT=4)
        card = dict(on, STAT_COUNT=5, STAT_SRC=0, STAT_BYTES=1048576, STAT_TICKS=50_000_000)
        ram = dict(on, STAT_COUNT=6, STAT_SRC=1, STAT_BYTES=1048576, STAT_TICKS=13_500_000)
        lines = self.run_watch([on, on, card, card, ram])
        self.assertEqual([l["source"] for l in lines], ["card", "ram"])
        self.assertEqual(lines[0]["mib_per_second"], 3.0)
        self.assertAlmostEqual(lines[1]["milliseconds"], 90.0)

    def test_refuses_when_the_swap_is_off(self):
        with self.assertRaises(ValueError):
            self.run_watch([dict(MODE=0)])

    def test_stops_when_the_swap_switches_itself_off(self):
        lines = self.run_watch([dict(MODE=1, STAT_COUNT=1), dict(MODE=2, STAT_COUNT=1)])
        self.assertEqual(lines, [dict(event="swap off", mode=2)])

    def test_offline_plan_sends_nothing(self):
        self.assertIsNone(stats.main([]))


if __name__ == "__main__":
    unittest.main()
