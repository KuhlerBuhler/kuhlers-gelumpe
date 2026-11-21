"""Tests for the text numbering of the BLECH menu (lang_texts.py): which strings get a number, the rewritten loads, the refusals."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.patch import lang_texts  # noqa: E402

SOURCE = """
    ldr r0, =str_a
    ldreq r1, =str_b
    ldr r2, =str_c
    ldr r3, =names
str_a: .asciz "ONE"
str_b:  ; a comment after the label
    .asciz "TWO"
str_c: .asciz "path"
names:
    .word str_a, str_c
"""
TEXTS = {"str_a": {"text": "EINS"}, "str_b": {"text": "ZWEI"}, "str_c": {"keep": "Dateipfad"}}


class LangTexts(unittest.TestCase):
    def test_strings_and_tables(self):
        self.assertEqual(lang_texts.strings(SOURCE), {"str_a": "ONE", "str_b": "TWO", "str_c": "path"})
        self.assertEqual(lang_texts.tables(SOURCE, {"str_a"}), {"names": ["str_a", "str_c"]})
        self.assertEqual(lang_texts.tables(SOURCE, {"str_b"}), {})

    def test_index_numbers_translated_strings_and_their_tables(self):
        self.assertEqual(lang_texts.index(SOURCE, TEXTS), ["names", "str_a", "str_b"])

    def test_index_needs_every_label(self):
        with self.assertRaisesRegex(lang_texts.LangError, "str_c"):
            lang_texts.index(SOURCE, {k: v for k, v in TEXTS.items() if k != "str_c"})

    def test_rewrite_loads_through_the_table_and_keeps_the_condition(self):
        out = lang_texts.rewrite(SOURCE, ["names", "str_a", "str_b"]).splitlines()
        self.assertIn("    ldreq r1, =LANG_TEXTS", out)
        self.assertIn("    ldreq r1, [r1]", out)
        self.assertIn("    ldreq r1, [r1, #8]", out)
        self.assertIn("    ldr r3, [r3, #0]", out)
        self.assertIn("    ldr r2, =str_c", out)
        self.assertIn("    .word str_a, str_c", out)

    def test_rewrite_refuses_other_uses(self):
        with self.assertRaisesRegex(lang_texts.LangError, "str_a"):
            lang_texts.rewrite("    add r0, r1, #str_a\n", ["str_a"])

    def test_key_follows_the_numbering(self):
        self.assertEqual(lang_texts.key(["a", "b"]), lang_texts.key(["a", "b"]))
        self.assertNotEqual(lang_texts.key(["a", "b"]), lang_texts.key(["b", "a"]))
        self.assertIn(".equ LANG_COUNT, 2", lang_texts.runtime_source(["a", "b"]))


if __name__ == "__main__":
    unittest.main()
