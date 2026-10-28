# SPDX-License-Identifier: GPL-2.0-only
"""The caches are keyed on the emulator's source, from the .py files or, frozen, from the stamp of the build (bootcache.py)."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootcache  # noqa: E402


class SourceHashTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.here = Path(self.folder.name) / "emu"
        self.here.mkdir()
        patches = [mock.patch.object(bootcache, "HERE", self.here), mock.patch.object(bootcache, "_source", None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def hash(self, *folders):
        bootcache._source = None
        return bootcache.source_hash(*folders)

    def test_a_change_to_the_source_changes_the_hash(self):
        (self.here / "machine.py").write_text("a = 1\n")
        before = self.hash()
        (self.here / "machine.py").write_text("a = 2\n")
        self.assertNotEqual(self.hash(), before)

    def test_frozen_the_hash_is_the_stamp_of_the_build(self):
        (self.here / bootcache.STAMP).write_text("ab" * 32 + "\n")
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertEqual(self.hash(), "ab" * 32)
            self.assertEqual(self.hash("patch"), "ab" * 32)
        (self.here / bootcache.STAMP).write_text("cd" * 32)
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertEqual(self.hash(), "cd" * 32, "a new build gives new keys")

    def test_frozen_without_a_stamp_is_an_error_not_a_hash_of_nothing(self):
        with mock.patch.object(sys, "frozen", True, create=True):
            with self.assertRaises(FileNotFoundError):
                self.hash()


if __name__ == "__main__":
    unittest.main()
