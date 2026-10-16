# SPDX-License-Identifier: GPL-2.0-only
"""The card and the MMC controller, driven through the registers the way the firmware does it."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdcard  # noqa: E402
from sdcard import ARG, BLEN, CMD, DRR, DXR, IM, NBLK, RSP01, RSP67, ST0  # noqa: E402

MIB = 1024 * 1024


def blocks(n, seed=0):
    return b"".join(bytes([(i + seed) & 0xFF]) * 512 for i in range(n))


class Driver:
    """Sends commands to a controller like the firmware: argument, then command word, then status."""

    def __init__(self, ctl):
        self.ctl = ctl

    def cmd(self, idx, arg=0, fmt=1, busy=0, extra=0):
        self.ctl.write(ARG, arg, 4)
        self.ctl.write(CMD, idx | (fmt << 9) | (busy << 8) | extra, 4)
        return self.ctl.read(ST0, 4)

    def response(self):
        return [self.ctl.read(o, 4) for o in range(RSP01, RSP67 + 4, 4)]

    def r2(self):
        """The 16 bytes of a 136-bit response, bit 127 first: RSP7 holds the top and RSP0 the bottom 16 bits."""
        halves = [x for w in self.response() for x in (w & 0xFFFF, w >> 16)]
        return b"".join(struct.pack(">H", h) for h in reversed(halves))

    def init(self):
        self.cmd(0, fmt=0)
        assert self.cmd(8, 0x1AA) & 4
        assert self.response()[3] & 0xFFF == 0x1AA
        for _ in range(2):
            self.cmd(55)
            self.cmd(41, 0x40000000)
        ocr = self.response()[3]
        self.cmd(2, fmt=2)
        self.cmd(3)
        rca = self.response()[3] >> 16
        self.cmd(9, rca << 16, fmt=2)
        csd = self.r2()
        self.cmd(7, rca << 16, busy=1)
        self.cmd(16, 512)
        return ocr, rca, csd

    def read_block(self, buf):
        out = bytearray()
        while len(out) < 512:
            out += self.ctl.read(DRR, 4).to_bytes(4, "little")
        return bytes(out)


class CardTest(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(128 * MIB)
        for i in range(0, 64):
            self.data[i * 512:(i + 1) * 512] = bytes([i]) * 512
        self.medium = sdcard.MemoryMedium(self.data)
        self.card = sdcard.SDCard(self.medium)
        self.ctl = sdcard.MMCController(self.card)
        self.d = Driver(self.ctl)

    def test_without_a_card_a_command_with_no_answer_completes_and_the_rest_time_out(self):
        ctl = sdcard.MMCController()
        d = Driver(ctl)
        self.assertEqual(d.cmd(0, fmt=0), sdcard.ST0_RSPDNE)
        self.assertEqual(d.cmd(8, 0x1AA), sdcard.ST0_TOUTRS)
        self.assertFalse(ctl.irq())
        ctl.write(IM, 0x600, 4)
        self.assertFalse(ctl.irq(), "no card, no interrupts")

    def test_the_init_sequence_the_firmware_uses_ends_with_a_ready_sdhc_card(self):
        ocr, rca, csd = self.d.init()
        self.assertTrue(ocr & 0x80000000, "power-up done")
        self.assertTrue(ocr & 0x40000000, "high capacity")
        self.assertEqual(rca, 0x1234)
        self.assertEqual(self.card.state, "tran")
        self.assertEqual(csd[0] >> 6, 1, "CSD version 2.0")
        c_size = (csd[7] & 0x3F) << 16 | csd[8] << 8 | csd[9]
        self.assertEqual((c_size + 1) * 512 * 1024, 128 * MIB)
        self.assertEqual(csd, self.card.csd(), "the register image is the CSD, byte for byte, CRC included")

    def test_unknown_commands_are_not_answered(self):
        self.d.init()
        for idx in (5, 13, 17 + 40, 51):
            self.assertEqual(self.d.cmd(idx) & sdcard.ST0_RSPDNE, 0, idx)

    def test_a_multiple_block_read_delivers_each_block_and_then_reports_done(self):
        self.d.init()
        self.ctl.write(BLEN, 512, 4)
        self.ctl.write(NBLK, 3, 4)
        st = self.d.cmd(18, 10, extra=0x12000)
        self.assertTrue(st & sdcard.ST0_RSPDNE)
        for lba in (10, 11, 12):
            self.assertEqual(self.d.read_block(None), self.data[lba * 512:(lba + 1) * 512])
        self.assertTrue(self.ctl.read(ST0, 4) & sdcard.ST0_DATDNE)
        self.d.cmd(12, busy=1)
        self.assertEqual(self.card.sectors_read, 3)

    def test_the_interrupt_line_follows_the_unmasked_data_ready_bit(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.ctl.write(IM, 0, 4)
        self.d.cmd(18, 0, extra=0x12000)
        self.assertFalse(self.ctl.irq(), "masked")
        self.ctl.write(IM, 0x600, 4)
        self.assertTrue(self.ctl.irq())
        self.d.read_block(None)
        self.ctl.read(ST0, 4)
        self.assertFalse(self.ctl.irq(), "block taken")

    def test_a_write_reaches_the_image_one_block_at_a_time(self):
        self.d.init()
        self.ctl.write(BLEN, 512, 4)
        self.ctl.write(NBLK, 2, 4)
        self.d.cmd(25, 100, extra=0x12000)
        self.assertTrue(self.ctl.read(ST0, 4) & sdcard.ST0_DXRDY)
        payload = blocks(2, 7)
        for i in range(0, 512, 4):
            self.ctl.write(DXR, int.from_bytes(payload[i:i + 4], "little"), 4)
        self.assertEqual(self.data[100 * 512:101 * 512], payload[:512], "first block is on the card before the second arrives")
        self.assertEqual(self.data[101 * 512:102 * 512], bytes(512))
        for i in range(512, 1024, 4):
            self.ctl.write(DXR, int.from_bytes(payload[i:i + 4], "little"), 4)
        self.assertEqual(self.data[100 * 512:102 * 512], payload)
        self.assertTrue(self.ctl.read(ST0, 4) & sdcard.ST0_DATDNE)
        self.d.cmd(12, busy=1)
        self.assertEqual((self.card.sectors_written, self.ctl.tx_lba), (2, None))

    def test_a_read_only_medium_swallows_writes(self):
        medium = sdcard.MemoryMedium(self.data, read_only=True)
        ctl = sdcard.MMCController(sdcard.SDCard(medium))
        d = Driver(ctl)
        d.init()
        ctl.write(NBLK, 1, 4)
        d.cmd(24, 5, extra=0x12000)
        for i in range(0, 512, 4):
            ctl.write(DXR, 0xFFFFFFFF, 4)
        self.assertEqual(self.data[5 * 512:6 * 512], bytes([5]) * 512)

    def test_an_address_past_the_end_goes_unanswered(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        st = self.d.cmd(17, self.medium.sectors)
        self.assertEqual(st & sdcard.ST0_RSPDNE, 0)
        self.assertTrue(st & sdcard.ST0_TOUTRS)

    def test_stop_drops_a_transfer_that_is_still_running(self):
        self.d.init()
        self.ctl.write(NBLK, 8, 4)
        self.d.cmd(18, 0, extra=0x12000)
        self.ctl.read(DRR, 4)
        self.d.cmd(12, busy=1)
        self.assertEqual((len(self.ctl.rx), self.ctl.blocks_left), (0, 0))
        self.assertEqual(self.ctl.read(DRR, 4), 0)

    def test_reading_a_block_past_the_last_one_in_a_multiple_read_gives_zeros_not_a_hang(self):
        self.d.init()
        last = self.medium.sectors - 1
        self.ctl.write(NBLK, 2, 4)
        self.d.cmd(18, last, extra=0x12000)
        self.d.read_block(None)
        self.assertEqual(self.d.read_block(None), bytes(512))


if __name__ == "__main__":
    unittest.main()
