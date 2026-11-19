"""Boot-stream safety checks for the recording DSP patch with synthetic data."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.dsp import dsp_extract
from tools.patch import recording_dsp as rec


class RecordingDspTests(unittest.TestCase):
    def test_synth_stream_has_its_own_mono_profile_and_authenticated_append(self):
        stream_start, length, final, length_word = 0xC00DFB80, 0x41C74, 0xC01217E4, 0xC000DD00
        raw = bytearray(b'\xFF' * 0x200100)
        first = rec.boot_header(1, 0xFFA00000, 0x2000) + bytes(0x2000)
        heaps = rec.boot_header(1, 0x01F02438, 60) + bytes(60)
        remaining = length - len(first) - len(heaps) - 32
        stream = first + heaps + rec.boot_header(1, 0x00100000, remaining) + bytes(remaining) + rec.boot_header(0x8001, 0xFFA00000)
        start = rec.file_offset(stream_start)
        raw[start:start + len(stream)] = stream
        struct.pack_into('<I', raw, rec.file_offset(length_word), length)
        hooks = {a: hashlib.sha256(bytes(10)).hexdigest() for a in (0xFFA0185A, 0xFFA018BA)}
        program = {'code': bytes(rec.PROGRAM_SIZE), 'hooks': [(a, b'\x11' * 10) for a in hooks]}
        with patch.object(rec, 'SYNTH_HOOK_HASHES', hooks, create=True):
            manifest = rec.build_patch(raw, program, build='synth')
            self.assertEqual(manifest['builds'], ['synth'])
            out = bytearray(raw)
            for change in manifest['changes']:
                data, offset = bytes.fromhex(change['bytes']), change['file']
                self.assertEqual(change['expect'], hashlib.sha256(out[offset:offset + len(data)]).hexdigest())
                out[offset:offset + len(data)] = data
            expanded = struct.unpack_from('<I', out, rec.file_offset(length_word))[0]
            blocks = list(dsp_extract.parse(out, start=stream_start, length=expanded))
            self.assertEqual((blocks[-2][3], blocks[-2][4]), (rec.CODE, rec.PROGRAM_SIZE))
            self.assertEqual(blocks[-1][1], rec.file_offset(final) + 16 + rec.PROGRAM_SIZE)
            raw[rec.file_offset(final) + 16] = 0
            with self.assertRaisesRegex(ValueError, 'occupied'):
                rec.build_patch(raw, program, build='synth')

    def setUp(self):
        self.raw = bytearray(b'\xFF' * 0x200100)
        first = rec.boot_header(1, 0xFFA00000, 0x2000) + bytes(0x2000)
        heaps = rec.boot_header(1, 0x01F02438, 60) + bytes(60)
        remaining = dsp_extract.STREAM_LEN - len(first) - len(heaps) - 32
        stream = first + heaps + rec.boot_header(1, 0x00100000, remaining) + bytes(remaining) + rec.boot_header(0x8001, 0xFFA00000)
        start = dsp_extract.file_offset(dsp_extract.STREAM_RAM)
        self.raw[start:start + len(stream)] = stream
        struct.pack_into('<I', self.raw, rec.file_offset(rec.LENGTH_WORD), len(stream))
        self.program = {'code': bytes(rec.PROGRAM_SIZE), 'hooks': [(a, b'\x11' * 10) for a in rec.HOOK_HASHES]}
        self.hashes = {a: hashlib.sha256(bytes(10)).hexdigest() for a in rec.HOOK_HASHES}

    def build(self, raw=None, program=None):
        with patch.object(rec, 'HOOK_HASHES', self.hashes):
            return rec.build_patch(self.raw if raw is None else raw, self.program if program is None else program)

    def test_checked_in_program_tracks_its_own_sources_and_magic_word(self):
        manifest = json.loads((ROOT / 'data/patches/native-recording-dsp.json').read_text())
        for name in ('recording_dsp.py', 'recording_dsp.s'):
            path = 'tools/patch/' + name
            self.assertEqual(manifest['sources'][path], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
        tail = b''.join(bytes.fromhex(next(c['bytes'] for c in manifest['changes'] if c['file'] == rec.file_offset(address)))
                        for address in (rec.FINAL_HEADER, rec.APPEND))
        _, target, count, _ = struct.unpack_from('<IIII', tail)
        self.assertEqual((target, count), (rec.CODE, rec.PROGRAM_SIZE))
        self.assertEqual(struct.unpack_from('<I', tail, 16 + rec.MAGIC_ADDRESS - rec.CODE)[0], rec.MAGIC)
        self.assertEqual(len(tail), 32 + rec.PROGRAM_SIZE)

    def test_extended_stream_loads_own_code_before_the_same_final_entry(self):
        manifest = self.build()
        out = bytearray(self.raw)
        for change in manifest['changes']:
            data, offset = bytes.fromhex(change['bytes']), change['file']
            self.assertEqual(change['expect'], hashlib.sha256(out[offset:offset + len(data)]).hexdigest())
            out[offset:offset + len(data)] = data
        length = struct.unpack_from('<I', out, rec.file_offset(rec.LENGTH_WORD))[0]
        blocks = list(dsp_extract.parse(out, length=length))
        self.assertEqual((blocks[-2][3], blocks[-2][4], blocks[-2][6]), (rec.CODE, rec.PROGRAM_SIZE, self.program['code']))
        self.assertEqual((blocks[-1][2], blocks[-1][3], blocks[-1][4]), (0x8001, 0xFFA00000, 0))
        self.assertEqual(manifest['ram'], [])
        self.assertEqual((manifest['dspMemory'][0]['at'], manifest['dspMemory'][0]['length']),
                         ('0x01F12000', rec.PROGRAM_SIZE))
        self.assertLessEqual(rec.APPEND + rec.PROGRAM_SIZE + 16, rec.RESERVE_END)
        self.assertEqual(len(out), len(self.raw))

    def test_headers_have_a_valid_signature_checksum_and_count(self):
        for flags, address, count in [(1, rec.CODE, rec.PROGRAM_SIZE), (0x8001, 0xFFA00000, 0)]:
            header = rec.boot_header(flags, address, count)
            code, target, length, argument = struct.unpack('<IIII', header)
            self.assertEqual(code >> 24, 0xAD)
            self.assertEqual(code & 65535, flags)
            self.assertEqual((target, length, argument), (address, count, 0))
            checksum = 0
            for value in header:
                checksum ^= value
            self.assertEqual(checksum, 0)

    def test_occupied_append_area_and_different_upload_length_are_rejected(self):
        for address, value in [(rec.APPEND, 0), (rec.LENGTH_WORD, 0)]:
            with self.subTest(address=hex(address)):
                raw = bytearray(self.raw)
                raw[rec.file_offset(address)] = value
                with self.assertRaises(ValueError):
                    self.build(raw)

    def test_changed_instructions_are_rejected_before_a_manifest_is_returned(self):
        raw = bytearray(self.raw)
        raw[dsp_extract.vsb_offset(raw, 0xFFA018DC)] = 1
        with self.assertRaisesRegex(ValueError, 'instructions'):
            self.build(raw)

    def test_an_existing_dsp_block_cannot_overlap_the_new_code_or_state(self):
        raw = bytearray(self.raw)
        start = dsp_extract.file_offset(dsp_extract.STREAM_RAM) + 16 + 0x2000
        raw[start:start + 16] = rec.boot_header(1, rec.CODE - 4, 60)
        with self.assertRaisesRegex(ValueError, 'already uses'):
            self.build(raw)

    def test_allocator_heap_cannot_extend_into_the_recording_program(self):
        raw = bytearray(self.raw)
        offset = dsp_extract.vsb_offset(raw, 0x01F02438)
        struct.pack_into('<III', raw, offset, rec.CODE - 4, rec.PROGRAM_SIZE + 4, 0)
        with self.assertRaisesRegex(ValueError, 'heap'):
            self.build(raw)

    def test_incomplete_or_oversized_programs_and_hooks_are_rejected(self):
        for program in [
            {'code': bytes(rec.PROGRAM_SIZE + 4), 'hooks': self.program['hooks']},
            {'code': self.program['code'], 'hooks': self.program['hooks'][:1]},
            {'code': self.program['code'], 'hooks': [(0xFFA018DC, bytes(12)), self.program['hooks'][1]]},
        ]:
            with self.subTest(program_size=len(program['code']), hooks=len(program['hooks'])):
                with self.assertRaises(ValueError):
                    self.build(program=program)


if __name__ == '__main__':
    unittest.main()
