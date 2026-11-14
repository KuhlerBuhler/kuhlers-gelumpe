# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded frame observations with generated programs."""
import os
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'dsp'))
from blackfin_probe import observe_frames
from blackfin_backend import BlackfinBackend, BackendError

WORKER = os.environ.get('BFIN_WORKER')


class ObservationFailures(unittest.TestCase):
    def test_missing_entry_is_a_failed_observation(self):
        backend = Mock()
        backend.run.return_value = dict(reached=False, steps=100, pc=0x2000)
        with self.assertRaisesRegex(BackendError, 'not reached'):
            observe_frames(SimpleNamespace(backend=backend), 1, 0x1000, 100)
        backend.set_register.assert_not_called()
        backend.sport_status.assert_not_called()

    def test_abort_is_not_replaced_by_a_success_report(self):
        backend = Mock()
        backend.run.side_effect = BackendError('replay aborted')
        with self.assertRaisesRegex(BackendError, 'replay aborted'):
            observe_frames(SimpleNamespace(backend=backend), 1, 0x1000)
        backend.sport_status.assert_not_called()

    def test_observation_rejects_unbounded_or_unaligned_requests(self):
        for frames, entry in ((0, 0x1000), (1001, 0x1000), (1, 0x1001)):
            with self.subTest(frames=frames, entry=entry), self.assertRaises(ValueError):
                observe_frames(SimpleNamespace(backend=Mock()), frames, entry)


@unittest.skipUnless(WORKER, 'build the GNU Blackfin worker and set BFIN_WORKER')
class GeneratedObservation(unittest.TestCase):
    def test_breakpoint_observation_never_replaces_native_control_flow(self):
        with BlackfinBackend(WORKER, operating=True) as backend:
            backend.configure_sport(core_hz=4800000)
            backend.write(0x1000, struct.pack('<H', 0x2000))
            backend.set_register(53, 0x1000)
            backend.set_register(48, 0x32)
            report = observe_frames(SimpleNamespace(backend=backend), 4, 0x1000)
            self.assertEqual(report['completed'], 4)
            entries = report['entries']
            self.assertEqual([e['pc'] for e in entries], [0x1000] * 5)
            self.assertEqual(entries[-1]['cycles'] - entries[0]['cycles'], 20)
            self.assertEqual(report['sport']['rx_frames'], 0)


if __name__ == '__main__':
    unittest.main()
