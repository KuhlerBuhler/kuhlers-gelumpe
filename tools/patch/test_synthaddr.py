"""Rejected candidates cannot be used, and failed retargeting leaves addresses intact."""
import unittest
from unittest.mock import patch

import synthaddr


class Addresses(unittest.TestCase):
    def test_a_rejected_candidate_blocks_even_an_automatic_entry(self):
        rows = [('auto.json', {'from': '0xC0001000', 'to': '0xC0002000'}),
                ('review.json', {'from': '0xC0001000', 'to': '0xC0002000', 'rejected': True})]
        with patch.object(synthaddr, 'entries', return_value=rows), patch.object(synthaddr, '_table', None):
            with self.assertRaises(synthaddr.Unmapped):
                synthaddr.tr(0xC0001000)

    def test_missing_addresses_do_not_partially_retarget_a_builder(self):
        namespace = {'FIRST': 0xC0001000, 'SECOND': 0xC0003000}
        with patch.object(synthaddr, '_table', {0xC0001000: 0xC0002000}):
            with self.assertRaises(SystemExit):
                synthaddr.use(namespace, ['FIRST', 'SECOND'], 'synth')
        self.assertEqual(namespace['FIRST'], 0xC0001000)
        self.assertEqual(namespace['SECOND'], 0xC0003000)

    def test_frozen_runtime_reads_its_bundled_address_maps(self):
        import tempfile
        import subprocess
        import sys
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            maps = Path(folder) / 'data/synth-map'
            maps.mkdir(parents=True)
            (maps / 'test.json').write_text(json.dumps({'entries': [{'from': '0xC0001000', 'to': '0xC0002000'}]}))
            code = "import sys,runpy; sys._MEIPASS=sys.argv[1]; ns=runpy.run_path(sys.argv[2]); assert ns['tr'](0xC0001000)==0xC0002000"
            result = subprocess.run([sys.executable, '-c', code, folder, synthaddr.__file__], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
