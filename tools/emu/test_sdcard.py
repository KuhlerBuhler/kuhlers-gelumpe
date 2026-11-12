# SPDX-License-Identifier: GPL-2.0-only
"""The card and the MMC controller, driven through the registers the way the firmware does it."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdcard  # noqa: E402
from sdcard import ARG, BLEN, CMD, DRR, DXR, IM, NBLK, RSP01, RSP67, ST0  # noqa: E402
from sdcard import ST0_CRCRD, ST0_CRCRS, ST0_CRCWR, ST0_DATDNE, ST0_RSPDNE, ST0_TOUTRD, ST0_TOUTRS  # noqa: E402

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

    def write_block(self, block):
        for i in range(0, len(block), 4):
            self.ctl.write(DXR, int.from_bytes(block[i:i + 4], "little"), 4)

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

    def test_a_read_chunk_raises_the_interrupt_once(self):
        """Raised again while the firmware still takes a chunk, the interrupt can come after the stop command, and the
        handler's MMCST0 read takes that command's answer (assertion AM180xMMSDCardController.cpp line 228)."""
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.ctl.write(IM, 0x600, 4)
        self.d.cmd(18, 0, extra=0x12000)
        for chunk in range(8):
            self.assertTrue(self.ctl.irq(), f"chunk {chunk} ready")
            self.ctl.raised()
            self.assertFalse(self.ctl.irq(), f"chunk {chunk} has had its interrupt")
            for _ in range(16):
                self.ctl.read(DRR, 4)
        self.assertTrue(self.ctl.read(ST0, 4) & sdcard.ST0_DATDNE)
        self.ctl.write(ARG, 0, 4)
        self.ctl.write(CMD, 12 | (1 << 9) | (1 << 8), 4)
        self.assertFalse(self.ctl.irq(), "nothing left to raise it after the stop")
        self.assertTrue(self.ctl.read(ST0, 4) & sdcard.ST0_RSPDNE, "the stop's answer is still there")

    def test_room_for_a_write_chunk_raises_the_interrupt_once(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.ctl.write(IM, 0x600, 4)
        self.d.cmd(25, 100, extra=0x12000)
        for chunk in range(8):
            self.assertTrue(self.ctl.irq(), f"room for chunk {chunk}")
            self.ctl.raised()
            self.assertFalse(self.ctl.irq())
            for _ in range(16):
                self.ctl.write(DXR, chunk, 4)
        self.assertFalse(self.ctl.irq(), "block written, no more room asked for")
        self.assertEqual(self.card.sectors_written, 1)

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


READ = 0x12000          # the DMATRIG and data bits of a read or write command word, as the firmware sends them


class Sdsc(unittest.TestCase):
    """An old standard-capacity card: no CMD8 answer, no high-capacity bit, a version 1.0 CSD, byte addresses."""

    def setUp(self):
        self.data = bytearray(64 * MIB)
        for i in range(0, 64):
            self.data[i * 512:(i + 1) * 512] = bytes([i]) * 512
        self.card = sdcard.SDCard(sdcard.MemoryMedium(self.data), kind="sdsc")
        self.ctl = sdcard.MMCController(self.card)
        self.d = Driver(self.ctl)

    def init(self):
        self.assertTrue(self.d.cmd(8, 0x1AA) & ST0_TOUTRS, "a version 1.x card does not know CMD8")
        self.d.cmd(0, fmt=0)
        for _ in range(2):
            self.d.cmd(55)
            self.d.cmd(41, 0x40000000)
        ocr = self.d.response()[3]
        self.d.cmd(2, fmt=2)
        self.d.cmd(3)
        rca = self.d.response()[3] >> 16
        self.d.cmd(9, rca << 16, fmt=2)
        csd = self.d.r2()
        self.d.cmd(7, rca << 16, busy=1)
        self.d.cmd(16, 512)
        return ocr, csd

    def test_the_answers_to_the_init_describe_a_card_without_the_high_capacity_bit(self):
        ocr, csd = self.init()
        self.assertTrue(ocr & 0x80000000, "power-up done")
        self.assertFalse(ocr & 0x40000000, "CCS clear: byte addresses")
        self.assertEqual(csd[0] >> 6, 0, "CSD version 1.0")
        self.assertEqual(csd, self.card.csd(), "CRC included")
        bits = int.from_bytes(csd, "big")
        read_bl_len, c_size, mult = (bits >> 80) & 0xF, (bits >> 62) & 0xFFF, (bits >> 47) & 7
        self.assertEqual((c_size + 1) * 2 ** (mult + 2) * 2 ** read_bl_len, 64 * MIB)

    def test_the_capacity_in_the_csd_is_right_up_to_two_gib(self):
        class Big:
            def __init__(self, sectors):
                self.sectors = sectors
        for size in (8 * MIB, 64 * MIB, 1024 * MIB, 2048 * MIB):
            csd = sdcard.SDCard(Big(size // 512), kind="sdsc").csd()
            bits = int.from_bytes(csd, "big")
            read_bl_len, c_size, mult = (bits >> 80) & 0xF, (bits >> 62) & 0xFFF, (bits >> 47) & 7
            self.assertEqual((c_size + 1) * 2 ** (mult + 2) * 2 ** read_bl_len, size, size)
        with self.assertRaises(ValueError):
            sdcard.SDCard(Big(4096 * MIB // 512), kind="sdsc")

    def test_a_read_takes_the_byte_address(self):
        self.init()
        self.ctl.write(NBLK, 1, 4)
        self.assertTrue(self.d.cmd(18, 5 * 512, extra=READ) & ST0_RSPDNE)
        self.assertEqual(self.d.read_block(None), bytes([5]) * 512, "block 5, not block 2560")
        self.d.cmd(12, busy=1)

    def test_a_write_takes_the_byte_address(self):
        self.init()
        self.ctl.write(NBLK, 1, 4)
        self.d.cmd(25, 7 * 512, extra=READ)
        self.d.write_block(bytes([0xAB]) * 512)
        self.assertEqual(self.data[7 * 512:8 * 512], bytes([0xAB]) * 512)

    def test_an_address_that_is_no_whole_block_moves_no_data_and_reports_the_address_error(self):
        self.init()
        self.ctl.write(NBLK, 1, 4)
        st = self.d.cmd(18, 5 * 512 + 4, extra=READ)
        self.assertTrue(st & ST0_RSPDNE and st & ST0_TOUTRD)
        self.assertTrue(self.d.response()[3] & sdcard.R1_ADDRESS_ERROR)
        self.d.cmd(25, 9 * 512 + 1, extra=READ)
        self.d.write_block(bytes([0xCD]) * 512)
        self.assertEqual(self.data[9 * 512:10 * 512], bytes([9]) * 512, "the data is dropped")


class Crc(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(64 * MIB)
        for i in range(0, 64):
            self.data[i * 512:(i + 1) * 512] = bytes([i]) * 512
        self.card = sdcard.SDCard(sdcard.MemoryMedium(self.data))
        self.ctl = sdcard.MMCController(self.card)
        self.d = Driver(self.ctl)

    def test_the_two_checksums_are_the_standard_ones(self):
        self.assertEqual(sdcard.crc16(b"123456789"), 0x31C3)
        self.assertEqual(sdcard.crc7(bytes.fromhex("4000000000")), 0x95 >> 1, "CMD0, the frame every card driver knows")
        self.assertEqual(sdcard.crc7(bytes.fromhex("48000001aa")), 0x87 >> 1, "CMD8 with the check pattern")
        self.assertEqual(sdcard.frame(16, 0)[-1], (sdcard.crc7(bytes([16, 0, 0, 0, 0])) << 1) | 1)

    def test_an_answer_with_a_bad_crc_is_flagged_and_not_taken_for_done(self):
        self.d.init()
        self.assertTrue(self.d.cmd(16, 512) & ST0_RSPDNE)
        fault = self.card.fail("response_crc", cmds=[16])
        st = self.d.cmd(16, 512)
        self.assertEqual((st & ST0_RSPDNE, bool(st & ST0_CRCRS), fault.hits), (0, True, 1))

    def test_the_answer_to_acmd41_has_no_crc_to_fail(self):
        self.card.fail("response_crc", cmds=[41])
        self.d.cmd(55)
        st = self.d.cmd(41, 0x40000000, fmt=3)
        self.assertEqual((bool(st & ST0_RSPDNE), st & ST0_CRCRS), (True, 0))

    def test_a_cid_or_csd_with_a_bad_crc_is_flagged(self):
        self.card.fail("response_crc", cmds=[9])
        self.assertTrue(self.d.cmd(9, 0x12340000, fmt=2) & ST0_CRCRS)
        self.assertTrue(self.d.cmd(10, 0x12340000, fmt=2) & ST0_RSPDNE)

    def test_a_block_with_a_bad_crc_arrives_damaged_and_is_flagged_at_its_end(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.card.fail("read_crc", lbas=[3])
        self.d.cmd(18, 3, extra=READ)
        got = self.d.read_block(None)
        self.assertNotEqual(got, self.data[3 * 512:4 * 512], "what the wire carried is what the firmware gets")
        self.assertEqual(sum(a != b for a, b in zip(got, self.data[3 * 512:4 * 512])), 1)
        st = self.ctl.read(ST0, 4)
        self.assertTrue(st & ST0_CRCRD and st & ST0_DATDNE)
        self.assertEqual(self.data[3 * 512:4 * 512], bytes([3]) * 512, "the card itself is fine")

    def test_a_good_block_has_no_crc_flag(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.d.cmd(18, 3, extra=READ)
        self.d.read_block(None)
        self.assertEqual(self.ctl.read(ST0, 4) & ST0_CRCRD, 0)

    def test_only_the_blocks_a_fault_names_are_hit_and_it_can_skip_and_end(self):
        self.d.init()
        self.card.fail("read_crc", lbas=range(10, 20), skip=1, count=2)
        flags = []
        for lba in (2, 10, 11, 12, 13):
            self.ctl.write(NBLK, 1, 4)
            self.d.cmd(18, lba, extra=READ)
            self.d.read_block(None)
            flags.append(bool(self.ctl.read(ST0, 4) & ST0_CRCRD))
            self.d.cmd(12, busy=1)
        self.assertEqual(flags, [False, False, True, True, False])

    def test_a_write_with_a_bad_crc_is_refused_flagged_and_the_next_status_says_so(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.card.fail("write_crc")
        self.d.cmd(25, 20, extra=READ)
        self.d.write_block(bytes([0xEE]) * 512)
        self.assertTrue(self.ctl.read(ST0, 4) & ST0_CRCWR)
        self.assertEqual(self.data[20 * 512:21 * 512], bytes([20]) * 512, "not stored")
        self.assertEqual(self.card.sectors_written, 0)
        self.d.cmd(12, busy=1)
        self.assertTrue(self.d.response()[3] & (sdcard.R1_COM_CRC_ERROR))
        self.d.cmd(16, 512)
        self.assertFalse(self.d.response()[3] & (sdcard.R1_COM_CRC_ERROR >> 16), "the bit is gone after one answer")

    def test_a_write_the_card_cannot_program_is_refused_the_same_way(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.card.fail("write_error")
        self.d.cmd(24, 21, extra=READ)
        self.d.write_block(bytes([0xEF]) * 512)
        self.assertTrue(self.ctl.read(ST0, 4) & ST0_CRCWR)
        self.assertEqual(self.data[21 * 512:22 * 512], bytes([21]) * 512)
        self.d.cmd(12, busy=1)
        self.assertTrue(self.d.response()[3] & (sdcard.R1_ERROR))


class Faults(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(64 * MIB)
        for i in range(0, 64):
            self.data[i * 512:(i + 1) * 512] = bytes([i]) * 512
        self.card = sdcard.SDCard(sdcard.MemoryMedium(self.data))
        self.ctl = sdcard.MMCController(self.card)
        self.d = Driver(self.ctl)

    def test_a_card_that_does_not_answer_leaves_no_command_done_but_cmd0(self):
        self.card.fail("no_response")
        self.assertEqual(self.d.cmd(0, fmt=0), ST0_RSPDNE, "CMD0 has nothing to wait for")
        self.assertEqual(self.d.cmd(8, 0x1AA), ST0_TOUTRS)
        self.assertEqual(self.card.state, "idle")

    def test_a_fault_names_the_commands_it_hits_and_heal_takes_it_away(self):
        self.d.init()
        self.card.fail("no_response", cmds=[17, 18])
        self.assertTrue(self.d.cmd(16, 512) & ST0_RSPDNE)
        self.ctl.write(NBLK, 1, 4)
        self.assertTrue(self.d.cmd(18, 3, extra=READ) & ST0_TOUTRS)
        self.card.heal()
        self.assertTrue(self.d.cmd(18, 3, extra=READ) & ST0_RSPDNE)

    def test_an_answer_fault_can_name_the_block_of_the_data_command_it_meets(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.card.fail("no_response", lbas=range(10, 20))
        self.assertTrue(self.d.cmd(16, 512) & ST0_RSPDNE, "no block, no hit")
        self.assertTrue(self.d.cmd(18, 3, extra=READ) & ST0_RSPDNE)
        self.assertTrue(self.d.cmd(18, 12, extra=READ) & ST0_TOUTRS)

    def test_a_read_that_times_out_answers_and_then_sends_nothing(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.card.fail("read_timeout", lbas=[4])
        st = self.d.cmd(18, 4, extra=READ)
        self.assertTrue(st & ST0_RSPDNE and st & ST0_TOUTRD)
        self.assertFalse(self.ctl.read(ST0, 4) & sdcard.ST0_DRRDY)
        self.assertEqual(self.ctl.blocks_left, 0)

    def test_a_read_error_does_the_same_and_the_next_answer_carries_the_ecc_bit(self):
        self.d.init()
        self.ctl.write(NBLK, 1, 4)
        self.card.fail("read_error", lbas=[4])
        self.assertTrue(self.d.cmd(18, 4, extra=READ) & ST0_TOUTRD)
        self.d.cmd(12, busy=1)
        self.assertTrue(self.d.response()[3] & (sdcard.R1_ECC_FAILED))

    def test_a_multiple_read_stops_at_the_block_that_fails(self):
        self.d.init()
        self.ctl.write(NBLK, 3, 4)
        self.card.fail("read_timeout", lbas=[11])
        self.d.cmd(18, 10, extra=READ)
        self.assertEqual(self.d.read_block(None), self.data[10 * 512:11 * 512])
        st = self.ctl.read(ST0, 4)
        self.assertTrue(st & ST0_TOUTRD and not st & ST0_DATDNE, "the transfer does not end, it breaks")

    def test_a_card_whose_power_up_never_ends_stays_busy(self):
        card = sdcard.SDCard(sdcard.MemoryMedium(self.data), never_ready=True)
        d = Driver(sdcard.MMCController(card))
        d.cmd(0, fmt=0)
        d.cmd(8, 0x1AA)
        for _ in range(5):
            d.cmd(55)
            d.cmd(41, 0x40000000)
            self.assertFalse(d.response()[3] & 0x80000000, "busy")
        self.assertEqual(card.state, "idle")

    def test_faults_are_checked_when_made(self):
        for bad in ({"kind": "nope"}, {"kind": "read_crc", "extra": 1}, {"kind": "read_crc", "lbas": "x"}, {"kind": "read_crc", "cmds": 3}):
            with self.assertRaises(ValueError, msg=bad):
                sdcard.Fault.parse(bad)
        with self.assertRaises(ValueError):
            sdcard.SDCard(sdcard.MemoryMedium(self.data), kind="mmc")

    def test_options_come_from_json_and_the_card_describes_itself_back(self):
        opts = sdcard.SDCard.options({"kind": "sdsc", "writeProtect": True, "faults": [
            {"kind": "read_crc", "lbas": {"from": 4, "to": 8}, "skip": 2, "count": 1}, {"kind": "no_response", "cmds": [24, 25]}]})
        card = sdcard.SDCard(sdcard.MemoryMedium(self.data), **opts)
        self.assertEqual(card.describe(), {"kind": "sdsc", "writeProtect": True, "neverReady": False, "faults": [
            {"kind": "read_crc", "cmds": None, "lbas": {"from": 4, "to": 8}, "skip": 2, "count": 1, "hits": 0},
            {"kind": "no_response", "cmds": [24, 25], "lbas": None, "skip": 0, "count": None, "hits": 0}]})
        for bad in ({"kind": "mmc"}, {"writeProtect": "yes"}, {"faults": "x"}, {"colour": 1}):
            with self.assertRaises(ValueError, msg=bad):
                sdcard.SDCard.options(bad)
        with self.assertRaises(ValueError):
            sdcard.SDCard.options({"kind": "sdsc"}, live=True)

    def test_a_card_with_faults_can_be_pickled_for_a_snapshot(self):
        import pickle
        card = sdcard.SDCard(sdcard.MemoryMedium(bytearray(MIB)), kind="sdsc", faults=[{"kind": "read_crc", "lbas": range(3)}])
        again = pickle.loads(pickle.dumps(card))
        self.assertEqual(again.describe(), card.describe())


class WriteProtect(unittest.TestCase):
    """The lock switch: the socket reports it on GPIO 4.0 and the firmware's disk status reads it (0xC0016DB8)."""

    def pin(self, card):
        import types
        import machine
        m = types.SimpleNamespace(regs={}, gpio={}, inputs={machine.pin(4, 1): 0}, mmc=sdcard.MMCController(card), handshake=0)
        return machine.Machine.gpio_read(m, 0x10 + 2 * 0x28 + 0x10) & 1

    def test_the_pin_follows_the_switch_of_the_card_in_the_slot(self):
        card = sdcard.SDCard(sdcard.MemoryMedium(bytearray(MIB)))
        self.assertEqual(self.pin(card), 0)
        card.write_protect = True
        self.assertEqual(self.pin(card), 1)
        self.assertEqual(self.pin(None), 0, "no card, no switch")


if __name__ == "__main__":
    unittest.main()
