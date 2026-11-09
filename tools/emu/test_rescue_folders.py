"""The card layouts of rescue_folders_probe.py, with synthetic files only."""
import unittest

import rescue_folders_probe as probe
from hacktribe_blue_probe import with_head


class Folders(unittest.TestCase):
    def test_the_three_folders_of_the_rescue_page(self):
        # data/rescue.mjs, folder:all:*: Korg's folder of the colour, hacktribe, blechtribe
        self.assertEqual(probe.FOLDERS["red"], ["electribe sampler", "hacktribe", "blechtribe"])
        self.assertEqual(probe.FOLDERS["blue"], ["electribe", "hacktribe", "blechtribe"])

    def test_card_puts_the_same_file_in_every_folder(self):
        vsb = b"\x01" * 16
        files = probe.card(probe.FOLDERS["red"], vsb)
        self.assertEqual(sorted(files), ["/KORG/blechtribe/System/SYSTEM.VSB", "/KORG/electribe sampler/System/SYSTEM.VSB",
                                         "/KORG/hacktribe/System/SYSTEM.VSB"])
        self.assertTrue(all(v is vsb for v in files.values()))

    def test_copy_question_only_for_the_synth_build_without_blechtribe(self):
        blue = with_head(bytes(0x200100), "blue")
        sampler = with_head(bytes(0x200100), "sampler")
        others = probe.card(["electribe", "hacktribe"], b"")
        self.assertTrue(probe.asks_to_copy(blue, others))
        self.assertFalse(probe.asks_to_copy(blue, probe.card(probe.FOLDERS["blue"], b"")))
        self.assertFalse(probe.asks_to_copy(sampler, others))


if __name__ == "__main__":
    unittest.main()
