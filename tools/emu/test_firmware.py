# SPDX-License-Identifier: GPL-2.0-only
"""Which build an image is and where its places sit (firmware.py). The first tests run on made-up code, no
Korg data. The last one looks at the user's own VSB (E2_VSB, optionally E2_STOCK_VSB for Korg's original),
skipped without it, a failure when E2_EMU_REQUIRED=1."""

import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import firmware as F  # noqa: E402

REQUIRED = os.environ.get("E2_EMU_REQUIRED") == "1"

# push {r4, lr}; mov r4, r0; bl <somewhere>; ldr r1, [pc, #0x40]; cmp r3, #150; ... then plain words
CODE = [0xE92D4010, 0xE1A04000, 0xEB000123, 0xE59F1040, 0xE3530096] + [0xE1A00000 + i for i in range(11)]


SYNTH_CODE = CODE[:11] + [0xE1A06000 + i for i in range(5)]     # the same code with one place that differs, as the synth's screen manager


def image(*placed, build_code=False):
    """An erased payload with `placed` = (RAM address, words) written into it."""
    payload = bytearray(b"\xff" * F.PAYLOAD_SIZE)
    for at, words in placed:
        payload[at - F.BASE:at - F.BASE + 4 * len(words)] = struct.pack(f"<{len(words)}I", *words)
    if build_code:
        payload[F.HACKTRIBE_CODE:F.HACKTRIBE_CODE + 4] = b"\x7f\x40\x2d\xe9"
    return bytes(payload)


def site(name, at, words=CODE, **kw):
    return F.Site(name, at, F.sign(image((at, words)), at), **kw)


class Signatures(unittest.TestCase):
    def test_a_branch_target_and_a_pc_relative_offset_do_not_count(self):
        other = list(CODE)
        other[2] = 0xEB000999          # bl somewhere else
        other[3] = 0xE59F1FFC          # ldr r1, [pc, #0xffc], another literal
        self.assertEqual(F.sign(image((0xC0001000, CODE)), 0xC0001000), F.sign(image((0xC0001000, other)), 0xC0001000))

    def test_any_other_word_counts(self):
        other = list(CODE)
        other[1] = 0xE1A05000          # mov r5, r0
        self.assertNotEqual(F.sign(image((0xC0001000, CODE)), 0xC0001000), F.sign(image((0xC0001000, other)), 0xC0001000))

    def test_the_signature_does_not_depend_on_where_the_code_sits(self):
        self.assertEqual(F.sign(image((0xC0001000, CODE)), 0xC0001000), F.sign(image((0xC0050000, CODE)), 0xC0050000))


class Lookup(unittest.TestCase):
    def test_a_place_at_its_usual_address_is_found_there(self):
        p = F.identify(image((0xC0001000, CODE)), (site("a", 0xC0001000),), ("a",))
        self.assertEqual((p.sites, p.moved, p.missing), ({"a": 0xC0001000}, (), ()))

    def test_the_entry_is_inside_the_window(self):
        p = F.identify(image((0xC0001000, CODE)), (site("a", 0xC0001000, entry=0x1C),), ("a",))
        self.assertEqual(p.site("a"), 0xC000101C)

    def test_a_place_that_moved_is_found_and_said_to_have_moved(self):
        usual = site("a", 0xC0001000)
        p = F.identify(image((0xC0070000, CODE)), (usual,), ("a",))
        self.assertEqual((p.sites["a"], p.moved), (0xC0070000, ("a",)))

    def test_a_place_that_sits_twice_is_refused(self):
        with self.assertRaisesRegex(F.ProfileError, "a ist mehrfach da"):
            F.identify(image((0xC0070000, CODE), (0xC0080000, CODE)), (site("a", 0xC0001000),), ("a",))

    def test_a_missing_required_place_is_refused_by_name(self):
        with self.assertRaisesRegex(F.ProfileError, "flash_read fehlt"):
            F.identify(image(), (site("flash_read", 0xC0001000),), ("flash_read",))

    def test_a_missing_optional_place_is_reported_and_the_rest_works(self):
        p = F.identify(image((0xC0001000, CODE)), (site("a", 0xC0001000), site("b", 0xC0002000, [0xE1A00000 + 99 + i for i in range(16)])), ("a",))
        self.assertEqual((sorted(p.sites), p.missing), (["a"], ("b",)))
        with self.assertRaisesRegex(F.ProfileError, "b fehlt"):
            p.site("b")

    def test_a_literal_is_read_out_of_the_code(self):
        words = list(CODE)
        # the ldr at +0xC sits at window + 12; its literal is at window + 12 + 8 + 0x40
        payload = bytearray(image((0xC0001000, words)))
        struct.pack_into("<I", payload, 0x1000 + 12 + 8 + 0x40, 0xC0345678)
        s = F.Site("a", 0xC0001000, F.sign(bytes(payload), 0xC0001000), reads=(("ptr", 0xC, "literal"),))
        p = F.identify(bytes(payload), (s,), ("a",))
        self.assertEqual(p.values, {"ptr": 0xC0345678})

    def test_an_optional_read_that_is_not_what_it_should_be_leaves_the_place_out(self):
        s = F.Site("a", 0xC0001000, F.sign(image((0xC0001000, CODE)), 0xC0001000), reads=(("v", 0x4, "literal"),))
        p = F.identify(image((0xC0001000, CODE)), (s,), ())
        self.assertEqual((p.sites, p.missing), ({}, ("a",)))

    def test_a_wrong_size_is_refused(self):
        with self.assertRaisesRegex(F.ProfileError, "Byte hinter dem Kopf"):
            F.identify(bytes(100))

    def test_the_real_table_does_not_know_an_empty_image(self):
        with self.assertRaisesRegex(F.ProfileError, "keine Sampler-2.02-Fassung"):
            F.identify(bytes(F.PAYLOAD_SIZE))


class Synth(unittest.TestCase):
    """The fallback to the synth's table, on made-up code: the tables are swapped for stand-ins."""

    def setUp(self):
        self.saved = F.SITES, F.SYNTH_SITES
        F.SITES = (site("a", 0xC0001000),)
        F.SYNTH_SITES = (F.Site("a", 0xC0004000, F.sign(image((0xC0004000, SYNTH_CODE)), 0xC0004000)),)

    def tearDown(self):
        F.SITES, F.SYNTH_SITES = self.saved

    def test_an_image_with_the_synths_places_is_the_synth_build(self):
        p = F.identify(image((0xC0004000, SYNTH_CODE)), F.SITES, ("a",))
        self.assertEqual((p.build, p.sites, p.moved, p.user_mark), ("synth", {"a": 0xC0004000}, (), b"KORGelec2USR"))
        self.assertTrue(F.is_synth(image((0xC0004000, SYNTH_CODE))))

    def test_the_sampler_wins_and_keeps_its_mark(self):
        p = F.identify(image((0xC0001000, CODE)), F.SITES, ("a",))
        self.assertEqual((p.build, p.user_mark), ("stock", b"KORGele2sUSR"))
        self.assertFalse(F.is_synth(image((0xC0001000, CODE))))

    def test_neither_is_refused_with_the_samplers_message(self):
        with self.assertRaisesRegex(F.ProfileError, "keine Sampler-2.02-Fassung"):
            F.identify(image(), F.SITES, ("a",))

    def test_the_synth_table_is_the_samplers_with_other_addresses(self):
        F.SITES, F.SYNTH_SITES = self.saved
        self.assertEqual([s.name for s in F.SITES], [s.name for s in F.SYNTH_SITES])
        self.assertEqual([s.sig for s in F.SITES if s.name != "screens"], [s.sig for s in F.SYNTH_SITES if s.name != "screens"])
        self.assertTrue(all(a.at != b.at for a, b in zip(F.SITES, F.SYNTH_SITES)))


class Build(unittest.TestCase):
    def test_hacktribes_code_run_tells_the_builds_apart(self):
        self.assertEqual(F.build_of(image()), "stock")
        self.assertEqual(F.build_of(image(build_code=True)), "hacktribe")


class BlueFile(unittest.TestCase):
    def test_the_blue_electribe_is_the_synth_build_with_every_place_found(self):
        path = os.environ.get("E2_BLUE_VSB")
        if not path:
            self.skipTest("E2_BLUE_VSB not set")
        payload = Path(path).read_bytes()[0x100:]
        p = F.identify(payload)
        self.assertEqual((p.build, p.moved, p.missing), ("synth", (), ()))
        self.assertTrue(F.is_synth(payload))
        self.assertEqual(p.screens, 0xC03406B0)
        self.assertEqual(p.user_mark, b"KORGelec2USR")


class OwnFiles(unittest.TestCase):
    def files(self):
        out = {k: os.environ[v] for k, v in (("hacktribe", "E2_VSB"), ("stock", "E2_STOCK_VSB")) if os.environ.get(v)}
        if not out:
            if REQUIRED:
                self.fail("E2_VSB is not set")
            self.skipTest("E2_VSB not set")
        return out

    def test_every_place_is_where_it_usually_is_and_the_build_is_named(self):
        for build, path in self.files().items():
            with self.subTest(path=path):
                payload = Path(path).read_bytes()[0x100:]
                p = F.identify(payload)
                self.assertEqual((p.moved, p.missing), ((), ()), "no place moved or went missing")
                self.assertEqual(p.build, F.build_of(payload))
                self.assertEqual(
                    (p.assert_handler, p.flash_read, p.dsp_upload, p.tx_full, p.screens, p.value("panel")),
                    (0xC00298BC, 0xC001E4AC, 0xC0011AB8, 0xC0024CB4, 0xC03404C0, 0xC033E6F8))
                self.assertIn(build, ("hacktribe", "stock"))

    def test_a_copy_with_the_presets_changed_is_still_the_same_build(self):
        for path in self.files().values():
            payload = bytearray(Path(path).read_bytes()[0x100:])
            before = F.identify(bytes(payload))
            payload[0xB5030:0xB5030 + 0x20C] = bytes(range(256)) * 2 + bytes(12)     # a preset record
            payload[0xF9854:0xF9854 + 1024] = bytes(1024)                            # the start image
            self.assertEqual(F.identify(bytes(payload)).summary(), before.summary())


if __name__ == "__main__":
    unittest.main()
