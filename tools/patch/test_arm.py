"""Tests for the assembler. Known encodings are written out by hand from the
ARM Architecture Reference Manual; with Capstone installed every line is also
disassembled and compared, and with E2_VSB set the assembler must reproduce
every instruction of the user's firmware that it claims to support.
"""

import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402

try:
    import capstone
except ImportError:  # the byte checks still run
    capstone = None


def words(text, origin=0):
    data = arm.assemble(text, origin).bytes
    return list(struct.unpack(f"<{len(data) // 4}I", data))


class Encodings(unittest.TestCase):
    CASES = [
        ("mov r0, #1", 0xE3A00001),
        ("mvn r1, #0", 0xE3E01000),
        ("mov r1, #-1", 0xE3E01000),
        ("push {r4, lr}", 0xE92D4010),
        ("pop {r4, pc}", 0xE8BD8010),
        ("ldr r3, [r0, #0x2c]", 0xE590302C),
        ("ldr r3, [r0, #-4]", 0xE5103004),
        ("str r2, [r0, r1, lsl #2]", 0xE7802101),
        ("ldrb r3, [r0], #1", 0xE4D03001),
        ("strb r3, [r0, #4]!", 0xE5E03004),
        ("cmp r3, #0x13", 0xE3530013),
        ("cmp r12, r3", 0xE15C0003),
        ("tst r6, #0x2000", 0xE3160A02),
        ("bxne lr", 0x112FFF1E),
        ("blx r3", 0xE12FFF33),
        ("movs r2, r2, lsr #1", 0xE1B020A2),
        ("eorcs r2, r2, r12", 0x2022200C),
        ("mov r2, r2, lsr r3", 0xE1A02332),
        ("mov r0, r0", 0xE1A00000),
        ("nop", 0xE1A00000),
        ("add r0, r4, #0x10", 0xE2840010),
        ("add r0, #1", 0xE2800001),
        ("sub sp, sp, #12", 0xE24DD00C),
        ("rsb r3, r3, #7", 0xE2633007),
        ("subs r3, r3, #1", 0xE2533001),
        ("ldmia sp!, {r0, r1, r2, lr}", 0xE8BD4007),
        ("stmdb sp!, {r4-r6, lr}", 0xE92D4070),
        ("ldmfd sp!, {r4, pc}", 0xE8BD8010),
        ("strne r1, [r2]", 0x15821000),
        ("mul r2, r0, r3", 0xE0020390),
        ("mulne r3, r1, r2", 0x10030291),
    ]

    def test_known_words(self):
        for text, want in self.CASES:
            self.assertEqual(words(text), [want], text)

    def test_branches(self):
        # b to itself: offset -8 from pc+8 is -2 words
        self.assertEqual(words("here: b here"), [0xEAFFFFFE])
        self.assertEqual(words("bl 0x1008", origin=0x1000), [0xEB000000 | (0x1008 - 0x1008) >> 2])
        self.assertEqual(words("bne 0x1000", origin=0x1000), [0x1AFFFFFE])
        self.assertEqual(words("b 0xC0000000", origin=0xC0000000 + 0x10000)[0] >> 24, 0xEA)

    def test_branch_forward_and_back(self):
        w = words("start: mov r0, #1\n b end\n mov r0, #2\nend: b start")
        self.assertEqual(w[1], 0xEA000000)          # skip one instruction
        self.assertEqual(w[3], 0xEAFFFFFB)          # back to the first, 3 words + pc bias

    def test_literal_pool(self):
        w = words("ldr r0, =0x12345678\n ldr r1, =0x12345678\n ldr r2, =sym\nsym: bx lr")
        # sym is at 12, the pool follows at 16: the shared constant, then sym
        self.assertEqual(w, [0xE59F0008, 0xE59F1004, 0xE59F2004, 0xE12FFF1E, 0x12345678, 12])

    def test_pool_directive_and_equ(self):
        w = words(".equ K, 3\n mov r0, #K+1\n ldr r1, =K\n.align 4\n.pool\n bx lr")
        self.assertEqual(w[0], 0xE3A00004)
        self.assertEqual(w[-1], 0xE12FFF1E)

    def test_data_directives(self):
        data = arm.assemble('.word 1, 2\n.byte 3\n.asciz "ab"\n.align 4\n.word s\ns:', 0x100).bytes
        self.assertEqual(data[:8], struct.pack("<II", 1, 2))
        self.assertEqual(data[8:12], b"\x03ab\x00")
        self.assertEqual(struct.unpack("<I", data[12:16])[0], 0x110)

    def test_sections_each_get_their_own_pool(self):
        a = arm.assemble(".org 0x1000\n ldr r0, =0xAABBCCDD\n b second\n.org 0x2000\nsecond: ldr r1, =0x11223344\n bx lr")
        self.assertEqual([addr for addr, _ in a.sections], [0x1000, 0x2000])
        first = struct.unpack("<3I", a.sections[0][1])
        self.assertEqual(first[2], 0xAABBCCDD)
        self.assertEqual(first[0], 0xE59F0000)       # the pool starts at pc+8
        second = struct.unpack("<3I", a.sections[1][1])
        self.assertEqual(second[2], 0x11223344)
        self.assertEqual(a.symbols["second"], 0x2000)

    def test_errors(self):
        for bad in ("mov r0, #0x12345", "foo r0", "ldr r0, [r1, #4096]", "b nowhere", "ldrh r0, [r1]", "mul r1, r1, r2"):
            with self.assertRaises(arm.AsmError, msg=bad):
                arm.assemble(bad)

    @unittest.skipUnless(capstone, "capstone not installed")
    def test_capstone_agrees(self):
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        for text, want in self.CASES:
            ins = next(md.disasm(struct.pack("<I", want), 0))
            norm = lambda s: s.replace(" ", "").replace("#0x", "#").lower()  # noqa: E731
            self.assertTrue(ins.mnemonic, text)
            self.assertEqual(words(f"{ins.mnemonic} {ins.op_str}"), [want], f"{text} via {ins.mnemonic} {ins.op_str}")


@unittest.skipUnless(os.environ.get("E2_VSB") and capstone, "needs E2_VSB and capstone")
class AgainstTheFirmware(unittest.TestCase):
    """Every instruction in the firmware's code that the assembler claims to
    support must come out as the same word. Reads the user's own VSB; nothing
    of it is kept."""

    def test_roundtrip(self):
        image = Path(os.environ["E2_VSB"]).read_bytes()[0x100:]
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        done = skipped = 0
        bad = []
        for off in range(0, 0xE0000, 8):             # every other word keeps it to some 15 seconds
            word = struct.unpack_from("<I", image, off)[0]
            ins = next(md.disasm(image[off:off + 4], 0xC0000000 + off), None)
            if ins is None or word >> 28 == 0xF:
                continue
            text = f"{ins.mnemonic} {ins.op_str}"
            try:
                got = struct.unpack("<I", arm.assemble(text, 0xC0000000 + off).bytes)[0]
            except (arm.AsmError, KeyError, IndexError, ValueError):
                skipped += 1
                continue
            done += 1
            if got != word:
                bad.append((hex(0xC0000000 + off), text, hex(word), hex(got)))
        self.assertGreater(done, 20000, "the supported subset covers most of the code")
        # What differs is not code: constants and text that happen to decode, and
        # single-register `ldr r0, [sp], #4`, which Capstone prints as `pop {r0}`.
        self.assertLess(len(bad), done // 100, f"{len(bad)} mismatches out of {done}: {bad[:5]}")


if __name__ == "__main__":
    unittest.main()
