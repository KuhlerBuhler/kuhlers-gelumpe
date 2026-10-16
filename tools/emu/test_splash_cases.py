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


def with_bar(image, columns):
    frame = bytearray(image)
    for c in columns:
        frame[7 * 128 + c] &= S.PROGRESS_MASK
    return bytes(frame)


class SameImage(unittest.TestCase):
    def test_equal_frames_are_the_image_with_or_without_the_bar_allowed(self):
        self.assertTrue(S.same_image(IMAGE, IMAGE))
        self.assertTrue(S.same_image(IMAGE, IMAGE, bar=True))

    def test_the_bar_is_the_image_only_where_Korgs_build_draws_it(self):
        frame = with_bar(IMAGE, range(9, 120))
        self.assertFalse(S.same_image(frame, IMAGE), "Hacktribe's build draws nothing there")
        self.assertTrue(S.same_image(frame, IMAGE, bar=True))
        self.assertFalse(S.same_image(with_bar(IMAGE, [8]), IMAGE, bar=True), "one column left of the bar")
        self.assertFalse(S.same_image(with_bar(IMAGE, [120]), IMAGE, bar=True), "one column right of it")

    def test_anything_but_the_two_rows_of_the_bar_or_another_place_is_another_image(self):
        frame = bytearray(with_bar(IMAGE, range(9, 20)))
        frame[7 * 128 + 30] ^= 0x02                       # inside the bar's columns, but a row the bar leaves alone
        self.assertFalse(S.same_image(bytes(frame), IMAGE, bar=True))
        frame = bytearray(IMAGE)
        frame[5] ^= 1                                     # outside the bar
        self.assertFalse(S.same_image(bytes(frame), IMAGE, bar=True))

    def test_classify_tells_the_images_blank_and_other_apart(self):
        images = {"vsb": IMAGE, "stored": OTHER}
        self.assertEqual(S.classify(with_bar(OTHER, range(9, 30)), images, bar=True), "stored")
        self.assertEqual(S.classify(with_bar(OTHER, range(9, 30)), images), "other")
        self.assertEqual(S.classify(bytes(1024), images, bar=True), "blank")
        self.assertEqual(S.classify(IMAGE, images), "vsb")


if __name__ == "__main__":
    unittest.main()
