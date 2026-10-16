"""Code candidates must match completely, including candidates outside the alignment."""
import unittest

import fwmap


class CodeCandidates(unittest.TestCase):
    def setUp(self):
        self.f = object.__new__(fwmap.FirmwareMap)
        ref = [0xE92D4010, 0xE3A00001, 0xEB000123, 0xE59F1050] * 4
        tgt = [0xE92D4010, 0xE3A00001, 0xEB000456, 0xE59F1070] * 4
        self.f.m_ref = [fwmap._mask(w) for w in ref]
        self.f.m_tgt = [0] * 4 + [fwmap._mask(w) for w in tgt]

    def test_explicit_candidate_compares_the_code_without_guessing_a_run(self):
        self.assertTrue(self.f.same_code(fwmap.BASE, target=fwmap.BASE + 16))
        self.f.m_tgt[-1] ^= 1
        self.assertFalse(self.f.same_code(fwmap.BASE, target=fwmap.BASE + 16))

    def test_short_outside_and_unaligned_windows_do_not_pass(self):
        for a, b in [(fwmap.BASE + 4, fwmap.BASE + 20), (fwmap.BASE - 4, fwmap.BASE),
                     (fwmap.BASE + 1, fwmap.BASE + 16), (fwmap.BASE, fwmap.BASE + 17)]:
            self.assertFalse(self.f.same_code(a, target=b))
