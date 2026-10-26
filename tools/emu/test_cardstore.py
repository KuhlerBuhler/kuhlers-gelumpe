# SPDX-License-Identifier: GPL-2.0-only
"""The card folder: inserting it, protecting it, mirroring the firmware's writes back, and the firmware picking the folder name."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardstore  # noqa: E402
import fat32  # noqa: E402
from cardstore import CardError, CardStore, card_folder  # noqa: E402
from fat32 import Volume  # noqa: E402

MIB = 1024 * 1024


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "sd"
        self.stores = []
        self.opened = []

    def tearDown(self):
        for s in self.stores:
            s.close()
        for where, dirs, _ in os.walk(self.tmp.name):
            for n in dirs:
                os.chmod(os.path.join(where, n), 0o755)
        self.tmp.cleanup()

    def store(self, **kw):
        s = CardStore(self.root, opener=self.opened.append, **kw)
        self.stores.append(s)
        return s

    @property
    def card(self):
        return self.root / "card"

    def firmware_writes(self, s, path, data=None, delete=False):
        """What the firmware does to the card: through the volume, on the medium it holds."""
        with s.image.lock:
            v = Volume(s.image.data, on_change=s.image.touch)
            try:
                v.delete(path, recursive=True) if delete else v.write(path, data, overwrite=True)
            finally:
                v.close()

    def make_folder(self):
        c = self.card
        (c / "drums" / "808").mkdir(parents=True)
        (c / "drums" / "kick.wav").write_bytes(b"K" * 5000)
        (c / "drums" / "808" / "Sub Bass: low?.wav").write_bytes(b"S" * 300)
        (c / "loop.WAV").write_bytes(b"L" * 70_000)
        (c / ".DS_Store").write_bytes(b"junk")
        (c / "empty dir").mkdir()
        (c / "link.wav").symlink_to(c / "loop.WAV")

    def test_a_new_card_folder_is_empty_in_the_firmware_layout(self):
        self.store()
        self.assertEqual(sorted(str(p.relative_to(self.card)) for p in self.card.rglob("*")),
                         ["KORG", "KORG/hacktribe", "KORG/hacktribe/Sample", "KORG/hacktribe/System"])

    def test_korgs_own_folder_has_a_space_and_is_made_and_used_as_it_is(self):
        s = self.store()
        s.ensure_layout("electribe sampler")
        self.assertEqual(sorted(p.name for p in (self.card / "KORG").iterdir()), ["electribe sampler"])
        s.put_system("electribe sampler", b"update")
        self.assertEqual((self.card / "KORG" / "electribe sampler" / "System" / "SYSTEM.VSB").read_bytes(), b"update")
        for bad in ("../evil", "a/b", " lead", "two  spaces", "x" * 33, ""):
            s.ensure_layout(bad)
        self.assertFalse((self.card.parent / "evil").exists())
        self.assertEqual(sorted(p.name for p in (self.card / "KORG").iterdir()), ["electribe sampler", "hacktribe"], "a bad name falls back to the default, nothing outside KORG/")

    def test_an_update_file_that_is_already_there_is_kept_next_to_the_folder_not_overwritten(self):
        s = self.store()
        s.put_system("hacktribe", b"mine")
        s.put_system("hacktribe", b"mine")
        folder = self.card / "KORG" / "hacktribe"
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["Sample", "System"], "the same file again leaves nothing behind")
        s.put_system("hacktribe", b"second")
        self.assertEqual((folder / "System" / "SYSTEM.VSB").read_bytes(), b"second")
        self.assertEqual((folder / "SYSTEM-vorher.VSB").read_bytes(), b"mine")
        s.put_system("hacktribe", b"third")
        self.assertEqual((folder / "SYSTEM-vorher.VSB").read_bytes(), b"mine", "an earlier copy is never replaced")
        self.assertEqual((folder / "SYSTEM-vorher-2.VSB").read_bytes(), b"second")
        self.assertEqual(sorted(p.name for p in (folder / "System").iterdir()), ["SYSTEM.VSB"], "nothing but the one file in System/")

    def test_the_layout_made_for_another_firmware_goes_when_it_is_empty_and_stays_when_it_is_not(self):
        s = self.store()
        s.ensure_layout("blechtribe")
        self.assertEqual(sorted(p.name for p in (self.card / "KORG").iterdir()), ["blechtribe"])
        (self.card / "KORG" / "blechtribe" / "Sample" / "e2sSample.all").write_bytes(b"mine")
        s.ensure_layout("hacktribe")
        self.assertEqual(sorted(p.name for p in (self.card / "KORG").iterdir()), ["blechtribe", "hacktribe"])
        self.assertEqual((self.card / "KORG" / "blechtribe" / "Sample" / "e2sSample.all").read_bytes(), b"mine")
        s.ensure_layout("../evil")
        self.assertFalse((self.card.parent / "evil").exists())

    def test_the_firmware_names_the_folder(self):
        data = bytearray(0x200100)
        for folder in ("hacktribe", "blechtribe", "electribe", "electribe sampler"):
            path, name = b"KORG/electribe/\x00\x00\x00\x00\x00\x00\x00\x00\x00KORG/" + folder.encode() + b"/\x00", b"e2sSample.all\x00"
            data[0xA5760:0xA5760 + len(path)] = path
            data[0xA57C4:0xA57C4 + len(name)] = name
            self.assertEqual(card_folder(data), folder)
        self.assertEqual(card_folder(bytes(100)), "hacktribe", "no sample file name: the default")

    def test_the_blue_firmware_names_its_folder_through_its_pool_word(self):
        from unittest.mock import patch
        payload = bytearray(0x200000)
        payload[0x904D4:0x904D4 + 16] = b"KORG/electribe/\0"
        payload[0x904E4:0x904E4 + 17] = b"KORG/blechtribe/\0"
        with patch.object(cardstore, "is_synth", return_value=True):
            payload[0x325B4:0x325B8] = (0xC00904D4).to_bytes(4, "little")
            for raw in (payload, bytes(0x100) + payload):
                self.assertEqual(card_folder(raw), "electribe")
            payload[0x325B4:0x325B8] = (0xC00904E4).to_bytes(4, "little")
            self.assertEqual(card_folder(payload), "blechtribe", "with BLECH the word points at the rewritten window")
            payload[0x904E4] = 0
            with self.assertRaises(CardError):
                card_folder(payload)

    def test_the_blue_update_directory_rejects_other_vsb_files(self):
        s = self.store()
        s.put_system("electribe", b"checked")
        system = self.card / "KORG" / "electribe" / "System"
        self.assertEqual([p.name for p in system.iterdir()], ["SYSTEM.VSB"])
        other = system / "BOOT.VSB"
        other.write_bytes(b"keep")
        with self.assertRaises(CardError):
            s.put_system("electribe", b"new")
        self.assertEqual(other.read_bytes(), b"keep")
        self.assertEqual((system / "SYSTEM.VSB").read_bytes(), b"checked")

    def test_inserting_copies_the_folder_in_and_protects_it(self):
        self.make_folder()
        s = self.store()
        report = s.insert()
        self.assertEqual((report["files"], report["bytes"], report["renamed"]), (3, 75_300, 1))
        self.assertEqual([x["why"] for x in report["skipped"]], ["Verknüpfung, wird nicht verfolgt"])
        with s.image.lock:
            v = Volume(s.image.data)
            self.assertEqual(v.read("/drums/kick.wav"), b"K" * 5000)
            self.assertEqual(v.read("/drums/808/Sub Bass_ low_.wav"), b"S" * 300)
            self.assertIn("empty dir", [e.name for e in v.listdir("/")])
            self.assertEqual(v.check(), [])
            v.close()
        self.assertEqual(s.image.sectors, 1024 * 2048)
        self.assertFalse(os.access(self.card, os.W_OK))
        self.assertFalse(os.access(self.card / "drums" / "kick.wav", os.W_OK))
        s.eject()
        self.assertTrue(os.access(self.card, os.W_OK))
        self.assertTrue(os.access(self.card / "drums" / "kick.wav", os.W_OK))
        self.assertEqual(sorted(p.name for p in self.card.iterdir() if p.name != "KORG"),
                         [".DS_Store", "drums", "empty dir", "link.wav", "loop.WAV"], "nothing was lost, also what was not copied")

    def test_what_the_firmware_writes_is_mirrored_and_the_rest_is_left_alone(self):
        self.make_folder()
        s = self.store(flusher=False)
        s.insert()
        self.firmware_writes(s, "/KORG/hacktribe/Sample/e2sSample.all", b"new samples")
        self.firmware_writes(s, "/drums/kick.wav", b"changed")
        self.firmware_writes(s, "/loop.WAV", None, delete=True)
        self.assertTrue(s.flush())
        self.assertIsNone(s.sync_error)
        self.assertEqual((self.card / "KORG" / "hacktribe" / "Sample" / "e2sSample.all").read_bytes(), b"new samples")
        self.assertEqual((self.card / "drums" / "kick.wav").read_bytes(), b"changed")
        self.assertFalse((self.card / "loop.WAV").exists())
        self.assertTrue((self.card / ".DS_Store").exists(), "a file the card never held is not deleted")
        self.assertTrue((self.card / "link.wav").is_symlink())
        self.assertFalse(os.access(self.card / "drums" / "kick.wav", os.W_OK), "protected again after the mirror")
        self.assertFalse(os.access(self.card, os.W_OK))
        self.assertFalse(s.flush(), "nothing changed, nothing mirrored")

    def test_a_name_that_fat_changed_is_written_back_under_the_name_it_had(self):
        self.make_folder()
        s = self.store(flusher=False)
        s.insert()
        self.firmware_writes(s, "/drums/808/Sub Bass_ low_.wav", b"changed bass")
        s.flush()
        self.assertEqual((self.card / "drums" / "808" / "Sub Bass: low?.wav").read_bytes(), b"changed bass")
        self.assertFalse((self.card / "drums" / "808" / "Sub Bass_ low_.wav").exists())

    def test_taking_the_card_out_mirrors_what_was_not_mirrored_yet(self):
        s = self.store(flusher=False)
        s.insert()
        self.firmware_writes(s, "/a.bin", b"x" * 10_000)
        s.eject()
        self.assertEqual((self.card / "a.bin").read_bytes(), b"x" * 10_000)
        self.assertFalse(s.inserted)

    def test_closing_the_store_takes_the_card_out(self):
        s = self.store(flusher=False)
        s.insert()
        self.firmware_writes(s, "/a.bin", b"closed")
        s.close()
        self.stores.remove(s)
        self.assertEqual((self.card / "a.bin").read_bytes(), b"closed")
        self.assertTrue(os.access(self.card, os.W_OK))

    def test_the_flusher_mirrors_once_the_card_is_quiet(self):
        old, cardstore.IDLE_S = cardstore.IDLE_S, 0.2
        try:
            s = self.store()
            s.insert()
            self.firmware_writes(s, "/a.bin", b"z" * 3000)
            deadline = time.monotonic() + 5
            while not (self.card / "a.bin").exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertEqual((self.card / "a.bin").read_bytes(), b"z" * 3000)
        finally:
            cardstore.IDLE_S = old

    def test_a_card_the_firmware_formatted_to_fat16_is_read_and_emptied_into_the_folder(self):
        self.make_folder()
        s = self.store(flusher=False)
        s.insert()
        with s.image.lock:
            s.image.data[:] = fat16_image(len(s.image.data), {"NEW.TXT": b"after format"})
        s.image.touch()
        s.flush()
        self.assertIsNone(s.sync_error)
        self.assertEqual((self.card / "NEW.TXT").read_bytes(), b"after format")
        self.assertFalse((self.card / "drums").exists(), "formatting removed what the card held")
        self.assertTrue((self.card / ".DS_Store").exists())

    def test_a_card_that_reads_as_nonsense_is_reported_and_does_not_break_the_service(self):
        s = self.store(flusher=False)
        s.insert()
        with s.image.lock:
            s.image.data[:] = bytes(len(s.image.data))
        s.image.touch()
        s.flush()
        self.assertIn("Dateisystem", s.sync_error)
        self.assertTrue(s.inserted)

    def test_a_folder_too_big_for_the_card_is_refused(self):
        with open(self.store().dir / "big.bin", "wb") as f:
            f.truncate(1100 * MIB)
        with self.assertRaises(CardError) as e:
            self.stores[0].insert()
        self.assertIn("größer als die Karte", str(e.exception))
        self.assertFalse(self.stores[0].inserted)
        self.assertTrue(os.access(self.card, os.W_OK))

    def test_a_folder_left_protected_by_a_dead_service_is_given_back(self):
        s = self.store(flusher=False)
        s.insert()
        s._lockfile.close()                            # as if the process were gone, without an eject
        self.stores.remove(s)
        s2 = self.store(flusher=False)
        self.assertFalse(s2.inserted)
        self.assertTrue(os.access(self.card, os.W_OK))

    def test_open_hands_the_folder_to_the_file_manager(self):
        s = self.store()
        self.assertEqual(s.open_folder(), str(self.card))
        self.assertEqual(self.opened, [self.card])

    def test_two_services_cannot_share_a_card_folder(self):
        try:
            import fcntl  # noqa: F401
        except ImportError:
            self.skipTest("no flock on this platform")
        self.store()
        with self.assertRaises(CardError) as e:
            CardStore(self.root)
        self.assertIn("anderen Emulator-Dienst", str(e.exception))


def fat16_image(size, files):
    """A bare FAT16 volume with `files` (8.3 names) in its root directory, the way a plain formatter leaves one."""
    img = bytearray(size)
    total, rsv, root_entries = size // 512, 1, 512
    spc = next(n for n in (4, 8, 16, 32, 64) if total // n < 65000)
    clusters = (total - rsv - root_entries * 32 // 512) // spc
    fatsz = -(-((clusters + 2) * 2) // 512)
    clusters = (total - rsv - 2 * fatsz - root_entries * 32 // 512) // spc
    boot = bytearray(512)
    boot[0:3], boot[3:11] = b"\xEB\x3C\x90", b"MSDOS5.0"
    boot[11:13], boot[13], boot[14:16], boot[16] = (512).to_bytes(2, "little"), spc, rsv.to_bytes(2, "little"), 2
    boot[17:19], boot[21] = root_entries.to_bytes(2, "little"), 0xF8
    boot[19:21] = (total if total < 65536 else 0).to_bytes(2, "little")
    boot[22:24] = fatsz.to_bytes(2, "little")
    boot[32:36] = (0 if total < 65536 else total).to_bytes(4, "little")
    boot[43:54], boot[54:62] = b"AFTER FMT  ", b"FAT16   "
    boot[510:512] = b"\x55\xaa"
    img[0:512] = boot
    fat = bytearray(fatsz * 512)
    fat[0:4] = b"\xF8\xFF\xFF\xFF"
    root = rsv + 2 * fatsz
    data = (root + root_entries * 32 // 512) * 512
    cluster = 2
    for i, (name, content) in enumerate(files.items()):
        stem, ext = name.split(".")
        need = max(1, -(-len(content) // (spc * 512)))
        entry = bytearray(32)
        entry[0:11] = stem.ljust(8).encode() + ext.ljust(3).encode()
        entry[11] = 0x20
        entry[26:28], entry[28:32] = cluster.to_bytes(2, "little"), len(content).to_bytes(4, "little")
        img[root * 512 + i * 32:root * 512 + (i + 1) * 32] = entry
        for k in range(need):
            fat[(cluster + k) * 2:(cluster + k) * 2 + 2] = ((cluster + k + 1) if k + 1 < need else 0xFFFF).to_bytes(2, "little")
        at = data + (cluster - 2) * spc * 512
        img[at:at + len(content)] = content
        cluster += need
    for k in range(2):
        img[(rsv + k * fatsz) * 512:(rsv + (k + 1) * fatsz) * 512] = fat
    return img


class Fat16Test(unittest.TestCase):
    def test_a_fat16_volume_reads_and_never_writes(self):
        img = fat16_image(64 * MIB, {"A.TXT": b"hello", "BIG.BIN": os.urandom(9000)})
        v = fat32.open_volume(img)
        self.assertIsInstance(v, fat32.Fat16Volume)
        self.assertEqual([p for p, _ in v.walk()], ["/A.TXT", "/BIG.BIN"])
        self.assertEqual(v.read("/A.TXT"), b"hello")
        self.assertEqual(len(v.read("/BIG.BIN")), 9000)
        with self.assertRaises(fat32.FatError):
            v.write("/c.txt", b"x")
        v.close()

    def test_fat32_images_still_open_as_fat32(self):
        v = fat32.open_volume(fat32.format_image(64 * MIB))
        self.assertIsInstance(v, Volume)
        self.assertNotIsInstance(v, fat32.Fat16Volume)
        v.close()

    def test_something_that_is_neither_is_the_fat32_complaint(self):
        with self.assertRaises(fat32.FatError) as e:
            fat32.open_volume(bytearray(64 * MIB))
        self.assertIn("0xAA55", str(e.exception))


if __name__ == "__main__":
    unittest.main()
