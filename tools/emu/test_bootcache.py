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


class PruneTest(unittest.TestCase):
    DAY = 86400

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        env = mock.patch.dict("os.environ", {"GELUMPE_CACHE_DIR": self.folder.name, "GELUMPE_CACHE": ""})
        env.start()
        self.addCleanup(env.stop)
        mem = mock.patch.object(bootcache, "_memory", {})
        mem.start()
        self.addCleanup(mem.stop)
        self.now = 100 * self.DAY

    def file(self, kind, key, age_days):
        path = bootcache.cache_dir(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 10)
        t = self.now - age_days * self.DAY
        import os
        os.utime(path, (t, t))
        return path

    def test_old_files_go_new_ones_stay(self):
        old = self.file("task", "a", 8)
        new = self.file("power-on", "b", 2)
        self.assertEqual(bootcache.prune(7, now=self.now), 10)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())

    def test_a_read_keeps_an_old_file(self):
        path = self.file("boot", "c", 30)
        self.assertEqual(bootcache.read("boot", "c"), b"x" * 10)
        bootcache.prune(7)
        self.assertTrue(path.exists(), "a file read today is in use")

    def test_once_a_day(self):
        self.file("task", "a", 8)
        bootcache.prune(7, now=self.now)
        late = self.file("task", "b", 8)
        self.assertEqual(bootcache.prune(7, now=self.now + self.DAY / 2), 0)
        self.assertTrue(late.exists())
        self.assertEqual(bootcache.prune(7, now=self.now + self.DAY), 10)

    def test_zero_days_or_cache_off_keeps_everything(self):
        path = self.file("task", "a", 300)
        self.assertEqual(bootcache.prune(0, now=self.now), 0)
        with mock.patch.dict("os.environ", {"GELUMPE_CACHE": "off"}):
            self.assertEqual(bootcache.prune(7, now=self.now), 0)
        self.assertTrue(path.exists())


class PowerOnTest(unittest.TestCase):
    def test_a_machine_with_the_dsp_model_boots_for_real(self):
        m = mock.Mock(time_ns=0, dsp_model=object())
        with mock.patch.object(bootcache, "_power_on_key") as key, mock.patch.object(bootcache, "read") as read:
            bootcache.power_on(m, 2.0)
        key.assert_not_called()
        read.assert_not_called()
        m.finish_boot.assert_called_once_with()
        m.run_until.assert_called_once_with(2.0)
        m.restore.assert_not_called()


if __name__ == "__main__":
    unittest.main()
