"""Exact DSP-stream validation, including appended recording code and upload length."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
from tools.patch.test_recording_dsp import RecordingDspTests as Fixture
from tools.patch import recording_dsp as rec
import recording_dsp_check
import stage2_memory_check


class RecordingStreamTests(unittest.TestCase):
    def setUp(self):
        fixture = Fixture()
        fixture.setUp()
        self.raw, self.hashes = fixture.raw, fixture.hashes
        self.manifest = fixture.build()
        self.patched = bytearray(self.raw)
        for change in self.manifest['changes']:
            data = bytes.fromhex(change['bytes'])
            self.patched[change['file']:change['file'] + len(data)] = data
        self.span = slice(0xF9F10, rec.file_offset(rec.APPEND))

    def check(self, patched):
        with patch.object(recording_dsp_check, 'load_manifest', return_value=self.manifest), patch.object(rec, 'HOOK_HASHES', self.hashes):
            return stage2_memory_check.dsp_stream(self.raw, patched, self.span)[0]

    def test_exact_recording_program_and_unchanged_program_pass(self):
        self.assertTrue(self.check(self.raw))
        self.assertTrue(self.check(self.patched))

    def test_appended_code_redirects_final_header_and_length_are_checked(self):
        for offset in (rec.file_offset(rec.APPEND) + 20,
                       rec.file_offset(rec.APPEND) + rec.PROGRAM_SIZE,
                       self.manifest['changes'][0]['file'], rec.file_offset(rec.LENGTH_WORD)):
            damaged = bytearray(self.patched)
            damaged[offset] ^= 1
            self.assertFalse(self.check(damaged), hex(offset))

    def test_upload_length_cannot_change_without_a_matching_program(self):
        damaged = bytearray(self.raw)
        damaged[rec.file_offset(rec.LENGTH_WORD)] ^= 1
        self.assertFalse(self.check(damaged))

    def test_recording_and_stage2_edits_must_both_match_exactly(self):
        offset = 0xF9F10 + 100
        combined = bytearray(self.patched)
        combined[offset:offset + 4] = b'\x55' * 4
        with patch.object(stage2_memory_check.spec, 'sites', return_value=[(offset, bytes(4), b'\x55' * 4, 'own fixture')]):
            self.assertTrue(self.check(combined))
            combined[offset + 4] ^= 1
            self.assertFalse(self.check(combined))
