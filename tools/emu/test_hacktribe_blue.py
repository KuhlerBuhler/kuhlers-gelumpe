"""The blue hardware for Sampler code (Hacktribe for the blue), with synthetic images only."""
import unittest

import bootmap
import hacktribe_blue_probe as probe
from firmware import HARDWARE_MARKS, SAMPLER_USER_MARK, USER_MARKS, hardware_of_head
from machine import USER_MARK, blank_flash, blank_flash_like, hardware_flash, hardware_of_flash


def vsb(head):
    """A VSB of zeros with the head bytes of the Sampler ("E2S") or of the blue ("E2")."""
    out = bytearray(0x200100)
    out[0x10:0x13] = b"E2S" if head == "sampler" else b"E2\0"
    out[0x2E] = 0x24 if head == "sampler" else 0x23
    return bytes(out)


class Hardware(unittest.TestCase):
    def test_the_blue_mark_is_the_synth_builds_mark(self):
        self.assertEqual(HARDWARE_MARKS, {"red": SAMPLER_USER_MARK, "blue": USER_MARKS["synth"]})

    def test_the_head_names_the_hardware(self):
        self.assertEqual(hardware_of_head(vsb("blue")), "blue")
        self.assertEqual(hardware_of_head(vsb("sampler")), "red")
        self.assertEqual(hardware_of_head(probe.with_head(vsb("sampler"), "blue")), "blue")

    def test_a_flash_belongs_to_the_hardware_of_its_mark(self):
        self.assertEqual(hardware_of_flash(hardware_flash("blue")), "blue")
        self.assertEqual(hardware_of_flash(blank_flash()), "red")
        self.assertIsNone(hardware_of_flash(b"\xff" * 0x1000000))
        self.assertIsNone(hardware_of_flash(None))

    def test_the_blue_flash_has_no_sample_bank(self):
        blue = hardware_flash("blue")
        self.assertEqual(bytes(blue[USER_MARK:USER_MARK + 12]), USER_MARKS["synth"])
        self.assertEqual(set(blue[0x800000:0x800000 + 0x10000]), {0xFF})
        self.assertNotEqual(set(blank_flash()[0x800000:0x800000 + 0x10000]), {0xFF})

    def test_a_blank_start_keeps_the_hardware_of_the_own_flash(self):
        blue = bytes(hardware_flash("blue"))
        self.assertEqual(bootmap.flash_for("blank", blue), blue)
        self.assertEqual(bootmap.flash_for("blank", bytes(blank_flash())), bytes(blank_flash()))
        self.assertIsNone(bootmap.flash_for("blank", None))
        self.assertIsNone(blank_flash_like(b"\xff" * 0x1000000))


class Paths(unittest.TestCase):
    def test_with_head_changes_only_the_two_bytes(self):
        red = vsb("sampler")
        blue = probe.with_head(red, "blue")
        self.assertEqual([i for i in range(len(red)) if red[i] != blue[i]], [0x12, 0x2E])
        self.assertEqual(probe.with_head(blue, "sampler"), red)
        self.assertEqual((probe.head_of(red), probe.head_of(blue)), ("sampler", "blue"))

    def test_each_running_firmware_takes_one_head(self):
        korg, hacktribe, blech = vsb("blue"), vsb("blue"), vsb("sampler")
        expect = {(running, probe.head_of(card)): written for _, running, card, written in probe.paths(korg, hacktribe, blech)
                  if running is not korg}
        self.assertEqual(expect, {(hacktribe, "sampler"): True, (hacktribe, "blue"): False,
                                  (blech, "sampler"): True, (blech, "blue"): False})
        firsts = [(probe.head_of(card), written) for _, running, card, written in probe.paths(korg, hacktribe, blech)[:2]]
        self.assertEqual(firsts, [("blue", True), ("sampler", False)])

    def test_a_refused_file_has_no_flash_command_and_a_written_one_restarts(self):
        done = {"erase_commands": {"count": 512}, "program_commands": {"count": 8192}, "firmware_area_is_the_new_file": True,
                "user_area_identical": True, "below_the_firmware_identical": True, "bank_identical": True, "asserts": [],
                "reboot": {"main_screen": True}}
        none = {**done, "erase_commands": {"count": 0}, "program_commands": {"count": 0}, "firmware_area_is_the_new_file": False}
        self.assertTrue(probe.verdict(done, True))
        self.assertFalse(probe.verdict(done, False))
        self.assertTrue(probe.verdict(none, False))
        self.assertFalse(probe.verdict(none, True))
        self.assertFalse(probe.verdict({**done, "reboot": {"main_screen": False}}, True))
        self.assertFalse(probe.verdict({**done, "user_area_identical": False}, True))


if __name__ == "__main__":
    unittest.main()
