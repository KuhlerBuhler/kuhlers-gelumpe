"""The one word that lets Korg's blue 2.02 start on a red flash, with synthetic images only."""
import struct
import unittest

import red_as_blue_probe as probe


def blue_like():
    """A VSB of zeros with the two words of the blue's mark check where Korg's blue 2.02 has them."""
    out = bytearray(0x200100)
    struct.pack_into("<I", out, probe.MARK_FIX - probe.BASE, probe.MARK_FIX_OLD)
    struct.pack_into("<I", out, probe.MARK_LITERAL - probe.BASE, 0x123)
    return bytes(out)


class MarkFix(unittest.TestCase):
    def test_changes_one_word(self):
        before = blue_like()
        after = probe.mark_fix(before)
        diff = [i for i in range(len(before)) if before[i] != after[i]]
        self.assertEqual(diff[0], probe.MARK_FIX - probe.BASE)
        self.assertLess(diff[-1] - diff[0], 4)
        self.assertEqual(probe.word(after, probe.MARK_FIX), probe.MARK_FIX_NEW)

    def test_the_new_word_loads_the_0x123_literal(self):
        new = probe.MARK_FIX_NEW
        self.assertEqual(new >> 28, 0x0)                    # EQ, like the instruction it replaces
        self.assertEqual((new >> 16) & 0xFFF, 0x59F)        # ldr r?, [pc, #+imm]
        self.assertEqual((new >> 12) & 0xF, 0)              # into r0
        self.assertEqual(probe.MARK_FIX + 8 + (new & 0xFFF), probe.MARK_LITERAL)

    def test_refuses_other_files(self):
        with self.assertRaises(ValueError):
            probe.mark_fix(bytes(0x200100))
        changed = bytearray(blue_like())
        struct.pack_into("<I", changed, probe.MARK_LITERAL - probe.BASE, 0x124)
        with self.assertRaises(ValueError):
            probe.mark_fix(bytes(changed))


if __name__ == "__main__":
    unittest.main()
