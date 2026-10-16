# SPDX-License-Identifier: GPL-2.0-only
"""synth_pcm_flash.py on made-up WAVs and waves: no Korg data, no firmware."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth_pcm_flash as F  # noqa: E402
import synth_probe as S  # noqa: E402


def wav(values, bits=24, rate=44100, channels=1):
    width = bits // 8
    body = b"".join(int(v).to_bytes(width, "little", signed=True) for v in values)
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * width * channels, width * channels, bits)
    return b"RIFF" + struct.pack("<I", 36 + len(body)) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"junk" + struct.pack("<I", 2) + b"\0\0" + b"data" + struct.pack("<I", len(body)) + body


class Wav(unittest.TestCase):
    def test_a_24_bit_mono_file_with_extra_chunks_is_read(self):
        rate, bits, values = F.parse_wav(wav([0, 5, -5, 8388607], 24))
        self.assertEqual((rate, bits, values), (44100, 24, [0, 5, -5, 8388607]))

    def test_stereo_is_averaged_and_other_formats_are_refused(self):
        _, _, values = F.parse_wav(wav([10, 20, -4, 4], 16, channels=2))
        self.assertEqual(values, [15, 0])
        with self.assertRaises(F.BankError):
            F.parse_wav(wav([1], 8))

    def test_one_gain_keeps_the_levels_between_waves(self):
        gain = 2047 / 1000
        self.assertEqual(F.quantise([1000, -1000, 500], 24, gain), [2047, -2047, 1024])


class Fit(unittest.TestCase):
    def test_the_zero_tail_goes_but_32_values_stay(self):
        self.assertEqual(len(F.trim_zero_tail([1] * 40 + [0] * 100)), 40)
        self.assertEqual(len(F.trim_zero_tail([0] * 100)), 32)

    def test_raw_size_matches_the_stream_the_probe_writes(self):
        for n in (1, 2047, 2048, 2049, 5000):
            self.assertEqual(F.raw_bytes(n), len(S.stream([1] * n)))

    def test_waves_that_fit_are_left_alone_and_strict_refuses_the_rest(self):
        small = [("A", [1] * 1000)]
        self.assertEqual(F.fit(small), (small, []))
        big = [("L1", [3] * 3_000_000), ("L2", [3] * 3_000_000), ("S", [3] * 1000)]
        with self.assertRaises(F.BankError):
            F.fit(big, strict=True)

    def test_too_big_waves_lose_only_their_tails_and_then_fit(self):
        big = [("L1", [3] * 3_000_000), ("L2", [3] * 3_000_000), ("S", [3] * 1000)]
        cut, report = F.fit(big)
        self.assertEqual(len(cut[2][1]), 1000)
        self.assertEqual([r["name"] for r in report], ["L1", "L2"])
        self.assertLessEqual(F.raw_bytes(sum(len(v) for _, v in cut)), S.BANK_SIZE - F.OVERHEAD)
        self.assertEqual(cut[0][1][-1], 0)           # faded out, no click

    def test_the_bank_with_a_filler_is_valid_and_the_flash_carries_the_mark(self):
        waves = [("A", S.sine(200, 2)), F.FILLER, ("C", S.sine(100, 1))]
        bank = S.build_bank(waves, pitch_word=F.ROOT_WORD)
        self.assertEqual(S.parse_bank(bank)["sum16"], 0)
        flash = F.flash_image(bank)
        self.assertEqual(len(flash), S.FLASH_SIZE)
        self.assertEqual(flash[0x220000:0x22000C], b"KORGelec2USR")
        self.assertEqual(S.bank_of(flash), bank)


if __name__ == "__main__":
    unittest.main()
