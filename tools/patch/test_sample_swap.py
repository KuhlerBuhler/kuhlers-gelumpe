"""The sample swap's routines run in Unicorn against tables made here; no firmware image is needed."""
import struct
import unittest

import unicorn
from unicorn import arm_const as R

import arm
import sample_swap as p

TRAP = 0xC01FF000
STACK = 0xC1F00000
SCREENS = 0xC0340000
F = p.FIRMWARE


def word(n):
    return struct.pack("<I", n & 0xFFFFFFFF)


class Swap:
    def __init__(self):
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.uc.mem_map(0xC0000000, 0x02000000)
        self.uc.mem_map(0xC2700000, 0x00200000)
        sections, self.sym = p.build_code(SCREENS)
        for at, data in sections:
            self.uc.mem_write(at, data)
        self.uc.mem_write(TRAP, word(0xE1A00000))
        # stand-ins of our own for the firmware routines the tested paths call
        stubs = {F["REPEATS"]: "ldr r3, =0x3B06\nldrb r0, [r0, r3]\nbx lr",
                 F["SWITCH"]: "bx lr",
                 F["DELETE"]: "bx lr"}
        for at, text in stubs.items():
            self.uc.mem_write(at, arm.assemble(text, origin=at).bytes)
        self.calls = []
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.note, begin=F["SWITCH"], end=F["SWITCH"])
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.note, begin=F["DELETE"], end=F["DELETE"])
        self.set_state("MODE", 1)
        self.set_state("GEN", 7)
        self.uc.mem_write(p.STATE + p.FAILED, bytes(128))

    def note(self, uc, at, size, _):
        self.calls.append((at, uc.reg_read(R.UC_ARM_REG_R0), uc.reg_read(R.UC_ARM_REG_R1)))

    def set_state(self, name, value):
        self.uc.mem_write(p.STATE + p.OFF[name], word(value))

    def state(self, name):
        return struct.unpack("<I", self.uc.mem_read(p.STATE + p.OFF[name], 4))[0]

    def u32(self, at):
        return struct.unpack("<I", self.uc.mem_read(at, 4))[0]

    def call(self, name, *args, regs=None):
        for i, value in enumerate(args):
            self.uc.reg_write(R.UC_ARM_REG_R0 + i, value & 0xFFFFFFFF)
        for reg, value in (regs or {}).items():
            self.uc.reg_write(reg, value)
        self.uc.reg_write(R.UC_ARM_REG_SP, STACK)
        self.uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        self.uc.reg_write(R.UC_ARM_REG_R11, p.STATE)
        self.uc.emu_start(self.sym[name] if isinstance(name, str) else name, TRAP, count=5_000_000)
        assert self.uc.reg_read(R.UC_ARM_REG_SP) == STACK, f"{name} left the stack moved"
        return self.uc.reg_read(R.UC_ARM_REG_R0)

    def slot(self, slot, active=True, base=0, length=0, in_file=True):
        """Identity mappings for a slot, as the firmware has them for a sample of an exported file."""
        k = slot
        self.uc.mem_write(F["NAMES"] + slot * 32 + 30, struct.pack("<H", k + 50))
        self.uc.mem_write(F["MAP_A"] + k * 32 + 16, struct.pack("<H", k))
        self.uc.mem_write(F["MAP_B"] + k * 16 + 8, struct.pack("<H", k))
        self.uc.mem_write(F["MAP_C"] + k * 8 + 2, struct.pack("<H", k))
        meta = F["META"] + k * 0x45C
        self.uc.mem_write(meta, word(base) + word(length))
        self.uc.mem_write(meta + 11, bytes([1 if active else 0]))
        self.uc.mem_write(p.HDR + 16 + 4 * slot, word(0x1000 + slot if in_file else 0))

    def parts(self, pattern, samples):
        for i in range(16):
            self.uc.mem_write(F["BANK"] + pattern * 0x4000 + 0x808 + i * 0x330,
                              struct.pack("<H", samples[i] if i < len(samples) else 0xFFFF))


class Resident(unittest.TestCase):
    def test_follows_the_three_mappings_to_the_active_flag(self):
        s = Swap()
        s.slot(600, active=True)
        s.slot(601, active=False)
        self.assertEqual(s.call("resident", 600), 1)
        self.assertEqual(s.call("resident", 601), 0)
        s.uc.mem_write(F["NAMES"] + 602 * 32 + 30, struct.pack("<H", 10))
        self.assertEqual(s.call("resident", 602), 0, "an import number below 50 is no slot")
        self.assertEqual(s.call("resident", 1000), 0)


class Ready(unittest.TestCase):
    def test_a_pattern_is_ready_when_every_loadable_sample_is_in_the_dsp(self):
        s = Swap()
        s.slot(600, active=True)
        s.slot(601, active=False)
        s.slot(602, active=False, in_file=False)
        s.parts(5, [600, 601, 602, 7, 0xFFFF])
        self.assertEqual(s.call("ready", 5), 0)
        s.uc.mem_write(p.STATE + p.FAILED + 4 * (601 >> 5), word(1 << (601 & 31)))
        self.assertEqual(s.call("ready", 5), 1, "a slot marked as failed does not hold the switch")
        self.assertEqual(s.call("ready", 250), 1)

    def test_the_sequence_end_plays_the_running_pattern_again(self):
        s = Swap()
        s.slot(601, active=False)
        s.parts(5, [601])
        player = 0xC1000000
        s.uc.mem_write(player + 0x318, word(3))
        s.call("ss_gate_seq", player, 5, 0)
        self.assertEqual(s.calls[-1][2], 3, "the switch is asked for the running number")
        self.assertEqual(s.state("REQ"), 5)
        s.slot(601, active=True)
        s.call("ss_gate_seq", player, 5, 0)
        self.assertEqual(s.calls[-1][2], 5)
        s.set_state("MODE", 0)
        s.slot(601, active=False)
        s.call("ss_gate_seq", player, 5, 0)
        self.assertEqual(s.calls[-1][2], 5, "with the swap off every switch goes through")

    def test_the_chain_keeps_its_counter_at_the_last_round(self):
        s = Swap()
        s.slot(601, active=False)
        s.parts(9, [601])
        player, pattern = 0xC1000000, 0xC1100000
        s.uc.mem_write(pattern + 0x3B06, bytes([4]))
        s.uc.mem_write(player + 0x318, word(2))
        s.uc.mem_write(player + 0x31C, word(0))
        # the chain step's frame: push {r4, r5, r6, lr}, as at 0xC0079A74
        frame = STACK - 16
        s.uc.mem_write(frame, word(0x11) + word(0x22) + word(0x33) + word(TRAP))
        s.uc.reg_write(R.UC_ARM_REG_SP, frame)
        for reg, value in ((R.UC_ARM_REG_R0, 9), (R.UC_ARM_REG_R4, player), (R.UC_ARM_REG_R6, pattern), (R.UC_ARM_REG_LR, 0)):
            s.uc.reg_write(reg, value)
        s.uc.emu_start(s.sym["ss_gate_chain"], TRAP, count=100_000)
        self.assertEqual(s.u32(player + 0x318), 2, "the target was not taken")
        self.assertEqual(s.u32(player + 0x31C), 3, "the next sequence end tries the chain again")
        self.assertEqual(s.state("REQ"), 9)
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_R4), 0x11)
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_SP), STACK)


class Place(unittest.TestCase):
    def test_the_lowest_aligned_place_that_overlaps_nothing(self):
        s = Swap()
        lo = F["DSP_MIN"]
        s.slot(600, base=lo, length=0x100)
        s.slot(601, base=lo + 0x200, length=0x105)
        self.assertEqual(s.call("first_fit", 0x100), lo + 0x100)
        self.assertEqual(s.call("first_fit", 0x120), lo + 0x320, "behind the second sample, aligned to 32 bytes")
        s.uc.mem_write(s.sym["ss_cap"], word(0x400))
        self.assertEqual(s.call("first_fit", 0x100), lo + 0x100)
        self.assertEqual(s.call("first_fit", 0x200), 0, "nothing beyond the budget")

    def test_moves_out_a_sample_the_two_patterns_do_not_use(self):
        s = Swap()
        lo = F["DSP_MIN"]
        s.uc.mem_write(s.sym["ss_cap"], word(0x200))
        s.slot(600, base=lo, length=0x100)
        s.slot(601, base=lo + 0x100, length=0x100)
        prot = [601] + [0xFFFF] * 31
        s.uc.mem_write(p.STATE + p.PROT, struct.pack("<32H", *prot))
        deleted = []

        def delete(uc, *_):
            k = uc.reg_read(R.UC_ARM_REG_R0)
            deleted.append(k)
            uc.mem_write(F["META"] + k * 0x45C + 11, b"\0")
        s.uc.hook_add(unicorn.UC_HOOK_CODE, delete, begin=F["DELETE"], end=F["DELETE"])
        self.assertEqual(s.call("place", 0x100), lo)
        self.assertEqual(deleted, [600])
        self.assertEqual(s.call("place", 0x200), 0, "the protected sample stays")


class Giver(unittest.TestCase):
    def test_hands_out_the_buffer_and_drops_the_cache(self):
        s = Swap()
        s.set_state("SESSION", 1)
        s.set_state("CFILL", 1)
        out = 0xC1000000
        self.assertEqual(s.call("ss_giver", out), 0xC0D3A940)
        self.assertEqual(s.u32(out), 0x1A00100)
        self.assertEqual((s.state("GEN"), s.state("SESSION"), s.state("CFILL")), (8, 0, 0))


class Encoding(unittest.TestCase):
    def test_half_word_lines(self):
        text = p.halfword("ldrh r1, [r2, #30]\nstrh r3, [r1]\nldrh r0, [r0, r1]")
        self.assertEqual(text.splitlines(), [".word 0xe1d211be", ".word 0xe1c130b0", ".word 0xe19000b1"])

    def test_the_code_fits_its_areas(self):
        sections, _ = p.build_code(SCREENS)
        for at, data in sections:
            area = next(a for a in p.AREAS if a[0] <= at < a[1])
            self.assertLessEqual(at + len(data), area[1])


if __name__ == "__main__":
    unittest.main()
