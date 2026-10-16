# SPDX-License-Identifier: GPL-2.0-only
"""The factory sample bank of the emulator's empty flash: its layout, that it is ours, and that the empty flash carries it."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import factorybank  # noqa: E402
from machine import USER_MARK, blank_flash  # noqa: E402


class FactoryBankTest(unittest.TestCase):
    def setUp(self):
        self.bank = factorybank.build()

    def test_the_header_names_seven_sections_that_start_with_their_tags(self):
        self.assertEqual(self.bank[:12], b"KORGelec2PCM")
        offsets = struct.unpack_from("<7I", self.bank, 0x10)
        self.assertEqual(offsets, (factorybank.DRMP, factorybank.DRUM, factorybank.MSPR, factorybank.MSRL, factorybank.SMPR, factorybank.SMPL, factorybank.MSVS))
        for tag, at in zip([b"DRMP", b"DRUM", b"MSPR", b"MSRL", b"SMPR", b"SMPL", b"MSVS"], offsets):
            self.assertEqual(self.bank[at:at + 4], tag)

    def test_the_sections_hold_411_entries_and_say_how_long_they_are(self):
        for tag, size in [(b"MSPR", 16), (b"MSRL", 8), (b"MSVS", 32), (b"SMPR", 16)]:
            at = self.bank.index(tag, 0x40)
            length, count = struct.unpack_from("<II", self.bank, at + 4)
            self.assertEqual(count, 411, tag)
            self.assertEqual(length, 0x20 + 411 * size, tag)

    def test_the_entries_are_ours_and_count_up(self):
        names = self.bank[factorybank.MSPR + 0x20:factorybank.MSPR + 0x20 + 411 * 16]
        for i in range(411):
            record = names[i * 16:(i + 1) * 16]
            self.assertEqual(record[:8], b"Fac%03d  " % (i + 1))
            self.assertEqual(struct.unpack_from("<I", record, 8)[0], i)
        ends = [struct.unpack_from("<I", self.bank, factorybank.SMPR + 0x20 + i * 16)[0] for i in range(411)]
        self.assertEqual(ends, sorted(ends))

    def test_there_is_no_audio_and_the_tables_end_where_the_audio_would_begin(self):
        self.assertEqual(len(self.bank), factorybank.END)
        self.assertEqual(self.bank[factorybank.SMPL + 0x20:], b"\xff" * (factorybank.END - factorybank.SMPL - 0x20))

    def test_the_empty_flash_has_the_bank_and_keeps_its_user_mark(self):
        mem = blank_flash()
        self.assertEqual(bytes(mem[factorybank.BASE:factorybank.BASE + len(self.bank)]), self.bank)
        self.assertEqual(bytes(mem[USER_MARK:USER_MARK + 12]), b"KORGele2sUSR")
        self.assertEqual(bytes(mem[factorybank.BASE + factorybank.END:factorybank.BASE + factorybank.END + 64]), b"\xff" * 64)


if __name__ == "__main__":
    unittest.main()
