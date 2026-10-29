"""Voice observations use generated memory and permit INFO and READ only."""
import struct
import unittest
import zlib
import contextlib
import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sample_voice_watch as p


class ReadOnlyAsk:
    def __init__(self):
        self.calls = []
        self.memory = {}

    def __call__(self, request):
        func = request[6]
        self.calls.append(func)
        if func == 0x60:
            reply, body = 0x68, struct.pack('<6I', 0, 1, 5, 1024, 0, 0)
        elif func == 0x61:
            at, size = struct.unpack('<2I', p.dec(request[7:-1]))
            data = bytes(self.memory.get(at + i, 0) for i in range(size))
            reply, body = 0x69, struct.pack('<4I', 0, at, size, zlib.crc32(data)) + data
        else:
            raise AssertionError('the watcher sent a command other than INFO or READ')
        return [0xF0, *request[1:6], reply, *p.enc(body), 0xF7]

    def put(self, at, data):
        self.memory.update({at + i: value for i, value in enumerate(data)})


class Watch(unittest.TestCase):
    def setup_link(self):
        ask = ReadOnlyAsk()
        link = p.ReadOnlyLink(ask, 0, 0x24)
        link.info()
        return ask, link

    def test_the_default_is_offline_and_observation_requires_a_version_and_report(self):
        self.assertFalse(p.arguments([]).observe)
        with self.assertRaises(ValueError):
            p.arguments(['--observe'])
        for seconds, rate in (('0', '5'), ('301', '5'), ('30', '0'), ('30', '11')):
            with self.subTest(seconds=seconds, rate=rate), self.assertRaises(ValueError):
                p.arguments(['--observe', '--vsb', 'own.vsb', '--json', 'new.json', '--seconds', seconds, '--hz', rate])

    def test_read_only_capabilities_are_sufficient_and_no_other_command_is_sent(self):
        ask, link = self.setup_link()
        snapshot = p.snapshot(link)
        self.assertTrue(snapshot['stable'])
        self.assertEqual(len(snapshot['voices']), 24)
        self.assertTrue(all(not v['busy'] for v in snapshot['voices']))
        self.assertEqual(set(ask.calls), {0x60, 0x61})

    def test_the_offline_entry_point_never_opens_midi(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(p.main([]), 0)
        self.assertFalse(json.loads(out.getvalue())['hardware_contact'])

    def test_write_and_execute_commands_are_refused_before_midi(self):
        ask, link = self.setup_link()
        for command in (0x62, 0x63, 0x72):
            with self.subTest(command=command), self.assertRaises(ValueError):
                link.call(command, b'', 0)
        self.assertEqual(ask.calls, [0x60])

    def test_both_native_flag_arrays_and_cached_imports_are_observed(self):
        ask, link = self.setup_link()
        ask.put(p.FLAG_SIGN, bytes([0x80]))
        ask.put(p.FLAG_BITS + 23, bytes([2]))
        for index in (0, 23):
            at = p.VOICES + p.STRIDE * index
            ask.put(at + 4, struct.pack('<I', 0xC069EA44 + index * 4))
            ask.put(at + 0x3A, struct.pack('<H', 600))
            ask.put(at + 0x40, struct.pack('<H', 550))
        snapshot = p.snapshot(link)
        for index in (0, 23):
            voice = snapshot['voices'][index]
            self.assertTrue(voice['busy'])
            self.assertEqual((voice['slot'], voice['import_number']), (600, 550))
        self.assertEqual(sum(v['busy'] for v in snapshot['voices']), 2)

    def test_a_retained_part_pointer_is_not_a_busy_voice(self):
        ask, link = self.setup_link()
        ask.put(p.VOICES + 4, struct.pack('<I', 0xC069EA44))
        voice = p.snapshot(link)['voices'][0]
        self.assertFalse(voice['busy'])
        self.assertEqual(voice['part'], 0xC069EA44)

    def test_a_changed_binding_or_flag_makes_the_snapshot_unstable(self):
        for at in (p.FLAG_SIGN, p.FLAG_BITS, p.VOICES + 0x40):
            with self.subTest(address=hex(at)):
                ask, link = self.setup_link()
                original = link.read
                count = 0

                def read(address, size):
                    nonlocal count
                    result = original(address, size)
                    if address == p.VOICES:
                        count += 1
                        if count == 1:
                            ask.put(at, bytes([1]))
                    return result

                link.read = read
                self.assertFalse(p.snapshot(link)['stable'])

    def test_a_fingerprint_mismatch_stops_before_voice_reads(self):
        ask, link = self.setup_link()
        with self.assertRaises(ValueError):
            p.check_fingerprints(link, [(0xC009115C, b'our generated code')])
        self.assertEqual(set(ask.calls), {0x60, 0x61})

    def test_a_packed_read_with_six_remaining_bytes_keeps_every_high_bit(self):
        ask, link = self.setup_link()
        data = bytes((i * 31 + 0x80) & 255 for i in range(144))
        ask.put(0xC1000000, data)
        self.assertEqual((16 + len(data)) % 7, 6)
        p.check_fingerprints(link, [(0xC1000000, data)])

    def test_a_bad_read_crc_stops_without_retry(self):
        ask = ReadOnlyAsk()

        def corrupted(request):
            reply = ask(request)
            if request[6] == 0x61:
                reply[-2] ^= 1
            return reply

        link = p.ReadOnlyLink(corrupted, 0, 0x24)
        link.info()
        with self.assertRaises(ValueError):
            link.read(p.FLAG_BITS, 24)
        self.assertEqual(ask.calls, [0x60, 0x61])

    def test_a_transport_exit_leaves_a_complete_failure_report(self):
        def unavailable(*args):
            raise SystemExit('our transport is unavailable')

        with tempfile.TemporaryDirectory(prefix='voice-watch-') as folder:
            original, report = Path(folder) / 'own.bin', Path(folder) / 'report.json'
            original.write_bytes(b'our generated firmware stand-in')
            transport = SimpleNamespace(midi_ask=unavailable, search=unavailable)
            with patch.object(p, 'source_fingerprints', return_value=[]), patch.dict(p.sys.modules, blue_report=transport):
                with contextlib.redirect_stdout(io.StringIO()):
                    status = p.main(['--observe', '--vsb', str(original), '--json', str(report)])
            result = json.loads(report.read_text())
            self.assertEqual(status, 1)
            self.assertFalse(result['writes'])
            self.assertEqual(result['snapshots'], [])
            self.assertFalse(result['result']['ok'])
            self.assertFalse(result['result']['hardware_identified'])


if __name__ == '__main__':
    unittest.main()
