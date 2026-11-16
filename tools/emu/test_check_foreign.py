# SPDX-License-Identifier: GPL-2.0-only
"""check.py start_phase_checks(): a patch of ours keeps the strict start phase check, a foreign one (IPS, bsdiff) has none."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import start_phase_checks  # noqa: E402

EVERYWHERE = {"code": [(0, 1 << 40)], "data": []}
RUNS = [(0x1100, 4)]            # a changed run in start code


class StartPhase(unittest.TestCase):
    def test_a_change_in_start_code_fails_for_a_patch_of_ours(self):
        checks = start_phase_checks(RUNS, EVERYWHERE, [], [])
        self.assertEqual([(c["id"], c["ok"]) for c in checks], [("start_phase", False)])

    def test_the_patch_can_name_it_as_an_exception(self):
        checks = start_phase_checks(RUNS, EVERYWHERE, [], [(0x1100, 4)])
        self.assertEqual([(c["id"], c["ok"]) for c in checks], [("start_phase", True), ("start_phase_exceptions", True)])

    def test_a_foreign_patch_has_no_start_phase_check(self):
        self.assertEqual(start_phase_checks(RUNS, EVERYWHERE, [], [], foreign=True), [])


if __name__ == "__main__":
    unittest.main()
