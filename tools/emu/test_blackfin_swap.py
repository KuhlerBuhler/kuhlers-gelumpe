# SPDX-License-Identifier: GPL-2.0-only
"""Swap PCM checks read executed DSP memory and propagate backend failures."""
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from blackfin_backend import BlackfinBackend, BackendError
import blackfin_swap_cases
from swap_cases import Box
from test_blackfin_backend import WORKER, ENTRY, DATA, program


class SessionDeadline(unittest.TestCase):
    def test_deadline_covers_slices_without_an_arm_instruction(self):
        slices = []
        machine = SimpleNamespace(run_slice=lambda limit=None: slices.append(limit))
        blackfin_swap_cases.bound_session(machine, 10)
        with patch.object(blackfin_swap_cases.time, 'monotonic', return_value=9):
            machine.run_slice(limit=.02)
        with patch.object(blackfin_swap_cases.time, 'monotonic', return_value=10):
            with self.assertRaisesRegex(BackendError, 'session deadline'):
                machine.run_slice(limit=.04)
        self.assertEqual(slices, [.02])


class CandidateCode(unittest.TestCase):
    def setUp(self):
        self.screens = 0xC0340000
        self.payload = bytearray(0x200000)
        for address, data in blackfin_swap_cases.spec.build_code(self.screens)[0]:
            at = address - 0xC0000000
            self.payload[at:at + len(data)] = data

    def test_generated_code_matches_the_current_builder(self):
        blackfin_swap_cases.verify_patch_code(self.payload, self.screens)

    def test_stale_code_is_rejected_before_native_startup(self):
        self.payload[blackfin_swap_cases.spec.CODE3 - 0xC0000000] ^= 1
        with self.assertRaisesRegex(ValueError, 'code differs.*rebuild'):
            blackfin_swap_cases.verify_patch_code(self.payload, self.screens)


@unittest.skipUnless(WORKER, 'build a Blackfin worker (tools/dsp/build_qemu.py) or set BFIN_WORKER')
class NativeSwapMemory(unittest.TestCase):
    def test_pcm_is_read_from_executed_dsp_memory(self):
        with BlackfinBackend(WORKER) as backend:
            box = Box.__new__(Box)
            box.m = SimpleNamespace(dsp_backend=SimpleNamespace(backend=backend))
            box.dsp = {DATA: 0xDEAD, DATA + 2: 0xBEEF}
            backend.write(ENTRY, program())
            backend.set_register(53, ENTRY)
            backend.run(6)
            self.assertEqual(box.dsp_bytes(DATA, 4), struct.pack('<I', 7))

    def test_failed_backend_cannot_fall_back_to_recorded_pcm(self):
        with BlackfinBackend(WORKER) as backend:
            box = Box.__new__(Box)
            box.m = SimpleNamespace(dsp_backend=SimpleNamespace(backend=backend))
            box.dsp = {DATA: 7, DATA + 2: 0}
            backend.close()
            with self.assertRaises(BackendError):
                box.dsp_bytes(DATA, 4)
