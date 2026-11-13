# SPDX-License-Identifier: GPL-2.0-only
"""The start image check against Korg's own build: its loading bar may be drawn over the image, nothing else may.
No firmware needed (docs/messungen/2026-10-14-stock-blech.md for what the bar is)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))
import splash_cases as S  # noqa: E402

IMAGE = bytes(i % 251 for i in range(896)) + bytes([0xFF]) * 128           # page 7 is lit everywhere, so the bar changes every column
OTHER = bytes(b ^ 0xFF for b in IMAGE)
OTHER = OTHER[:896] + bytes([0x60]) * 128                 # a stored image with the two bar rows lit in page 7


RED = S.PROGRESS_BARS["stock"]                            # Korg's red build: rows 61 and 62 in page 7
BLUE = S.PROGRESS_BARS["synth"]                           # Korg's blue build: rows 54 and 55 in page 6


def with_bar(image, columns, page=7, mask=RED[1]):
    frame = bytearray(image)
    for c in columns:
        frame[page * 128 + c] &= mask
    return bytes(frame)


class SameImage(unittest.TestCase):
    def test_equal_frames_are_the_image_with_or_without_the_bar_allowed(self):
        self.assertTrue(S.same_image(IMAGE, IMAGE))
        self.assertTrue(S.same_image(IMAGE, IMAGE, bar=RED))

    def test_the_bar_is_the_image_only_where_Korgs_build_draws_it(self):
        frame = with_bar(IMAGE, range(9, 120))
        self.assertFalse(S.same_image(frame, IMAGE), "Hacktribe's build draws nothing there")
        self.assertTrue(S.same_image(frame, IMAGE, bar=RED))
        self.assertFalse(S.same_image(with_bar(IMAGE, [8]), IMAGE, bar=RED), "one column left of the bar")
        self.assertFalse(S.same_image(with_bar(IMAGE, [120]), IMAGE, bar=RED), "one column right of it")

    def test_anything_but_the_two_rows_of_the_bar_or_another_place_is_another_image(self):
        frame = bytearray(with_bar(IMAGE, range(9, 20)))
        frame[7 * 128 + 30] ^= 0x02                       # inside the bar's columns, but a row the bar leaves alone
        self.assertFalse(S.same_image(bytes(frame), IMAGE, bar=RED))
        frame = bytearray(IMAGE)
        frame[5] ^= 1                                     # outside the bar
        self.assertFalse(S.same_image(bytes(frame), IMAGE, bar=RED))

    def test_classify_tells_the_images_blank_and_other_apart(self):
        images = {"vsb": IMAGE, "stored": OTHER}
        self.assertEqual(S.classify(with_bar(OTHER, range(9, 30)), images, bar=RED), "stored")
        self.assertEqual(S.classify(with_bar(OTHER, range(9, 30)), images), "other")
        self.assertEqual(S.classify(bytes(1024), images, bar=RED), "blank")
        self.assertEqual(S.classify(IMAGE, images), "vsb")

    def test_the_blue_bar_is_two_rows_higher_in_page_6(self):
        image = bytes([0xFF]) * 1024
        frame = with_bar(image, range(9, 120), page=6, mask=BLUE[1])
        self.assertTrue(S.same_image(frame, image, bar=BLUE))
        self.assertFalse(S.same_image(frame, image, bar=RED), "the red bar is in page 7")
        self.assertFalse(S.same_image(with_bar(image, range(9, 120), page=6, mask=RED[1]), image, bar=BLUE), "other rows")


if __name__ == "__main__":
    unittest.main()
