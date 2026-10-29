"""The card probe uses generated records and native-file stand-ins, never device data."""
import sys
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'patch'))
import sample_store_probe as p
from test_sample_store import Machine, LIBRARY


class Guards(unittest.TestCase):
    def test_default_does_not_contact_midi(self):
        self.assertFalse(p.arguments([]).execute)
        with self.assertRaises(ValueError):
            p.arguments(['--execute'])
        with self.assertRaises(ValueError):
            p.arguments(['--execute', '--vsb', 'own.vsb'])
        self.assertTrue(p.arguments(['--execute', '--vsb', 'own.vsb', '--card-write-confirmed',
                                     '--json', 'report.json', '--backup-dir', 'backup']).execute)
        with self.assertRaises(ValueError):
            p.arguments(['--preflight'])
        self.assertTrue(p.arguments(['--preflight', '--vsb', 'own.vsb']).preflight)

    def test_scratch_excludes_the_task_stack_and_native_work_buffer(self):
        for at, length in p.REGIONS[1:]:
            self.assertGreaterEqual(at, 0xC274F000)
            self.assertLessEqual(at + length, 0xC4000000)
        for i, (at, length) in enumerate(p.REGIONS):
            for other, count in p.REGIONS[i + 1:]:
                self.assertFalse(at < other + count and other < at + length)

    def test_the_only_card_path_is_a_generated_test_name(self):
        self.assertTrue(p.test_path(b'SD:/BT123ABC.all'))
        for path in (b'SD:/e2sSample.all', b'SD:/BT123ABC.tmp', b'SD:/KORG/BT123ABC.all', b'SD:/BT../../x.all'):
            self.assertFalse(p.test_path(path))


class FakeLink:
    def __init__(self):
        self.machine = Machine(b'original library stays unchanged')
        for at, length in p.REGIONS[1:]:
            self.machine.uc.mem_map(at, length)
        self.machine.uc.mem_map(p.TIMER, 4096)
        self.machine.uc.mem_write(p.TIMER + 0x18, struct.pack('<I', 149999999))
        self.machine.uc.mem_write(p.TIMER + 0x20, struct.pack('<I', 0x80))
        self.machine.uc.mem_write(p.TIMER + 0x24, struct.pack('<I', 1))
        self.initial = {at: bytes(self.machine.uc.mem_read(at, count)) for at, count in p.REGIONS}
        self.unknown = False
        self.writes = []

    def read(self, at, count):
        return bytes(self.machine.uc.mem_read(at, count))

    def write_at(self, at, data):
        self.writes.append((at, len(data)))
        self.machine.uc.mem_write(at, data)

    def execute(self, token):
        if self.unknown:
            raise TimeoutError('return not confirmed')
        self.machine.symbols['probe'] = p.STUB
        self.machine.uc.ctl_flush_tb()
        if self.machine.call('probe', token) != p.MAGIC:
            raise ValueError('return marker differs')


class Probe(unittest.TestCase):
    def test_an_incomplete_host_backup_prevents_all_device_writes(self):
        link = FakeLink()
        with patch.object(p, 'idle', lambda *_: None):
            report = p.run(link, b'SD:/BT123ABC.all', backup=lambda at, data: len(data) - 1)
        self.assertFalse(report['ok'])
        self.assertEqual(link.writes, [])
        self.assertEqual(link.machine.writes, [])

    def test_the_same_uploaded_arm_program_puts_replaces_deletes_and_restores_ram(self):
        link = FakeLink()
        with patch.object(p, 'idle', lambda *_: None):
            report = p.run(link, b'SD:/BT123ABC.all')
        self.assertTrue(report['ok'], report)
        self.assertTrue(report['ram_restored'])
        self.assertEqual(link.machine.files[LIBRARY], b'original library stays unchanged')
        self.assertNotIn(b'SD:/BT123ABC.all', link.machine.files)
        self.assertNotIn(b'SD:/BT123ABC.txn', link.machine.files)
        for at, old in link.initial.items():
            self.assertEqual(link.read(at, len(old)), old)

    def test_an_existing_file_is_refused_without_card_writes(self):
        link = FakeLink()
        link.machine.files[b'SD:/BT123ABC.all'] = bytearray(b'existing file')
        with patch.object(p, 'idle', lambda *_: None):
            report = p.run(link, b'SD:/BT123ABC.all')
        self.assertFalse(report['ok'])
        self.assertEqual(link.machine.files[b'SD:/BT123ABC.all'], b'existing file')
        self.assertEqual(link.machine.writes, [])
        self.assertTrue(report['ram_restored'])

    def test_a_close_error_cannot_make_an_existing_library_look_absent(self):
        link = FakeLink()
        original = p.sampleset.build({500: ('Existing generated entry', 100)})
        link.machine.files[b'SD:/BT123ABC.all'] = bytearray(original)
        link.machine.close_error_at = 1
        link.machine.close_error_status = 4
        with patch.object(p, 'idle', lambda *_: None):
            report = p.run(link, b'SD:/BT123ABC.all')
        self.assertFalse(report['ok'])
        self.assertEqual(link.machine.files[b'SD:/BT123ABC.all'], original)
        self.assertEqual(link.machine.writes, [])
        self.assertTrue(report['ram_restored'])

    def test_unconfirmed_exec_never_sends_cleanup_or_retry(self):
        link = FakeLink()
        link.unknown = True
        with patch.object(p, 'idle', lambda *_: None):
            report = p.run(link, b'SD:/BT123ABC.all')
        self.assertFalse(report['ok'])
        self.assertFalse(report['ram_restored'])
        self.assertTrue(report['execution_unconfirmed'])
        self.assertEqual(link.writes[-1][0], p.STUB)
        self.assertEqual(link.machine.writes, [])

    def test_a_missing_upload_reply_never_sends_more_writes(self):
        link = FakeLink()
        original = link.write_at
        def failed(at, data):
            original(at, data)
            raise TimeoutError('upload acknowledgement missing')
        link.write_at = failed
        with patch.object(p, 'idle', lambda *_: None):
            report = p.run(link, b'SD:/BT123ABC.all')
        self.assertFalse(report['ok'])
        self.assertFalse(report['ram_restored'])
        self.assertTrue(report['communication_unconfirmed'])
        self.assertEqual(len(link.writes), 1)
        self.assertEqual(link.machine.writes, [])

    def test_a_transport_error_during_restore_is_reported_and_stops_cleanup(self):
        link = FakeLink()
        original = link.write_at
        def failed(at, data):
            original(at, data)
            if at == p.SOURCE and len(data) == p.REGIONS[3][1]:
                raise TimeoutError('restore acknowledgement missing')
        link.write_at = failed
        with patch.object(p, 'idle', lambda *_: None):
            report = p.run(link, b'SD:/BT123ABC.all')
        self.assertFalse(report['ok'])
        self.assertFalse(report['ram_restored'])
        self.assertTrue(report['communication_unconfirmed'])
        self.assertEqual(link.writes[-1], (p.SOURCE, p.REGIONS[3][1]))


if __name__ == '__main__':
    unittest.main()
