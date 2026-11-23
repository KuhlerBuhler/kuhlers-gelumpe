# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import blackfin_worker


class Find(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.home = Path(self.dir.name)
        environ = patch.dict(os.environ, {'GELUMPE_DSP': self.dir.name})
        environ.start()
        self.addCleanup(environ.stop)
        os.environ.pop('BFIN_WORKER', None)
        blackfin_worker._warned = False

    def build(self, relative):
        path = self.home / relative
        path.parent.mkdir(parents=True)
        path.write_text('#!/bin/sh\n')
        path.chmod(0o755)
        return str(path)

    def find(self, chosen=None):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            return blackfin_worker.find(chosen), err.getvalue()

    def test_none_without_a_build(self):
        self.assertEqual(self.find(), (None, ''))

    def test_qemu_is_the_default(self):
        self.build(blackfin_worker.GNU)
        qemu = self.build(blackfin_worker.QEMU)
        self.assertEqual(self.find(), (qemu, ''))

    def test_gnu_without_qemu_says_so(self):
        gnu = self.build(blackfin_worker.GNU)
        worker, err = self.find()
        self.assertEqual(worker, gnu)
        self.assertIn('no QEMU worker', err)

    def test_explicit_choice_wins(self):
        self.build(blackfin_worker.QEMU)
        os.environ['BFIN_WORKER'] = '/x/blackfin-worker'
        self.assertEqual(self.find(), ('/x/blackfin-worker', ''))
        self.assertEqual(self.find('/y/w'), ('/y/w', ''))


if __name__ == '__main__':
    unittest.main()
