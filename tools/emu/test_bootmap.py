"""The start trace ends before main-screen frame work."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import bootmap


class BoundaryMachine:
    main_at = 23_000_000

    def __init__(self, payload, flash):
        self.profile = SimpleNamespace(build=payload.decode())
        self.time_ns = 0
        self.asserts = []
        self.powered = True
        self.pre_main_seen = False
        self.main_frame_seen = False
        self.events = {}

    def run_until(self, seconds):
        self.time_ns = round(seconds * 1e9)
        self.pre_main_seen |= self.time_ns >= 21_000_000
        self.main_frame_seen |= self.main_at is not None and self.time_ns >= 25_000_000

    def screen(self):
        return 1 if self.main_at is not None and self.time_ns >= self.main_at else 9

    def loading(self):
        return False

    def note(self, name):
        self.events[name] = self.time_ns


class TraceBoundary(unittest.TestCase):
    def test_each_build_keeps_startup_work_but_stops_before_main_frame(self):
        with patch.object(bootmap, 'Probe', BoundaryMachine):
            for build in (b'hacktribe', b'stock', b'synth'):
                with self.subTest(build=build):
                    m = bootmap.run(build, None, seconds=0.1)
                    self.assertTrue(m.pre_main_seen)
                    self.assertFalse(m.main_frame_seen)
                    self.assertIn('screen_1', m.events)

    def test_a_start_mode_without_main_keeps_its_whole_observation(self):
        with patch.object(bootmap, 'Probe', BoundaryMachine), patch.object(BoundaryMachine, 'main_at', None):
            m = bootmap.run(b'hacktribe', None, seconds=0.1)
        self.assertGreaterEqual(m.time_ns, 100_000_000)
        self.assertTrue(m.pre_main_seen)
        self.assertNotIn('screen_1', m.events)


if __name__ == '__main__':
    unittest.main()
