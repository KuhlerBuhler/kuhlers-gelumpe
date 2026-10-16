# SPDX-License-Identifier: GPL-2.0-only
"""The FAT32 volume editor, on images it formats itself (no firmware, no Unicorn)."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fat32  # noqa: E402
from fat32 import BadName, CardFull, Exists, FatError, NotEmpty, NotFound, Volume  # noqa: E402

MIB = 1024 * 1024


def fsck(image):
    """fsck_msdos on the macOS loop device of an image file; None where that is not possible."""
    if sys.platform != "darwin" or not shutil.which("hdiutil"):
        return None
    attach = subprocess.run(["hdiutil", "attach", "-nomount", "-imagekey", "diskimage-class=CRawDiskImage", str(image)],
                            capture_output=True, text=True)
    if attach.returncode:
        return None
    disk = re.search(r"/dev/disk\d+", attach.stdout).group(0)
    try:
        r = subprocess.run(["fsck_msdos", "-n", disk.replace("/dev/", "/dev/r") + "s1"], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr
    finally:
        subprocess.run(["hdiutil", "detach", disk], capture_output=True)


class VolumeTest(unittest.TestCase):
    def setUp(self):
        self.img = fat32.format_image(64 * MIB, volume_id=0x1234ABCD)
        self.v = Volume(self.img)

    def tearDown(self):
        self.v.close()

    def names(self, path="/"):
        return sorted(e.name for e in self.v.listdir(path))

    def test_a_fresh_card_is_empty_and_consistent(self):
        self.assertEqual(self.v.listdir("/"), [])
        self.assertEqual(self.v.check(), [])
        self.assertEqual(self.v.label, "GELUMPE")
        self.assertGreaterEqual(self.v.clusters, fat32.MIN_CLUSTERS)
        self.assertEqual(self.v.usage()["free"] + self.v.csz, self.v.capacity(), "only the root directory is used")

    def test_geometry_keeps_the_cluster_count_above_the_fat32_limit(self):
        for mb in (64, 128, 256, 512, 1024, 4096):
            spc, fatsz, clusters = fat32.geometry(mb * MIB)
            self.assertGreaterEqual(clusters, fat32.MIN_CLUSTERS, mb)
            self.assertLessEqual(spc, 64)
        self.assertEqual(fat32.geometry(128 * MIB)[0], 2)
        with self.assertRaises(FatError):
            fat32.geometry(32 * MIB)

    def test_a_file_comes_back_byte_for_byte_with_its_folders(self):
        data = os.urandom(70_001)
        self.v.write("/KORG/hacktribe/Sample/501_kick.wav", data)
        self.assertEqual(self.v.read("/KORG/hacktribe/Sample/501_kick.wav"), data)
        self.assertEqual(self.v.read("korg/HACKTRIBE/sample/501_KICK.WAV"), data, "names ignore case")
        self.assertEqual(self.names(), ["KORG"])
        self.assertEqual(self.names("/KORG/hacktribe"), ["Sample"])
        self.assertEqual(self.v.check(), [])

    def test_empty_files_and_files_of_exactly_one_cluster(self):
        self.v.write("/empty.txt", b"")
        one = bytes(range(256)) * (self.v.csz // 256)
        self.v.write("/one.bin", one)
        self.assertEqual(self.v.read("/empty.txt"), b"")
        self.assertEqual(self.v.read("/one.bin"), one)
        self.assertEqual(self.v.stat("/empty.txt").cluster, 0)
        self.assertEqual(self.v.check(), [])

    def test_names_with_spaces_case_and_unicode_keep_their_long_form(self):
        names = ["Kick Drum 01.wav", "snare.WAV", "Ärger über Öl.wav", "a" * 13 + ".wav", "x" * 255, "UPPER.WAV", "t.wav", ".hidden"]
        for n in names:
            self.v.write("/" + n, n.encode())
        self.assertEqual(self.names(), sorted(names))
        for n in names:
            self.assertEqual(self.v.read("/" + n), n.encode())
        self.assertEqual(self.v.check(), [])

    def test_short_aliases_of_long_names_never_collide(self):
        for n in ["Long Name A.wav", "Long Name B.wav", "Long Name C.wav", "Long Name D.wav"]:
            self.v.write("/" + n, b"x")
        shorts = [e.short for e in self.v.listdir("/")]
        self.assertEqual(len(set(shorts)), 4)
        self.assertEqual(shorts[0], b"LONGNA~1WAV")
        self.assertEqual(self.v.read("/LONGNA~2.WAV"), b"x", "the alias opens the file too")

    def test_a_name_that_already_fits_8_3_gets_no_extra_entries(self):
        self.v.write("/T.WAV", b"1")
        self.assertEqual(len(self.v.listdir("/")[0].slots), 1)
        self.v.write("/501_tst_root.wav", b"2")
        self.assertGreater(len(self.v.stat("/501_tst_root.wav").slots), 1)

    def test_refuses_what_fat_cannot_hold(self):
        for bad in ["/a:b.wav", "/q?.wav", "/x/../y", "/trailing.", "/ leading", "/" + "z" * 256, "/ctl\x01.wav"]:
            with self.assertRaises(BadName, msg=bad):
                self.v.write(bad, b"x")
        with self.assertRaises(BadName):
            self.v.write("/", b"x")
        self.assertEqual(self.v.check(), [])

    def test_a_second_write_needs_overwrite_and_replaces_in_place(self):
        self.v.write("/a.wav", b"one")
        with self.assertRaises(Exists):
            self.v.write("/A.WAV", b"two")
        self.assertEqual(self.v.read("/a.wav"), b"one")
        free = self.v.free
        self.v.write("/a.wav", b"x" * 5000, overwrite=True)
        self.assertEqual(self.v.read("/a.wav"), b"x" * 5000)
        self.assertEqual(len(self.names()), 1)
        self.v.write("/a.wav", b"y", overwrite=True)
        self.assertEqual(self.v.free, free, "the clusters of the old content were given back")
        self.v.mkdir("/dir")
        with self.assertRaises(Exists):
            self.v.write("/dir", b"x", overwrite=True)
        self.assertEqual(self.v.check(), [])

    def test_delete_gives_the_space_back(self):
        free = self.v.free
        self.v.write("/a/b/c.wav", os.urandom(50_000))
        self.v.write("/a/d.wav", os.urandom(1))
        with self.assertRaises(NotEmpty):
            self.v.delete("/a")
        self.v.delete("/a/b/c.wav")
        self.v.delete("/a/b")
        self.assertEqual(self.names("/a"), ["d.wav"])
        self.v.delete("/a", recursive=True)
        self.assertEqual(self.v.listdir("/"), [])
        self.assertEqual(self.v.free, free)
        self.assertEqual(self.v.check(), [])
        with self.assertRaises(NotFound):
            self.v.delete("/a")
        with self.assertRaises(BadName):
            self.v.delete("/")

    def test_deleted_directory_slots_are_reused(self):
        for i in range(10):
            self.v.write(f"/f{i}.wav", b"x")
        freed = self.v.stat("/f3.wav").slots
        self.v.delete("/f3.wav")
        self.v.write("/g3.wav", b"y")
        self.assertEqual(self.v.stat("/g3.wav").slots, freed)
        self.assertEqual(len(self.names()), 10)
        self.assertEqual(self.v.check(), [])

    def test_a_directory_grows_past_one_cluster(self):
        for i in range(120):
            self.v.write(f"/Sample number {i:03d}.wav", f"{i}".encode())
        self.assertEqual(len(self.v.listdir("/")), 120)
        self.assertGreater(len(self.v.chain(self.v.root)), 1)
        self.assertEqual(self.v.read("/Sample number 119.wav"), b"119")
        self.assertEqual(self.v.check(), [])

    def test_a_full_card_says_so_and_loses_nothing(self):
        big = os.urandom(self.v.csz * 1000)
        self.v.write("/keep.bin", big)
        with self.assertRaises(CardFull):
            self.v.write("/huge.bin", bytes(self.v.free_bytes() + self.v.csz * 10))
        self.assertEqual(self.v.read("/keep.bin"), big)
        with self.assertRaises(CardFull):
            self.v.write("/keep.bin", bytes(self.v.free_bytes() + len(big) + self.v.csz * 10), overwrite=True)
        self.assertEqual(self.v.read("/keep.bin"), big, "a failed overwrite leaves the old file")
        self.assertEqual(self.v.check(), [])

    def test_fragmented_files_read_back(self):
        for i in range(6):
            self.v.write(f"/f{i}.bin", bytes([i]) * (self.v.csz * 3))
        for i in (1, 3):
            self.v.delete(f"/f{i}.bin")
        self.v.hint = 3
        data = os.urandom(self.v.csz * 8)
        self.v.write("/frag.bin", data)
        self.assertNotEqual(len(self.v.chain(self.v.stat("/frag.bin").cluster)), 0)
        chain = self.v.chain(self.v.stat("/frag.bin").cluster)
        self.assertNotEqual(chain, list(range(chain[0], chain[0] + len(chain))), "the file has to be in pieces")
        self.assertEqual(self.v.read("/frag.bin"), data)
        self.assertEqual(self.v.check(), [])

    def test_both_fat_copies_and_fsinfo_follow_every_change(self):
        self.v.write("/a.bin", os.urandom(30_000))
        self.v.write("/d/b.bin", os.urandom(9_000))
        self.v.delete("/a.bin")
        self.assertEqual(self.v.check(), [])
        again = Volume(self.img)
        self.assertEqual(again.free, self.v.free)
        o = (self.v.ps + self.v.fsinfo) * 512
        self.assertEqual(int.from_bytes(self.img[o + 488:o + 492], "little"), self.v.free)
        again.close()

    def test_a_volume_without_a_partition_table_opens_too(self):
        self.v.write("/KORG/a.wav", b"hello")
        ps = self.v.ps * 512
        bare = bytearray(self.img[ps:])
        self.v.close()
        # the hidden-sectors field points at the old start, which a reader of a bare volume ignores
        w = Volume(bare)
        self.assertEqual(w.read("/KORG/a.wav"), b"hello")
        w.close()
        self.v = Volume(self.img)

    def test_walk_lists_everything_with_folders_first(self):
        self.v.write("/b/y.wav", b"1")
        self.v.write("/a.wav", b"22")
        self.assertEqual([p for p, _ in self.v.walk()], ["/b", "/b/y.wav", "/a.wav"])
        self.assertEqual([p for p, _ in self.v.walk("/b")], ["/b/y.wav"])

    def test_the_change_hook_runs_after_each_edit_and_after_a_failed_one(self):
        calls = []
        v = Volume(self.img, on_change=lambda: calls.append(1))
        v.write("/a", b"x")
        v.mkdir("/d")
        v.delete("/a")
        self.assertEqual(len(calls), 3)
        with self.assertRaises(NotFound):
            v.delete("/missing")
        self.assertEqual(len(calls), 4)
        v.close()

    def test_a_modified_timestamp_is_read_back(self):
        fat32.clock, saved = (lambda: 1_700_000_000.0), fat32.clock
        try:
            self.v.write("/t.bin", b"x")
        finally:
            fat32.clock = saved
        self.assertAlmostEqual(self.v.stat("/t.bin").mtime, 1_700_000_000.0, delta=2)

    def test_a_garbage_image_is_refused(self):
        with self.assertRaises(FatError):
            Volume(bytearray(1024 * 1024))
        bad = bytearray(self.img)
        bad[446 + 4] = 0x83
        bad[fat32.PARTITION_START * 512 + 82] = 0
        with self.assertRaises(FatError):
            Volume(bad)

    def test_a_fat16_card_from_the_firmware_is_named_as_that(self):
        fat16 = bytearray(self.img)
        fat16[446 + 4] = 0x06                      # what CARD FORMAT writes on a 1 GiB card
        fat16[fat32.PARTITION_START * 512 + 82] = 0
        with self.assertRaises(FatError) as e:
            Volume(fat16)
        self.assertIn("FAT16", str(e.exception))

    @unittest.skipUnless(sys.platform == "darwin" and shutil.which("hdiutil"), "needs macOS and hdiutil")
    def test_fsck_msdos_accepts_what_this_writes(self):
        self.v.write("/KORG/hacktribe/Sample/501_Kick Drum.wav", os.urandom(40_000))
        self.v.write("/Ärger.wav", b"x" * 3000)
        for i in range(60):
            self.v.write(f"/many/File number {i}.wav", b"z" * (i * 700))
        self.v.delete("/many/File number 7.wav")
        self.v.write("/empty", b"")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "card.img"
            path.write_bytes(bytes(self.img))
            result = fsck(path)
        if result is None:
            self.skipTest("no loop device available")
        self.assertEqual(result[0], 0, result[1])


if __name__ == "__main__":
    unittest.main()
