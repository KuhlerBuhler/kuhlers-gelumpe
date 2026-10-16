"""Tests for vm_bench.py: the stub against the reference VM, in Unicorn without firmware.

The numbers of the opcode table are checked against data/script/contract.mjs;
the stub runs need Unicorn (tools/emu/.venv) and are skipped without it.
"""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vm_bench as vb  # noqa: E402

try:
    import unicorn  # noqa: F401
    from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_R0
except ImportError:
    unicorn = None

SIZES = (0, 1, 5, 37)
R_OFFSETS = tuple(vb.R.values())


def run_raw(variant, code, n=0, fuel=10_000, limit_ticks=10 ** 6):
    """Run arbitrary bytecode in the stub; (link, results dict) with the raw words."""
    image, sym = vb.build(variant)
    link = vb.BareLink()
    vb.BYTECODE["_test"] = code
    try:
        link.write(vb.STUB_AT, vb.with_program(image, "_test"))
    finally:
        del vb.BYTECODE["_test"]
    link.write(vb.STUB_AT, vb.head_block(limit_ticks, fuel, n) + code.ljust(vb.BC_MAX, b"\0"))
    link.execute(sym["entry"])
    return link, vb.parse_results(link.read(vb.STUB_AT, vb.VARS_OFF + vb.VARS * 4))


class FakeDevice:
    """RAM behind a write-back data cache: a write to a line the CPU has read stays in the cache, a read through
    the uncached alias shows RAM, and reading enough other memory writes the cache back."""

    def __init__(self, ack=True, cached=True):
        self.ram, self.cache, self.read_kib, self.ack, self.cached = bytearray(0x1000), {}, 0, ack, cached
        self.executes, self.lose = 0, 0

    def read(self, addr, length):
        if addr >= vb.STUB_AT + vb.ALIAS:
            a = addr - vb.ALIAS - vb.STUB_AT
            return bytes(self.ram[a:a + length])
        if addr < vb.STUB_AT:
            self.read_kib += length / 1024
            if self.read_kib >= 16:
                for a, v in self.cache.items():
                    self.ram[a] = v
                self.cache.clear()
            return bytes(length)
        a = addr - vb.STUB_AT
        for i in range(length):
            self.cache.setdefault(a + i, self.ram[a + i])
        return bytes(self.cache[a + i] for i in range(length))

    def write(self, addr, data, verify=True):
        a = addr - vb.STUB_AT
        for i, v in enumerate(data):
            if a + i in self.cache and self.cached:
                self.cache[a + i] = v
            else:
                self.ram[a + i] = v
                self.cache.pop(a + i, None)

    def execute(self, addr):
        self.executes += 1
        if not self.ack or self.executes <= self.lose:
            raise SystemExit("no answer; stopping")


class Args:
    repeat, target_ms, limit_ms, caches, evict_kib, settle, retries, retry_pause, pause = 1, 1.0, 40, True, 64, 0, 0, 0, 0


class Coherence(unittest.TestCase):
    def bench(self, **kw):
        args = type("A", (Args,), kw)
        bench = vb.Bench(FakeDevice(), None, args)
        bench.alias = True
        return bench

    def test_a_write_into_a_cached_line_reaches_ram_only_after_the_cache_is_pushed_out(self):
        bench = self.bench()
        bench.dev.read(vb.STUB_AT, 64)                      # the host's read of the original bytes
        image = bytes(range(1, 65))
        bench.put(vb.STUB_AT, image)
        self.assertNotEqual(bytes(bench.dev.ram[:64]), image, "RAM is stale while the cache holds the data")
        bench.make_coherent(image)
        self.assertEqual(bytes(bench.dev.ram[:64]), image)

    def test_without_eviction_the_stale_ram_stops_the_run(self):
        bench = self.bench(evict_kib=0)
        bench.dev.read(vb.STUB_AT, 64)
        image = bytes(range(1, 65))
        bench.put(vb.STUB_AT, image)
        with self.assertRaises(vb.StageFailed):
            bench.make_coherent(image)

    def test_nothing_to_check_without_caches(self):
        bench = self.bench(caches=False)
        bench.dev.read(vb.STUB_AT, 64)
        bench.put(vb.STUB_AT, bytes(64))
        bench.make_coherent(bytes(range(64)))               # would differ, but the emulator has no cache to ask

    def test_a_missing_ack_reports_the_progress_word(self):
        bench = self.bench()
        bench.dev.ack = False
        bench.dev.ram[vb.R["prog"]] = 2
        with self.assertRaises(vb.StageFailed) as cm:
            bench.execute(vb.STUB_AT + vb.CODE_OFF, "stage 2", probe=4)
        self.assertIn("progress word 2", str(cm.exception))
        self.assertIn("stage 2", str(cm.exception))

    def test_a_lost_ack_after_the_stub_finished_is_not_a_failure(self):
        bench = self.bench()
        bench.dev.ack = False
        bench.dev.ram[vb.R["prog"]] = 1
        bench.execute(vb.STUB_AT + vb.CODE_OFF, "stage 1", probe=1)

    def test_an_interpreter_run_that_left_its_operation_count_is_finished(self):
        bench = self.bench()
        bench.dev.ack = False
        bench.dev.ram[vb.R["ops"]] = 46
        bench.execute(vb.STUB_AT, "run")

    def test_a_stub_that_did_not_run_is_executed_again(self):
        bench = self.bench(retries=2)
        bench.dev.lose = 2
        bench.image = bytes(range(1, 65))
        bench.dev.ram[:64] = bench.image
        bench.execute(vb.STUB_AT, "stage 0", probe=5)
        self.assertEqual(bench.dev.executes, 3)

    def test_the_retries_end_in_a_failure_that_names_the_progress(self):
        bench = self.bench(retries=2)
        bench.dev.ack = False
        with self.assertRaises(vb.StageFailed) as cm:
            bench.execute(vb.STUB_AT, "stage 0", probe=5)
        self.assertIn("3 tries", str(cm.exception))
        self.assertEqual(bench.dev.executes, 3)

    def test_stale_code_in_ram_stops_a_retry(self):
        bench = self.bench(retries=1, evict_kib=0)
        bench.dev.ack = False
        bench.image = bytes(range(1, vb.CODE_OFF + 9))
        with self.assertRaises(vb.StageFailed) as cm:
            bench.execute(vb.STUB_AT, "stage 1", probe=1)
        self.assertIn("RAM never matched", str(cm.exception))
        self.assertEqual(bench.dev.executes, 1)

    def test_a_lost_write_ack_is_repeated_and_a_wrong_read_back_is_not(self):
        bench = self.bench(retries=2)
        calls = []
        real = bench.dev.write

        def flaky(addr, data, verify=True):
            calls.append(1)
            if len(calls) == 1:
                raise SystemExit("data 0xc1000000: no write ack, got ")
            real(addr, data, verify)
        bench.dev.write = flaky
        bench.put(vb.STUB_AT, bytes(8))
        self.assertEqual(len(calls), 2)

        def bad(addr, data, verify=True):
            raise SystemExit("write 0xc1000000: read back differs")
        bench.dev.write = bad
        with self.assertRaises(SystemExit):
            bench.put(vb.STUB_AT, bytes(8))

    def test_the_stage_zero_stub_stores_its_mark(self):
        code = vb.arm.assemble(vb.STAGE0, vb.STUB_AT).bytes
        self.assertLessEqual(len(code), vb.R["prog"], "the stub ends before the word it marks")




class PickTimer(unittest.TestCase):
    def rows(self, ticks, prd=(23999, 0x16E35FF, 0x124F7, 0x8F0D17F)):
        return [{"base": b, "hz": hz, "name": n, "prd": p, "ticks": t, "tgcr": 5, "tcr": 0x80}
                for (b, hz, n), p, t in zip(vb.TIMER_LIST, prd, ticks)]

    def test_takes_the_fastest_counter_that_runs_and_wraps_late(self):
        best, notes = vb.pick_timer(self.rows((3997, 0, 24985, 24985)))
        self.assertEqual(best["base"], 0x01F0D000)
        self.assertEqual(notes, [])

    def test_a_counter_that_does_not_run_is_skipped(self):
        best, _ = vb.pick_timer(self.rows((3997, 0, 24985, 0)))
        self.assertIsNone(best, "timer 2 wraps every 0.5 ms and timer 0 every 1 ms: both too short")

    def test_a_clock_far_from_its_assumed_rate_is_replaced_by_the_measured_one(self):
        best, notes = vb.pick_timer(self.rows((4000, 0, 0, 12000)))
        self.assertAlmostEqual(best["hz_used"], 72e6)
        self.assertEqual(len(notes), 1)

    def test_select_timer_sets_the_tick_length(self):
        old = vb.TIMER, vb.TICK_NS
        try:
            vb.select_timer(0x01C20000, 24e6)
            self.assertAlmostEqual(vb.TICK_NS, 1000 / 24)
            self.assertEqual(vb.TIMER, 0x01C20000)
        finally:
            vb.TIMER, vb.TICK_NS = old


class Where(unittest.TestCase):
    def head(self, **kw):
        return {k: kw.get(k, 0) for k in vb.R}

    def test_interpreter_stages(self):
        self.assertIn("never started", vb.where(self.head(), None))
        self.assertIn("before the timer registers", vb.where(self.head(cpsr=0x53), None))
        self.assertIn("inside the interpreter", vb.where(self.head(cpsr=0x53, prd=5, tcr=0x80), None))
        self.assertIn("only the ack is missing", vb.where(self.head(cpsr=0x53, prd=5, tcr=0x80, ops=302), None))


class Tables(unittest.TestCase):
    def test_contract(self):
        problems = vb.check_contract()
        if problems is None:
            self.skipTest("data/script/contract.mjs not found")
        self.assertEqual(problems, [])

    def test_images_fit_the_stub_area(self):
        for variant in ("lean", "checked"):
            image, sym = vb.build(variant)
            self.assertLessEqual(len(image), vb.STUB_SIZE, variant)
            self.assertEqual(sym["entry"], vb.STUB_AT + vb.CODE_OFF)

    def test_every_program_fits_its_slot_and_ends(self):
        for name, code in vb.BYTECODE.items():
            self.assertLessEqual(len(code), vb.BC_MAX, name)
            ref = vb.reference(code, 5)
            self.assertGreater(ref["ops"], 0, name)

    def test_head_fields_do_not_overlap(self):
        spans = [(off, off + 4) for off in (*R_OFFSETS, vb.IN_LIMIT, vb.IN_LIMIT + 4, vb.IN_N)]
        self.assertEqual(len(set(spans)), len(spans))
        self.assertTrue(all(end <= vb.HEAD_LEN for _, end in spans))

    def test_probe_image_fits_and_starts_at_the_interpreter_entry(self):
        image, sym = vb.build_probes()
        self.assertLessEqual(len(image), vb.STUB_SIZE)
        self.assertEqual(sym["p_ret"], vb.STUB_AT + vb.CODE_OFF)
        self.assertEqual(image[:vb.CODE_OFF], vb.zero_head() + bytes(vb.CODE_OFF - vb.HEAD_LEN))

    def test_counting_loop_reference(self):
        for n in SIZES:
            ref = vb.reference(vb.BYTECODE["count"], n)
            self.assertEqual(ref["vars"][1], n)
            self.assertEqual(ref["ops"], 9 * n + 5)


@unittest.skipUnless(unicorn, "Unicorn not installed")
class Stub(unittest.TestCase):
    def test_matches_the_reference(self):
        for variant in ("lean", "checked"):
            for name, code in vb.BYTECODE.items():
                for n in SIZES:
                    ref = vb.reference(code, n)
                    fuel = ref["cost"] if variant == "checked" else ref["ops"] + 1
                    _, got = run_raw(variant, code, n, fuel=fuel)
                    with self.subTest(variant=variant, program=name, n=n):
                        self.assertEqual(got["err"], 0)
                        self.assertEqual(got["vars"], ref["vars"])
                        self.assertEqual(got["ops"], ref["ops"])

    def run_probe(self, name):
        image, sym = vb.build_probes()
        link = vb.BareLink()
        link.write(vb.STUB_AT, image)
        link.execute(sym[name])
        return link, vb.parse_head(link.read(vb.STUB_AT, vb.HEAD_LEN))

    def test_trampoline_reaches_the_entry_from_the_stub_start(self):
        image, sym = vb.build("lean")
        link = vb.BareLink()
        link.write(vb.STUB_AT, vb.with_program(image, "count"))
        link.write(vb.STUB_AT, vb.head_block(10 ** 6, 10 ** 4, 5))
        link.execute(vb.STUB_AT)
        got = vb.parse_results(link.read(vb.STUB_AT, vb.VARS_OFF + vb.VARS * 4))
        self.assertEqual((got["err"], got["ops"]), (0, 9 * 5 + 5))
        self.assertEqual(link.read(vb.STUB_AT, 4), vb.TRAMPOLINE)

    def test_probe_one_leaves_its_mark(self):
        _, head = self.run_probe("p_ret")
        self.assertEqual(head["prog"], 1)

    def test_probe_two_reads_every_timer_and_finishes(self):
        link, head = self.run_probe("p_timer")
        self.assertEqual(head["prog"], 4)
        self.assertNotEqual(head["cpsr"], 0)
        rows = vb.parse_timers(link.read(vb.STUB_AT, vb.PROBE_DATA + 20 * len(vb.TIMER_LIST)))
        by = {r["base"]: r for r in rows}
        self.assertEqual(by[0x01F0D000]["prd"] + 1, 150_000_000)
        self.assertEqual(by[0x01C21000]["ticks"], 0, "the watchdog-mode timer stays at 0")
        for base in (0x01C20000, 0x01F0C000, 0x01F0D000):
            self.assertGreater(by[base]["ticks"], 0, hex(base))
        best, _ = vb.pick_timer(rows)
        self.assertEqual(best["base"], 0x01F0D000)

    def test_caller_state_survives(self):
        image, sym = vb.build("checked")
        link = vb.BareLink()
        link.write(vb.STUB_AT, vb.with_program(image, "mix"))
        link.write(vb.STUB_AT, vb.head_block(10 ** 6, 10 ** 5, 20))
        for r in range(4, 12):
            link.uc.reg_write(UC_ARM_REG_R0 + r, 0x1000 + r)
        cpsr = link.uc.reg_read(UC_ARM_REG_CPSR)
        link.execute(sym["entry"])
        self.assertEqual([link.uc.reg_read(UC_ARM_REG_R0 + r) for r in range(4, 12)], [0x1000 + r for r in range(4, 12)])
        self.assertEqual(link.uc.reg_read(UC_ARM_REG_CPSR) & 0xFF, cpsr & 0xFF, "mode and interrupt bits untouched")
        self.assertEqual(link.uc.reg_read(UC_ARM_REG_R0), 0, "return value 0 sends the ack to both ports")

    def test_only_results_variables_and_stack_are_written(self):
        for variant in ("lean", "checked"):
            image, sym = vb.build(variant)
            link = vb.BareLink()
            link.write(vb.STUB_AT, vb.with_program(image, "mix") + bytes(0x1000 - len(image)))
            link.write(vb.STUB_AT, vb.head_block(10 ** 6, 10 ** 5, 20))
            before = link.read(vb.STUB_AT, 0x1000)
            link.execute(sym["entry"])
            after = link.read(vb.STUB_AT, 0x1000)
            changed = [i for i in range(0x1000) if before[i] != after[i]]
            self.assertTrue(changed)
            self.assertTrue(all(i < vb.HEAD_LEN or vb.VARS_OFF <= i < vb.CODE_OFF for i in changed),
                            f"{variant}: code or bytecode changed")

    def test_fuel_stops_an_endless_loop(self):
        loop = vb.assemble_code(["L:", ("JMP", "L")])
        for variant in ("lean", "checked"):
            _, got = run_raw(variant, loop, fuel=500)
            self.assertEqual(got["err"], 1, variant)

    def test_time_limit_stops_the_checked_stub(self):
        loop = vb.assemble_code(["L:", ("JMP", "L")])
        _, got = run_raw("checked", loop, fuel=10 ** 9, limit_ticks=20)
        self.assertEqual(got["err"], 7)

    def test_array_bounds(self):
        for index in (4, 100):
            code = vb.assemble_code([("PUSHB", index), ("ALOAD", 8, 4), ("HALT",)])
            for variant in ("lean", "checked"):
                _, got = run_raw(variant, code, fuel=500)
                self.assertEqual(got["err"], 3, f"{variant} index {index}")

    def test_unimplemented_opcode(self):
        for variant in ("lean", "checked"):
            _, got = run_raw(variant, bytes([13]), fuel=500)
            self.assertEqual(got["err"], 2, variant)
        _, got = run_raw("checked", bytes([200]), fuel=500)
        self.assertEqual(got["err"], 2)

    def test_instructions_per_operation_match_the_research(self):
        # 9.6 instructions per operation for the prototype (research 2.3), plus the 16-bit operands of format 2.
        link, _ = run_raw("lean", vb.BYTECODE["count"], n=500, fuel=10 ** 5)
        per_op = link.last_insns / (9 * 500 + 5)
        self.assertTrue(9 <= per_op <= 10.5, per_op)


class Window(unittest.TestCase):
    @unittest.skipUnless(unicorn, "Unicorn not installed")
    def test_bench_refuses_writes_outside_the_stub_area_and_away_from_its_start(self):
        image, sym = vb.build("lean")
        bench = vb.Bench(vb.BareLink(), sym, Args)
        for addr, size in ((vb.STUB_AT + vb.STUB_SIZE, 4), (vb.STUB_AT - 4, 4), (vb.STUB_AT + vb.STUB_SIZE - 2, 4),
                           (vb.STUB_AT + 0x100, 4)):
            with self.assertRaises(SystemExit):
                bench.put(addr, bytes(size))


if __name__ == "__main__":
    unittest.main()
