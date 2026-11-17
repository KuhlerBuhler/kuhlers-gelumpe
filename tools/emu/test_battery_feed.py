"""The panel messages a case sends for the battery: message 6 with a reading (machine.battery), message 7 for mains or battery
(machine.power_source). Needs no firmware: the methods run on a stand-in that records what would go out on the panel line.

Measured in docs/messungen/2026-11-16-batterie-prozent.md."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import machine  # noqa: E402


class Panel:
    """Stands in for the machine: send() keeps the messages."""

    def __init__(self):
        self.sent, self.adapter = [], False

    def send(self, msg):
        self.sent.append(list(msg))


class BatteryFeedTest(unittest.TestCase):
    def test_a_reading_is_message_6(self):
        p = Panel()
        machine.Machine.battery(p, 0x70)
        machine.Machine.battery(p, 2)
        machine.Machine.battery(p, 255)
        self.assertEqual(p.sent, [[6, 0x70, 0, 0, 0], [6, 2, 0, 0, 0], [6, 255, 0, 0, 0]])

    def test_the_power_key_and_out_of_range_are_refused(self):
        p = Panel()
        for raw in (0, 1, 256, -1):
            with self.assertRaises(ValueError):
                machine.Machine.battery(p, raw)
        self.assertEqual(p.sent, [])

    def test_mains_or_battery_is_message_7(self):
        p = Panel()
        machine.Machine.power_source(p, True)
        self.assertTrue(p.adapter)
        machine.Machine.power_source(p, False)
        self.assertFalse(p.adapter)
        self.assertEqual(p.sent, [[7, 1, 0, 0, 0], [7, 0, 0, 0, 0]])


if __name__ == "__main__":
    unittest.main()
