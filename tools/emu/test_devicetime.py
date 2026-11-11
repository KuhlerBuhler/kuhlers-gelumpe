# SPDX-License-Identifier: GPL-2.0-only
"""devicetime.py: the base rate matches the emulator's, the four timing_probe loops come out as measured
(docs/messungen/2026-10-16-emulator-timing.md, mean of three device runs), by hand and with the live model
(`Pace`) that machine.py charges its slices by."""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "patch"))
import arm  # noqa: E402
import devicetime  # noqa: E402
import machine  # noqa: E402

# measured per round on the device: alu 20.15 ns, mul 26.82, memh 47.88, mem 143.43, memu 234.1
MEASURED = {"alu": 20.15, "mul": 26.82, "memh": 47.88, "mem": 143.43, "memu": 234.1}
CODE_AT = 0xC1000000
LOOPS = {                 # the loops of tools/device/timing_probe.py, r7 the address read, r5 the rounds
    "alu": "add r0, r0, r1\n eor r1, r1, r0, ror #3\n subs r5, r5, #1\n bne loop",
    "mul": "mul r3, r0, r1\n add r0, r3, #1\n subs r5, r5, #1\n bne loop",
    "mem": "ldmia r7!, {r0, r1, r3, r4}\n add lr, lr, r0\n add lr, lr, r1\n add lr, lr, r3\n add lr, lr, r4\n"
           " subs r5, r5, #1\n bne loop",
    "memh": "ldmia r7!, {r0, r1, r3, r4}\n bic r7, r7, #0x1000\n add lr, lr, r0\n add lr, lr, r1\n add lr, lr, r3\n"
            " add lr, lr, r4\n subs r5, r5, #1\n bne loop",
}


def word(w):
    return devicetime.decode(w, 0x1000)


class Decode(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(word(0xE0030190)[0], 1)                          # mul r3, r0, r1
        self.assertEqual(word(0xE8B7001B)[1], (7, 16, True))              # ldmia r7!, {r0, r1, r3, r4}
        self.assertEqual(word(0xE5910004)[1], (1, 4, False))              # ldr r0, [r1, #4]
        self.assertEqual(word(0xE4D10001)[1], (1, 1, True))               # ldrb r0, [r1], #1
        self.assertEqual(word(0xE1D100B2)[1], (1, 2, False))              # ldrh r0, [r1, #2]
        self.assertIsNone(word(0xE5810004)[1])                            # str r0, [r1, #4]
        self.assertEqual(word(0x1AFFFFFC)[2], ("loop", 0x1000 + 8 - 16))  # bne back
        self.assertEqual(word(0xEB000000)[2], devicetime.END)             # bl
        self.assertEqual(word(0xE12FFF1E)[2], devicetime.END)             # bx lr
        self.assertEqual(word(0xE8BD8010)[2], devicetime.END)             # pop {r4, pc}
        self.assertIsNone(word(0xE0800001)[2])                            # add r0, r0, r1
        self.assertEqual(devicetime.advances(0xE2877010), 7)              # add r7, r7, #16


class ByHand(unittest.TestCase):
    def test_base_rate_is_the_emulators(self):
        self.assertEqual(devicetime.ALU_NS_PER_INSN, machine.NS_PER_INSN)

    def test_probe_loops(self):
        est = devicetime.estimate_device_ns
        loop = lambda insns: insns * machine.NS_PER_INSN
        self.assertAlmostEqual(est(loop(4)), MEASURED["alu"], delta=1)
        self.assertAlmostEqual(est(loop(4), mul_insns=1), MEASURED["mul"], delta=1)
        self.assertAlmostEqual(est(loop(8), read_hit_bytes=16), MEASURED["memh"], delta=1.5)
        self.assertAlmostEqual(est(loop(7), read_stream_bytes=16), MEASURED["mem"], delta=2)
        self.assertAlmostEqual(est(loop(7), read_uncached_bytes=16), MEASURED["memu"], delta=2)

    def test_plain_code_is_unchanged(self):
        self.assertEqual(devicetime.estimate_device_ns(1234), 1234)


class Live(unittest.TestCase):
    """The loops run in a bare Unicorn, sliced as machine.run_slice slices: each slice is charged at the rate Pace gives
    for the pc it starts at. Device ns per round = charged time / rounds."""

    def setUp(self):
        try:
            import unicorn  # noqa: F401
        except ImportError:
            self.skipTest("Unicorn not installed")

    def run_loop(self, name, rounds, at=0xC0040000, pace=None):
        import struct
        import unicorn
        from unicorn import arm_const as A
        code = arm.assemble(f"loop: {LOOPS[name]}\ndone: b done", CODE_AT)
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        uc.ctl_set_cpu_model(A.UC_CPU_ARM_926)
        uc.mem_map(0xC0000000, 0x08000000)
        uc.mem_write(CODE_AT, code.bytes)
        uc.reg_write(A.UC_ARM_REG_R5, rounds)
        uc.reg_write(A.UC_ARM_REG_R7, at)
        uc.reg_write(A.UC_ARM_REG_R1, 0x9E3779B1)
        done = code.symbols["done"]
        regs = [getattr(A, f"UC_ARM_REG_R{i}") for i in range(13)] + [A.UC_ARM_REG_SP, A.UC_ARM_REG_LR, A.UC_ARM_REG_PC]
        words = lambda a, n: struct.unpack(f"<{n}I", bytes(uc.mem_read(a, 4 * n)))
        pace = pace or devicetime.Pace()
        pc, t, insns = CODE_AT, 0, 0
        while pc != done:
            rate = pace.rate(pc, words(pc, 1)[0], lambda n: uc.reg_read(regs[n]), t, words)
            uc.emu_start(pc, done, count=machine.SLICE)
            after = uc.reg_read(A.UC_ARM_REG_PC)
            n = machine.SLICE if after != done else None
            if n is None:       # the last slice: count what ran of it
                n = rounds * len(LOOPS[name].splitlines()) - insns
            insns += n
            t += round(n * rate)
            pc = after
        return t / rounds, pace

    def test_probe_loops(self):
        sizes = {"alu": 100_000, "mul": 100_000, "memh": 100_000, "mem": 2 * 1024 * 1024 // 16}
        for name, rounds in sizes.items():
            ns, _ = self.run_loop(name, rounds)
            self.assertAlmostEqual(ns, MEASURED[name], delta=0.04 * MEASURED[name], msg=name)
        ns, _ = self.run_loop("mem", 2 * 1024 * 1024 // 16, at=0xC4400000)
        self.assertAlmostEqual(ns, MEASURED["memu"], delta=0.04 * MEASURED["memu"], msg="memu")

    def test_a_walk_that_fits_the_cache_hits(self):
        """The same streaming loop over 4 KiB again and again (a quarter of the assumed data cache) stays at the hit rate."""
        pace = devicetime.Pace()
        for i in range(20):
            ns, _ = self.run_loop("memh", 2000, pace=pace)
            self.assertLess(ns, 50, msg=f"round {i}")

    def test_the_first_sample_of_a_walk_counts_as_a_hit(self):
        """A copy shorter than one slice is sampled once at most: it counts as a hit (the model's known blind spot)."""
        ns, _ = self.run_loop("mem", 1024 // 16)
        self.assertLess(ns, 50)


if __name__ == "__main__":
    unittest.main()
