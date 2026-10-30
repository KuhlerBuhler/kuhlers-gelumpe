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
PART_BASE, VOICE_BASE, VOICE_FLAGS = 0xC069EA44, 0xC06916A0, 0xC1004000
MANAGER, TRANSPORT_OBJECT = 0xC1008000, 0xC1009000


def word(n):
    return struct.pack("<I", n & 0xFFFFFFFF)


class Swap:
    def __init__(self):
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.uc.mem_map(0xC0000000, 0x02000000)
        self.uc.mem_map(0xC2700000, 0x00200000)
        self.uc.mem_map(p.SIG, 0x1000)
        sections, self.sym = p.build_code(SCREENS)
        for at, data in sections:
            self.uc.mem_write(at, data)
        self.uc.mem_write(TRAP, word(0xE1A00000))
        # stand-ins of our own for the firmware routines the tested paths call
        stubs = {F["REPEATS"]: "ldr r3, =0x3B06\nldrb r0, [r0, r3]\nbx lr",
                 F["SWITCH"]: "bx lr",
                 0xC0079A78: "pop {r4, r5, r6, pc}",
                 F["DELETE"]: "bx lr",
                 0xC009AF20: f"ldr r1, ={PART_BASE}\nmov r2, #0x148\nmla r0, r2, r0, r1\nbx lr\n.pool",
                 0xC009115C: f"ldr r1, ={VOICE_FLAGS}\nldrb r0, [r1, r0]\nbx lr\n.pool",
                 F["TRANSPORT"]: f"ldr r0, ={TRANSPORT_OBJECT}\nbx lr\n.pool"}
        for at, text in stubs.items():
            self.uc.mem_write(at, arm.assemble(text, origin=at).bytes)
        self.calls = []
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.note, begin=F["SWITCH"], end=F["SWITCH"])
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.note, begin=F["DELETE"], end=F["DELETE"])
        self.uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
        self.uc.mem_write(p.sample_owner.STARTED, word(1))
        self.uc.mem_write(p.FILE_OWNER, bytes(20))
        self.set_state("MODE", 1)
        self.set_state("GEN", 7)
        self.uc.mem_write(p.STATE + p.FAILED, bytes(128))
        self.uc.mem_write(SCREENS, word(MANAGER))
        self.uc.mem_write(MANAGER + 0x2C, word(1))

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

    def owner(self):
        return struct.unpack("<4I", self.uc.mem_read(p.FILE_OWNER, 16))

    def read_call(self, name, *args, regs=None):
        assert self.call("owner_acquire", p.sample_owner.READ) == 0
        token = self.uc.reg_read(R.UC_ARM_REG_R1)
        try:
            return self.call(name, *args, regs={**(regs or {}), R.UC_ARM_REG_R10: token})
        finally:
            assert self.call("owner_release", token) == 0

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
        if active and in_file:
            self.call("mark_clean", slot)     # the row as the loader or the swap put it there

    def parts(self, pattern, samples):
        for i in range(16):
            self.uc.mem_write(F["BANK"] + pattern * 0x4000 + 0x808 + i * 0x330,
                              struct.pack("<H", samples[i] if i < len(samples) else 0xFFFF))


class CacheRanges(unittest.TestCase):
    def test_cache_stays_in_measured_free_ram_and_excludes_the_task_stack(self):
        for lo, hi in ((p.ARENA_L, p.ARENA_L_END), (p.ARENA_U, p.ARENA_U_END)):
            self.assertGreaterEqual(lo, 0xC1010000)
            self.assertLess(lo, hi)
            self.assertLessEqual(hi, 0xC4000000)
            self.assertTrue(hi <= 0xC274E000 or lo >= 0xC274F000)


class AllocationBounds(unittest.TestCase):
    def prepared(self, length):
        s = Swap()
        for name, value in dict(P_LEN=length, P_BITS=16, CGEN=7, CPTR=p.ARENA_U).items():
            s.set_state(name, value)
        s.uc.mem_write(s.sym["parse"], arm.assemble("mov r0, #0\nbx lr", origin=s.sym["parse"]).bytes)
        return s

    def test_prefetch_rejects_lengths_that_cannot_fit_the_dsp_without_copying(self):
        for length in (0x40000000, 0xFFF00000, 0xFFFFFFF0, 1):
            with self.subTest(length=hex(length)):
                s = self.prepared(length)
                writes = []
                s.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, lambda uc, access, at, size, value, data: writes.append(at),
                              begin=p.ARENA_U, end=p.ARENA_U + 0x49F)
                s.read_call("start_prepare", 601)
                self.assertEqual(s.state("J_STATE"), 0)
                self.assertEqual(writes, [])

    def test_card_install_rejects_lengths_before_placement(self):
        for length in (0x40000000, 0xFFF00000, 0xFFFFFFF0, 1):
            with self.subTest(length=hex(length)):
                s = self.prepared(length)
                s.slot(600, active=True, base=F["DSP_MIN"], length=4096)
                s.uc.mem_write(p.STATE + p.PROT, struct.pack("<32H", 600, *([0xFFFF] * 31)))
                s.uc.mem_write(s.sym["place"], arm.assemble(f"ldr r0, ={F['DSP_MIN']}\nbx lr\n.pool",
                                                           origin=s.sym["place"]).bytes)
                entered = []
                s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: entered.append(True),
                              begin=s.sym["place"], end=s.sym["place"])
                s.read_call("start_install", 601)
                self.assertEqual(s.state("J_STATE"), 0)
                self.assertEqual(entered, [])

    def test_cached_install_validates_its_length_before_placement(self):
        s = self.prepared(32)
        s.uc.mem_write(p.DIR + 601 * 16, struct.pack("<4I", p.ARENA_U, 0xFFFFFFF0, 0, 7))
        s.uc.mem_write(s.sym["place"], arm.assemble(f"ldr r0, ={F['DSP_MIN']}\nbx lr\n.pool",
                                                   origin=s.sym["place"]).bytes)
        s.read_call("start_install", 601)
        self.assertEqual(s.state("J_STATE"), 0)

    def test_cache_cursor_below_the_arena_cannot_start_a_copy(self):
        for pointer in (0, p.ARENA_L - 32):
            with self.subTest(pointer=hex(pointer)):
                s = self.prepared(32)
                s.uc.mem_map(0, 0x1000)
                s.set_state("CPTR", pointer)
                s.read_call("start_prepare", 601)
                self.assertEqual(s.state("J_STATE"), 0)

    def test_temporary_space_shortage_can_be_retried_without_a_failed_slot(self):
        s = self.prepared(32)
        at = s.sym["place"]
        s.uc.mem_write(at, arm.assemble("mov r0, #0\nbx lr", origin=at).bytes)
        s.read_call("start_install", 601)
        failed_word = p.STATE + p.FAILED + (601 >> 5) * 4
        self.assertEqual(s.state("J_STATE"), 0)
        self.assertEqual(s.u32(failed_word) & (1 << (601 & 31)), 0)
        s.uc.mem_write(at, arm.assemble(f"ldr r0, ={F['DSP_MIN']}\nbx lr\n.pool", origin=at).bytes)
        s.uc.ctl_flush_tb()
        s.read_call("start_install", 601)
        self.assertEqual(s.state("J_STATE"), 1)

    def test_sampling_started_during_placement_cannot_reserve_a_dsp_job(self):
        s = self.prepared(32)
        at = s.sym["place"]
        source = f"ldr r1, ={TRANSPORT_OBJECT + 0x308}\nmov r2, #11\nstr r2, [r1]\nldr r0, ={F['DSP_MIN']}\nbx lr\n.pool"
        s.uc.mem_write(at, arm.assemble(source, origin=at).bytes)
        cursor = s.u32(F["CURSOR"])
        s.uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
        s.read_call("start_install", 601)
        self.assertEqual(s.state("J_STATE"), 0)
        self.assertEqual(s.u32(F["CURSOR"]), cursor)
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80, 0)


class StepContext(unittest.TestCase):
    def setup_step(self, *, screen=1, window=0, transport=0, sampling=0):
        s = Swap()
        s.uc.mem_map(F["TIMER"], 0x1000)
        s.uc.mem_write(F["PLAYER"], arm.assemble("ldr r0, =0xC100A000\nbx lr\n.pool", origin=F["PLAYER"]).bytes)
        s.uc.mem_write(s.sym["chunk"], arm.assemble("mov r0, #2\nbx lr", origin=s.sym["chunk"]).bytes)
        for field, value in dict(J_STATE=1, J_STAGED=32, SESSION=1, CFILL=1, WASPLAY=1, LASTRUN=0).items():
            s.set_state(field, value)
        s.uc.mem_write(MANAGER + 0x2C, word(screen))
        s.uc.mem_write(MANAGER + 0x24, word(window))
        s.uc.mem_write(TRANSPORT_OBJECT + 0x308, word(transport))
        s.uc.mem_write(TRANSPORT_OBJECT + 0x312, bytes([sampling]))
        s.entered = []
        for address, name in ((F["PLAYER"], "player"), (s.sym["chunk"], "chunk")):
            s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, at, size, label: s.entered.append(label),
                          name, begin=address, end=address)
        return s

    def test_a_writer_defers_the_whole_step_without_invalidating_its_job(self):
        s = self.setup_step()
        self.assertEqual(s.call("owner_acquire", p.sample_owner.WRITE), 0)
        before = s.owner()
        s.call("ss_step")
        self.assertEqual(s.entered, [])
        self.assertEqual(s.owner(), before)
        self.assertEqual(s.state("J_STAGED"), 32)
        self.assertEqual(s.state("GEN"), 7)

    def test_a_step_releases_its_reader_after_the_last_chunk(self):
        s = self.setup_step()
        s.call("ss_step")
        self.assertEqual(s.entered, ["player", "chunk"])
        self.assertEqual(s.owner(), (0, 1, 0, 0))

    def test_a_card_error_blocks_another_step_until_checked_recovery(self):
        s = self.setup_step()
        s.uc.mem_write(s.sym["chunk"], arm.assemble(
            f"mov r0, #2\nstr r0, [r11, #{p.OFF['MODE']}]\nbx lr",
            origin=s.sym["chunk"]).bytes)
        s.call("ss_step")
        self.assertEqual(s.owner(), (0, 1, 1, 0))
        s.set_state("MODE", 1)
        s.entered.clear()
        s.call("ss_step")
        self.assertEqual(s.entered, [])

    def test_other_modes_cancel_staged_work_before_any_dsp_or_card_step(self):
        for values in (dict(screen=37), dict(window=1), dict(transport=11), dict(transport=1, sampling=1)):
            with self.subTest(**values):
                s = self.setup_step(**values)
                s.call("ss_step")
                self.assertEqual(s.entered, [])
                self.assertEqual(s.state("GEN"), 8)
                for field in ("J_STATE", "J_STAGED", "SESSION", "CFILL"):
                    self.assertEqual(s.state(field), 0, field)
                s.call("ss_step")
                self.assertEqual(s.state("GEN"), 8, "an already paused step does not advance the generation again")

    def test_pausing_preserves_the_last_observed_play_state(self):
        s = self.setup_step(screen=37, transport=1)
        s.call("ss_step")
        self.assertEqual(s.state("WASPLAY"), 1, "returning from a menu must not invent a new PLAY edge")

    def test_a_mode_change_between_chunks_pauses_before_the_next_chunk(self):
        s = self.setup_step()
        s.uc.mem_write(s.sym["chunk"], arm.assemble("mov r0, #0\nbx lr", origin=s.sym["chunk"]).bytes)

        def change_mode(uc, at, size, _):
            uc.mem_write(MANAGER + 0x2C, word(37))

        def stop_second_chunk(uc, at, size, _):
            if s.entered.count("chunk") > 1:
                uc.reg_write(R.UC_ARM_REG_PC, s.sym["st_ret"])

        s.uc.hook_add(unicorn.UC_HOOK_CODE, stop_second_chunk, begin=s.sym["chunk"], end=s.sym["chunk"])
        s.uc.hook_add(unicorn.UC_HOOK_CODE, change_mode, begin=s.sym["since"], end=s.sym["since"])
        s.call("ss_step")
        self.assertEqual(s.entered, ["player", "chunk"])
        self.assertEqual(s.state("GEN"), 8)
        self.assertEqual(s.state("J_STATE"), 0)

    def test_main_screen_allows_demand_loading_in_the_six_sequencer_states(self):
        for transport in range(6):
            with self.subTest(transport=transport):
                s = self.setup_step(transport=transport)
                s.call("ss_step")
                self.assertEqual(s.entered, ["player", "chunk"])
                self.assertEqual(s.state("GEN"), 7)


class BootOwnership(unittest.TestCase):
    def library(self, result=0, *, checked=False, close_status=None, held=False):
        s = Swap()
        s.uc.mem_write(p.FILE_OWNER, p.sample_owner.INITIAL + bytes(4))
        panel = 0xC100E000
        s.uc.mem_write(F["PANEL"], word(panel))
        s.uc.mem_write(panel + 0x18, word(p.KILL if held else 0))
        entry = 0xC100F000
        s.uc.mem_write(entry, arm.assemble(
            f"push {{r4-r11, lr}}\nb {s.sym['ss_library']}", origin=entry).bytes)
        body = 0xC00364F8
        code = f"sub sp, sp, #4\nmov r4, #{result}\n"
        if checked:
            code += f"ldr r0, ={p.BOOT_LEASE}\nldr r0, [r0]\nbl {s.sym['owner_resolve']}\n"
        if close_status is not None:
            s.uc.mem_write(F["F_CLOSE"], arm.assemble(
                f"mov r0, #{close_status}\nbx lr", origin=F["F_CLOSE"]).bytes)
            code += f"bl {s.sym['ss_library_close']}\ncmp r0, #0\nmovne r4, #4\n"
        code += f"b {s.sym['ss_library_finish']}\n.pool"
        s.uc.mem_write(body, arm.assemble(code, origin=body).bytes)
        tail = 0xC0036764
        s.uc.mem_write(tail, arm.assemble(
            "add sp, sp, #0x840\nadd sp, sp, #4\npop {r4-r11, pc}", origin=tail).bytes)
        return s, entry

    def test_boot_releases_a_checked_catalogue(self):
        s, entry = self.library()
        self.assertEqual(s.call(entry), 0)
        self.assertEqual(s.owner(), (0, 1, 0, 0))
        self.assertEqual(s.u32(p.BOOT_LEASE), 0)

    def test_boot_initializes_native_dsp_recovery_before_entering_the_loader(self):
        s, entry = self.library()
        self.assertTrue(hasattr(p, 'NATIVE_SCOPE'))
        s.uc.mem_write(p.NATIVE_SCOPE, word(0xFFFFFFFF))
        s.set_state("TSTATE", 0xFFFFFFFF)
        observed = []
        s.uc.hook_add(unicorn.UC_HOOK_CODE,
                      lambda *_: observed.append((s.u32(p.NATIVE_SCOPE), s.state("TSTATE"))),
                      begin=0xC00364F8, end=0xC00364F8)
        self.assertEqual(s.call(entry), 0)
        self.assertEqual(observed, [(0, 0)])

    def test_a_library_reload_does_not_discard_another_native_dsp_scope(self):
        s, entry = self.library()
        self.assertTrue(hasattr(p, 'NATIVE_SCOPE'))
        active = 0xC100F800
        s.uc.mem_write(p.NATIVE_SCOPE, word(active))
        self.assertEqual(s.call(entry), 0)
        self.assertEqual(s.u32(p.NATIVE_SCOPE), active)
        self.assertEqual(s.state("TSTATE"), 0)

    def test_cold_exit_does_not_enable_native_dsp_recovery(self):
        s, entry = self.library(held=True)
        s.uc.mem_write(p.NATIVE_SCOPE, word(0xFFFFFFFF))
        s.set_state("TSTATE", 0xFFFFFFFF)
        self.assertEqual(s.call(entry), 0)
        self.assertEqual(s.u32(p.NATIVE_SCOPE), 0xFFFFFFFF)
        self.assertEqual(s.state("TSTATE"), 0xFFFFFFFF)

    def test_failed_boot_leaves_the_catalogue_uncertain(self):
        s, entry = self.library(4)
        self.assertEqual(s.call(entry), 4)
        self.assertEqual(s.owner(), (0, 1, 1, 0))
        self.assertEqual(s.u32(p.BOOT_LEASE), 0)

    def test_an_isolated_bad_record_does_not_reject_a_checked_catalogue(self):
        s, entry = self.library(4, checked=True)
        self.assertEqual(s.call(entry), 4)
        self.assertEqual(s.owner(), (0, 1, 0, 0))

    def test_a_failed_native_close_invalidates_a_previously_checked_catalogue(self):
        s, entry = self.library(checked=True, close_status=1)
        self.assertEqual(s.call(entry), 4)
        self.assertEqual(s.owner(), (0, 1, 1, 0))
        self.assertEqual(s.u32(p.BOOT_LEASE), 0)

    def test_a_competing_recovery_cannot_enter_the_native_loader(self):
        s, entry = self.library()
        self.assertEqual(s.call("owner_acquire", p.sample_owner.RECOVER), 0)
        before = s.owner()
        entered = []
        s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: entered.append(True), begin=0xC00364F8, end=0xC00364F8)
        self.assertEqual(s.call(entry), 4)
        self.assertEqual(s.owner(), before)
        self.assertEqual(entered, [])


class LibraryBypass(unittest.TestCase):
    def loader(self, *, held=False, recovery_error=0, fault=0, close_error=None, release_during_open=False):
        s = Swap()
        path, panel = 0xC100A000, 0xC100B000
        s.uc.mem_write(path, b"SD:own/Sample/e2sSample.all\0")
        s.uc.mem_write(F["PANEL"], word(panel))
        s.uc.mem_write(panel + 0x18, word(p.KILL if held else 0))
        s.set_state("FILE", 1 if close_error is not None else 0)
        s.set_state("TSTATE", fault)
        events = []
        s.uc.mem_write(s.sym["store_recover"], arm.assemble(
            f"mov r0, #{recovery_error}\nbx lr", origin=s.sym["store_recover"]).bytes)
        s.uc.mem_write(F["F_OPEN"], arm.assemble("mov r0, #0\nbx lr", origin=F["F_OPEN"]).bytes)
        s.uc.mem_write(p.FIL + 12, word(p.CAP_DEFAULT + 0x2000))
        if close_error is not None:
            s.uc.mem_write(F["F_CLOSE"], arm.assemble(
                f"mov r0, #{close_error}\nbx lr", origin=F["F_CLOSE"]).bytes)
        for address, name in ((s.sym["store_recover"], "recover"), (F["F_OPEN"], "open"),
                              (F["F_CLOSE"], "close")):
            s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, at, size, tag: events.append(tag),
                          name, begin=address, end=address)
        if release_during_open:
            s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: s.uc.mem_write(panel + 0x18, word(0)),
                          begin=F["F_OPEN"], end=F["F_OPEN"])
        result = s.call("ss_fopen", p.FIL, path, 1)
        return s, result, events

    def test_exit_skips_a_failing_recovery_and_opens_natively(self):
        s, result, events = self.loader(held=True, recovery_error=1)
        self.assertEqual(result, 0)
        self.assertEqual(events, ["open"])
        self.assertEqual(s.state("MODE"), 0)

    def test_exit_bypass_remains_off_when_the_key_is_released_during_open(self):
        s, result, events = self.loader(held=True, recovery_error=1, release_during_open=True)
        self.assertEqual(result, 0)
        self.assertEqual(events, ["open"])
        self.assertEqual(s.state("MODE"), 0)

    def test_normal_boot_recovers_before_open_and_refuses_a_recovery_error(self):
        # 1: the journal was refused before anything was written, the index is untouched and the file loads as it is.
        # 3: writing the recovered index failed, the index is uncertain and the load is refused.
        for error in (0, 1, 3):
            with self.subTest(error=error):
                s, result, events = self.loader(recovery_error=error)
                refused = error > 1
                self.assertEqual(result, 1 if refused else 0)
                self.assertEqual(events, ["recover"] if refused else ["recover", "open"])
                self.assertEqual(s.state("MODE"), 2 if refused else 1)

    def test_exit_does_not_clear_a_transport_fault(self):
        s, result, events = self.loader(held=True, fault=1)
        self.assertEqual(result, 1)
        self.assertEqual(events, [])
        self.assertEqual(s.state("MODE"), 2)
        self.assertEqual(s.state("TSTATE"), 1)

    def test_exit_requires_a_successful_existing_reader_close(self):
        for error in (0, 1):
            with self.subTest(error=error):
                s, result, events = self.loader(held=True, close_error=error)
                self.assertEqual(result, error)
                self.assertEqual(events, ["close"] if error else ["close", "open"])
                self.assertEqual(s.state("MODE"), 2 if error else 0)
                self.assertEqual(s.state("FILE"), 2 if error else 0)


class SampleChoice(unittest.TestCase):
    def test_the_osc_iterator_accepts_an_indexed_unloaded_user_slot(self):
        s = Swap()
        self.assertIn('ss_choice', s.sym, 'indexed samples need an OSC eligibility hook')
        s.slot(601, active=False)
        at = 0xC004E3CC
        s.uc.mem_write(at, arm.assemble('mov r0, #0\nbx lr', origin=at).bytes)
        self.assertEqual(s.call('ss_choice', 601, regs={R.UC_ARM_REG_R4: 601}), 1)

    def test_other_modes_factory_empty_and_out_of_range_choices_keep_native_results(self):
        s = Swap()
        self.assertIn('ss_choice', s.sym)
        for mode in (0, 1, 2, 0xFFFFFFFF):
            for slot in (499, 500, 998, 999):
                for indexed in (False, True):
                    for native in (0, 1):
                        with self.subTest(mode=mode, slot=slot, indexed=indexed, native=native):
                            s.set_state('MODE', mode)
                            s.slot(slot, active=False, in_file=indexed)
                            at = 0xC004E3CC
                            s.uc.mem_write(at, arm.assemble(f'mov r0, #{native}\nbx lr', origin=at).bytes)
                            s.uc.ctl_flush_tb()
                            registers = {R.UC_ARM_REG_R4: slot, R.UC_ARM_REG_R5: 777, R.UC_ARM_REG_R6: 0xFFFFFFFF}
                            expected = int(bool(native) or (mode == 1 and 500 <= slot <= 998 and indexed))
                            self.assertEqual(s.call('ss_choice', slot, regs=registers), expected)
                            for register, value in registers.items():
                                self.assertEqual(s.uc.reg_read(register), value)
                            self.assertEqual(s.state('MODE'), mode)
                            self.assertEqual(s.state('GEN'), 7)


class PartPublication(unittest.TestCase):
    def setup_part(self, target=601):
        s = Swap()
        s.slot(600, base=F["DSP_MIN"], length=0x100)
        s.slot(601, active=False)
        record = 0xC100C000
        s.uc.mem_write(PART_BASE + 8, word(record))
        s.uc.mem_write(record + 8, struct.pack("<H", target))
        s.uc.mem_write(PART_BASE + 0x34, struct.pack("<H", 600))
        return s, record

    def test_an_indexed_unloaded_sample_cannot_replace_the_actual_part(self):
        s, record = self.setup_part()
        self.assertEqual(s.call("part_ready", PART_BASE), 0)
        for name, continuation in (("ss_part_update", 0xC009A000), ("ss_part_bind", 0xC0099D8C)):
            with self.subTest(entry=name):
                body = "pop {r3, r4, r5, lr}\nbx lr" if name == "ss_part_update" else "mov r0, #0\nbx lr"
                s.uc.mem_write(continuation, arm.assemble(body, origin=continuation).bytes)
                entered = []
                s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *args: entered.append(True), begin=continuation, end=continuation)
                self.assertEqual(s.call(name, PART_BASE), PART_BASE)
                self.assertEqual(entered, [])
                self.assertEqual(s.u32(PART_BASE + 0x34) & 0xFFFF, 600)

    def test_resident_empty_and_factory_selections_keep_native_behavior(self):
        for target, active, indexed in ((601, True, True), (601, False, False), (400, False, False), (0xFFFF, False, False)):
            with self.subTest(target=target, active=active, indexed=indexed):
                s, record = self.setup_part(target)
                if target == 601:
                    s.slot(601, active=active, in_file=indexed)
                self.assertEqual(s.call("part_ready", PART_BASE), 1)

    def test_a_transport_fault_blocks_even_a_resident_target(self):
        s, record = self.setup_part(600)
        s.set_state("TSTATE", 1)
        self.assertEqual(s.call("part_ready", PART_BASE), 0)
        s.set_state("MODE", 2)
        self.assertEqual(s.call("part_ready", PART_BASE), 0)
        s.set_state("MODE", 0)
        self.assertEqual(s.call("part_ready", PART_BASE), 1)

    def test_card_fault_keeps_safe_native_bindings_but_a_dsp_fault_blocks_them(self):
        for mode in (1, 2):
            for fault in (0, 1):
                for target in (400, 600, 601, 0xFFFF):
                    for name, continuation in (("ss_part_update", 0xC009A000), ("ss_part_bind", 0xC0099D8C)):
                        with self.subTest(mode=mode, fault=fault, target=target, entry=name):
                            s, _ = self.setup_part(target)
                            s.set_state("MODE", mode)
                            s.set_state("TSTATE", fault)
                            body = "pop {r3, r4, r5, lr}\nbx lr" if name == "ss_part_update" else "bx lr"
                            s.uc.mem_write(continuation, arm.assemble(body, origin=continuation).bytes)
                            entered = []
                            s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: entered.append(True),
                                          begin=continuation, end=continuation)
                            s.call(name, PART_BASE)
                            # a latched fault holds back indexed user samples only: factory and empty choices still bind
                            indexed = 500 <= target <= p.LAST_USER
                            self.assertEqual(bool(entered), target != 601 and (fault == 0 or not indexed))

    def test_successful_publication_refreshes_only_parts_requesting_that_slot(self):
        s, record = self.setup_part()
        s.slot(601, active=True)
        s.uc.mem_write(PART_BASE + 0x148 + 8, word(record + 0x100))
        s.uc.mem_write(record + 0x108, struct.pack("<H", 600))
        called = []
        update = 0xC0099FFC
        s.uc.mem_write(update, arm.assemble("bx lr", origin=update).bytes)
        s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *args: called.append(uc.reg_read(R.UC_ARM_REG_R0)), begin=update, end=update)
        s.call("apply_ready_parts", 601)
        self.assertEqual(called, [PART_BASE])


class Resident(unittest.TestCase):
    def test_the_actual_part_keeps_its_sample_when_the_requested_sample_differs(self):
        s = Swap()
        s.slot(600, base=F["DSP_MIN"], length=0x100)
        s.slot(601, base=F["DSP_MIN"] + 0x100, length=0x100)
        s.uc.mem_write(p.STATE + p.PROT, struct.pack("<32H", 601, *([0xFFFF] * 31)))
        s.uc.mem_write(PART_BASE + 0x34, struct.pack("<H", 600))
        self.assertEqual(s.call("victim"), 0)
        s.uc.mem_write(PART_BASE + 0x34, struct.pack("<H", 0xFFFF))
        self.assertEqual(s.call("victim"), 600)

    def test_a_voice_protects_its_cached_import_after_the_name_has_changed(self):
        s = Swap()
        s.slot(600, base=F["DSP_MIN"], length=0x100)
        s.slot(601, base=F["DSP_MIN"] + 0x100, length=0x100)
        self.alias(s, 602, 650 - 50, 600)
        s.call("mark_clean", 602)            # the alias as the file loaded it
        s.uc.mem_write(F["NAMES"] + 600 * 32 + 30, struct.pack("<H", 651))
        s.uc.mem_write(p.STATE + p.PROT, struct.pack("<32H", 601, *([0xFFFF] * 31)))
        s.uc.mem_write(PART_BASE + 0x34, struct.pack("<H", 601))
        s.uc.mem_write(VOICE_FLAGS, b"\1")
        s.uc.mem_write(VOICE_BASE + 4, word(PART_BASE))
        s.uc.mem_write(VOICE_BASE + 0x3A, struct.pack("<H", 600))
        s.uc.mem_write(VOICE_BASE + 0x40, struct.pack("<H", 650))
        self.assertEqual(s.call("victim"), 0)
        s.uc.mem_write(VOICE_FLAGS, b"\0")
        self.assertEqual(s.call("victim"), 602, "a stale part pointer does not keep a completed voice allocated")

    def test_the_last_of_the_twentyfour_voices_also_protects_its_sample(self):
        s = Swap()
        s.slot(600, base=F["DSP_MIN"], length=0x100)
        s.uc.mem_write(VOICE_FLAGS + 23, b"\1")
        s.uc.mem_write(VOICE_BASE + 23 * 0x48 + 4, word(PART_BASE))
        s.uc.mem_write(VOICE_BASE + 23 * 0x48 + 0x40, struct.pack("<H", 650))
        self.assertEqual(s.call("victim"), 0)

    def test_an_unresolved_busy_voice_defers_eviction_but_a_factory_oscillator_does_not(self):
        for number, expected in ((0xFFFF, 0), (10, 600)):
            with self.subTest(import_number=number):
                s = Swap()
                s.slot(600, base=F["DSP_MIN"], length=0x100)
                s.uc.mem_write(VOICE_FLAGS, b"\1")
                s.uc.mem_write(VOICE_BASE + 4, word(PART_BASE))
                s.uc.mem_write(VOICE_BASE + 0x40, struct.pack("<H", number))
                self.assertEqual(s.call("victim"), expected)

    def test_an_alias_does_not_make_a_factory_metadata_row_evictable(self):
        s = Swap()
        s.slot(400, base=F["DSP_MIN"], length=0x100)
        self.alias(s, 600, 700, 400)
        self.assertEqual(s.call("victim"), 0)

    def test_the_last_real_slot_is_valid_but_the_following_name_is_not_a_slot(self):
        s = Swap()
        s.slot(998, active=True)
        self.assertEqual(s.call("physical", 998), 998)
        self.assertEqual(s.call("resident", 998), 1)
        s.uc.mem_write(F["NAMES"] + 999 * 32 + 30, struct.pack("<H", 1048))
        self.assertEqual(s.call("physical", 999), 0xffffffff)

    def test_each_mapping_rejects_an_index_past_the_native_table(self):
        for at, value in ((F["NAMES"] + 600 * 32 + 30, 1049),
                          (F["MAP_A"] + 600 * 32 + 16, 999),
                          (F["MAP_B"] + 600 * 16 + 8, 999),
                          (F["MAP_C"] + 600 * 8 + 2, 999)):
            with self.subTest(address=hex(at)):
                s = Swap()
                s.slot(600, active=True)
                s.uc.mem_write(at, struct.pack("<H", value))
                self.assertEqual(s.call("physical", 600), 0xffffffff)

    def alias(self, s, slot, import_key, physical):
        s.uc.mem_write(F["NAMES"] + slot * 32 + 30, struct.pack("<H", import_key + 50))
        s.uc.mem_write(F["MAP_A"] + import_key * 32 + 16, struct.pack("<H", import_key))
        s.uc.mem_write(F["MAP_B"] + import_key * 16 + 8, struct.pack("<H", import_key))
        s.uc.mem_write(F["MAP_C"] + import_key * 8 + 2, struct.pack("<H", physical))

    def test_a_protected_alias_protects_the_same_physical_sample(self):
        s = Swap()
        s.slot(600, active=True, base=F["DSP_MIN"], length=1024)
        s.slot(601, active=True, base=F["DSP_MIN"] + 1024, length=1024)
        self.alias(s, 602, 702, 600)
        s.uc.mem_write(p.STATE + p.PROT, struct.pack("<32H", 602, *([0xFFFF] * 31)))
        self.assertEqual(s.call("victim"), 601)

    def test_a_protected_alias_cannot_be_the_only_eviction_candidate(self):
        s = Swap()
        s.slot(600, active=True, base=F["DSP_MIN"], length=1024)
        self.alias(s, 602, 702, 600)
        s.uc.mem_write(p.STATE + p.PROT, struct.pack("<32H", 602, *([0xFFFF] * 31)))
        self.assertEqual(s.call("victim"), 0)

    def test_follows_the_three_mappings_to_the_active_flag(self):
        s = Swap()
        s.slot(600, active=True)
        s.slot(601, active=False)
        self.assertEqual(s.call("resident", 600), 1)
        self.assertEqual(s.call("resident", 601), 0)
        s.uc.mem_write(F["NAMES"] + 602 * 32 + 30, struct.pack("<H", 10))
        self.assertEqual(s.call("resident", 602), 0, "an import number below 50 is no slot")
        self.assertEqual(s.call("resident", 1000), 0)


class LibraryOwnership(unittest.TestCase):
    def setup_loader(self, size=p.CAP_DEFAULT + 4097, close_status=0):
        s = Swap()
        s.file, s.path = 0xC1002000, 0xC1001000
        s.uc.mem_write(s.path, b"SD:/own.all\0")
        s.uc.mem_write(F["PANEL"], word(0xC1003000))
        for at, code in ((s.sym["store_recover"], "mov r0, #0\nbx lr"),
                         (F["F_CLOSE"], f"mov r0, #{close_status}\nbx lr"),
                         (F["F_OPEN"], f"ldr r3, ={size}\nstr r3, [r0, #12]\nmov r0, #0\nbx lr\n.pool")):
            s.uc.mem_write(at, arm.assemble(code, origin=at).bytes)
        s.events = []
        for at, name in ((F["F_CLOSE"], "close"), (s.sym["store_recover"], "recover"), (F["F_OPEN"], "open")):
            def called(uc, address, count, event):
                s.events.append((event, s.state("GEN"), s.state("J_STATE"), s.state("FILE")))
            s.uc.hook_add(unicorn.UC_HOOK_CODE, called, name, begin=at, end=at)
        return s

    def test_library_open_cancels_jobs_and_closes_old_reader_before_recovery(self):
        s = self.setup_loader()
        for field in ("FILE", "SESSION", "CFILL", "J_STATE"):
            s.set_state(field, 1)
        s.uc.mem_write(p.DIR + 601 * 16, struct.pack("<4I", p.ARENA_U, 32, 0, 7))
        self.assertEqual(s.call("cached", 601), 1)
        self.assertEqual(s.call("ss_fopen", s.file, s.path, 1), 0)
        self.assertEqual([e[0] for e in s.events], ["close", "recover", "open"])
        self.assertEqual(s.events[0][1:], (8, 0, 2))
        self.assertTrue(all(event[1:] == (8, 0, 0) for event in s.events[1:]), s.events)
        self.assertEqual(s.call("cached", 601), 0)

    def test_small_library_keeps_a_path_and_initialized_state_for_later_edits(self):
        s = self.setup_loader(size=4096)
        s.set_state("TSTATE", 0xFFFFFFFF)
        self.assertEqual(s.call("ss_fopen", s.file, s.path, 1), 0)
        self.assertEqual(s.state("MODE"), 0)
        self.assertEqual(s.state("GEN"), 8)
        self.assertEqual(s.state("TSTATE"), 0)
        self.assertEqual(bytes(s.uc.mem_read(p.STATE + p.PATH, 12)), b"SD:/own.all\0")

    def test_a_failed_close_refuses_the_new_load(self):
        s = self.setup_loader(close_status=1)
        s.set_state("FILE", 1)
        self.assertNotEqual(s.call("ss_fopen", s.file, s.path, 1), 0)
        self.assertEqual([e[0] for e in s.events], ["close"])
        self.assertEqual(s.state("MODE"), 2)
        self.assertEqual(s.state("FILE"), 2)

    def test_reopening_a_library_does_not_clear_a_dsp_protocol_fault(self):
        s = self.setup_loader()
        s.set_state("MODE", 2)
        s.set_state("TSTATE", 1)
        self.assertNotEqual(s.call("ss_fopen", s.file, s.path, 1), 0)
        self.assertEqual(s.events, [])
        self.assertEqual(s.state("TSTATE"), 1)
        self.assertEqual(s.state("MODE"), 2)

    def test_active_reload_never_publishes_an_off_window_or_a_zero_generation(self):
        for fault in (0, 1):
            with self.subTest(fault=fault):
                s = self.setup_loader()
                s.set_state("MODE", 2 if fault else 1)
                s.set_state("TSTATE", fault)
                writes = []
                s.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,
                              lambda uc, access, at, size, value, _: writes.append((at - p.STATE, value)),
                              begin=p.STATE, end=p.STATE + 4 * len(p.FIELDS) - 1)
                s.call("ss_fopen", s.file, s.path, 1)
                self.assertNotIn((p.OFF["MODE"], 0), writes)
                self.assertEqual([value for at, value in writes if at == p.OFF["GEN"]], [8])
                if fault:
                    self.assertNotIn((p.OFF["TSTATE"], 0), writes)


class SelectionCancellation(unittest.TestCase):
    SITE = 0xC008205C

    def run_selection(self, mode=1, pending=5, target=0, masked=False):
        s = Swap()
        s.set_state('MODE', mode)
        s.set_state('REQ', pending)
        s.uc.mem_write(p.STATE + p.FAILED, bytes([0xA5]) * 128)
        s.uc.mem_write(self.SITE + 4, arm.assemble('bx lr', origin=self.SITE + 4).bytes)
        instruction = (p.redirect(0xEA000000, self.SITE, s.sym['ss_selection']) if 'ss_selection' in s.sym
                       else 0xE1A0100D)
        s.uc.mem_write(self.SITE, word(instruction))
        s.uc.reg_write(R.UC_ARM_REG_CPSR, 0x93 if masked else 0x13)
        saved = {R.UC_ARM_REG_R0 + i: 0x1000 + i for i in range(13)}
        saved[R.UC_ARM_REG_R5] = target
        saved[R.UC_ARM_REG_R11] = p.STATE
        s.call(self.SITE, regs=saved)
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_R1), STACK)
        for register, value in saved.items():
            if register != R.UC_ARM_REG_R1:
                self.assertEqual(s.uc.reg_read(register), value)
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_CPSR) & 255, 0x93 if masked else 0x13)
        return s

    def test_an_accepted_new_choice_drops_the_old_pending_target_and_allows_retry(self):
        for target in (0, 5, 9):
            for masked in (False, True):
                with self.subTest(target=target, masked=masked):
                    s = self.run_selection(target=target, masked=masked)
                    self.assertEqual(s.state('REQ'), 0xFFFFFFFF)
                    self.assertEqual(bytes(s.uc.mem_read(p.STATE + p.FAILED, 128)), bytes(128))
                    self.assertEqual(s.state('GEN'), 7)

    def test_a_selection_without_a_pending_request_keeps_failed_prefetches(self):
        s = self.run_selection(pending=0xFFFFFFFF)
        self.assertEqual(s.state('REQ'), 0xFFFFFFFF)
        self.assertEqual(bytes(s.uc.mem_read(p.STATE + p.FAILED, 128)), bytes([0xA5]) * 128)

    def test_bypass_and_fault_modes_do_not_clear_a_deferred_target(self):
        for mode in (0, 2, 0xFFFFFFFF):
            with self.subTest(mode=mode):
                s = self.run_selection(mode=mode)
                self.assertEqual(s.state('REQ'), 5)
                self.assertEqual(bytes(s.uc.mem_read(p.STATE + p.FAILED, 128)), bytes([0xA5]) * 128)


class FramePosting(unittest.TestCase):
    def setup_frame(self):
        s = Swap()
        s.posts = []
        at = F['POST']
        s.uc.mem_write(at, arm.assemble('mvn r0, #0\nbx lr', origin=at).bytes)
        s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *args: s.posts.append(True), begin=at, end=at)
        return s

    def test_an_unacknowledged_notification_is_retried_without_using_post_return(self):
        s = self.setup_frame()
        s.call('ss_frame')
        self.assertEqual(len(s.posts), 1)
        for _ in range(49):
            s.call('ss_frame')
        self.assertEqual(len(s.posts), 1, 'a queued step does not flood the command task')
        s.call('ss_frame')
        self.assertEqual(len(s.posts), 2, 'a lost notification cannot stop loading forever')

    def test_a_dispatch_acknowledgement_allows_the_next_frame_to_post(self):
        s = self.setup_frame()
        s.call('ss_frame')
        s.set_state('MODE', 0)
        s.call('ss_step')
        s.set_state('MODE', 1)
        s.call('ss_frame')
        self.assertEqual(len(s.posts), 2)

    def test_inactive_frames_do_not_retry_or_change_the_pending_counter(self):
        for mode in (0, 2):
            with self.subTest(mode=mode):
                s = self.setup_frame()
                s.set_state('MODE', mode)
                s.set_state('POSTED', 5)
                for _ in range(60):
                    s.call('ss_frame')
                self.assertEqual(s.posts, [])
                self.assertEqual(s.state('POSTED'), 5)


class Ready(unittest.TestCase):
    def test_failed_samples_still_hold_the_switch_until_resident(self):
        s = Swap()
        s.slot(600, active=True)
        s.slot(601, active=False)
        s.slot(602, active=False, in_file=False)
        s.parts(5, [600, 601, 602, 7, 0xFFFF])
        self.assertEqual(s.call("ready", 5), 0)
        s.uc.mem_write(p.STATE + p.FAILED + 4 * (601 >> 5), word(1 << (601 & 31)))
        self.assertEqual(s.call("needs", 601), 0, "a failed job is not scheduled again")
        self.assertEqual(s.call("ready", 5), 0, "a failed job is not a loaded sample")
        s.slot(601, active=True)
        self.assertEqual(s.call("ready", 5), 0, "a user sample absent from the file is still missing")
        s.slot(602, active=True, in_file=False)
        self.assertEqual(s.call("ready", 5), 1)
        self.assertEqual(s.call("ready", 250), 1)

    def test_a_latched_transport_fault_keeps_the_sequence_gate_closed(self):
        s = Swap()
        s.slot(601, active=False)
        s.parts(5, [601])
        s.set_state("TSTATE", 1)
        s.set_state("POSTED", 1)
        s.call("ss_step")
        self.assertEqual(s.state("MODE"), 2)
        self.assertEqual(s.state("POSTED"), 0)
        s.call("ss_step")
        self.assertEqual(s.state("MODE"), 2)
        player = 0xC1000000
        s.uc.mem_write(player + 0x318, word(3))
        s.call("ss_gate_seq", player, 5, 0)
        self.assertEqual(s.calls[-1][2], 3, "the running pattern repeats after a fault")
        self.assertEqual(s.state("REQ"), 5)
        s.slot(601, active=True)
        s.call("ss_gate_seq", player, 5, 0)
        self.assertEqual(s.calls[-1][2], 3, "pattern changes also need DSP commands even when PCM is resident")
        self.assertEqual(s.state("TSTATE"), 1)

    def test_a_dsp_fault_refuses_factory_empty_and_resident_pattern_targets(self):
        for slots in ([7], [0xFFFF], [600]):
            with self.subTest(slots=slots):
                s = Swap()
                s.parts(5, slots)
                s.slot(600, active=True)
                s.set_state('TSTATE', 1)
                self.assertEqual(s.call('ready', 5), 0)

    def test_failed_samples_hold_the_sequence_gate(self):
        s = Swap()
        s.slot(601, active=False)
        s.parts(5, [601])
        s.call("set_failed", 601)
        player = 0xC1000000
        s.uc.mem_write(player + 0x318, word(3))
        s.call("ss_gate_seq", player, 5, 0)
        self.assertEqual(s.calls[-1][2], 3)
        self.assertEqual(s.state("REQ"), 5)

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

    def check_chain(self, mode, failed, resident, repeats):
        s = Swap()
        s.slot(601, active=resident)
        s.set_state("MODE", mode)
        s.set_state("REQ", 0xFFFFFFFF)
        if failed:
            s.call("set_failed", 601)
        s.parts(9, [601])
        player, pattern = 0xC1000000, 0xC1100000
        s.uc.mem_write(pattern + 0x3B06, bytes([repeats]))
        s.uc.mem_write(player + 0x318, word(2))
        s.uc.mem_write(player + 0x31C, word(0))
        # the chain step's frame: push {r4, r5, r6, lr}, as at 0xC0079A74
        frame = STACK - 16
        s.uc.mem_write(frame, word(0x11) + word(0x22) + word(0x33) + word(TRAP))
        s.uc.reg_write(R.UC_ARM_REG_SP, frame)
        for reg, value in ((R.UC_ARM_REG_R0, 9), (R.UC_ARM_REG_R4, player), (R.UC_ARM_REG_R6, pattern), (R.UC_ARM_REG_LR, 0)):
            s.uc.reg_write(reg, value)
        s.uc.emu_start(s.sym["ss_gate_chain"], TRAP, count=100_000)
        blocked = mode in (1, 2) and not resident
        self.assertEqual(s.u32(player + 0x318), 2 if blocked else 9)
        self.assertEqual(s.u32(player + 0x31C), max(repeats - 1, 0) if blocked else 0)
        self.assertEqual(s.state("REQ"), 9 if blocked else 0xFFFFFFFF)
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_R4), 0x11)
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_SP), STACK)

    def test_the_chain_waits_after_failures_and_transport_faults(self):
        for mode in (0, 1, 2, 0xFFFFFFFF):
            for failed in (False, True):
                for resident in (False, True):
                    for repeats in (0, 1, 4):
                        with self.subTest(mode=mode, failed=failed, resident=resident, repeats=repeats):
                            self.check_chain(mode, failed, resident, repeats)


class Place(unittest.TestCase):
    def test_only_the_final_candidate_check_masks_interrupts(self):
        s = Swap()
        s.slot(998, base=F["DSP_MIN"], length=0x100)
        s.uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
        counts = dict(masked=0, unmasked=0, delete_masked=False)

        def observe(uc, at, size, _):
            masked = bool(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)
            counts["masked" if masked else "unmasked"] += 1
            if at == F["DELETE"]:
                counts["delete_masked"] = masked

        s.uc.hook_add(unicorn.UC_HOOK_CODE, observe)
        slot = s.call("victim")
        self.assertEqual(slot, 998)
        self.assertEqual(counts["masked"], 0)
        self.assertGreater(counts["unmasked"], 5000)
        self.assertEqual(s.call("evict_unused", slot), slot)
        self.assertTrue(counts["delete_masked"])
        self.assertGreater(counts["masked"], 0)
        self.assertLess(counts["masked"], 5000)
        self.assertFalse(s.uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)
        s.uc.reg_write(R.UC_ARM_REG_CPSR, 0x93)
        self.assertEqual(s.call("evict_unused", slot), slot)
        self.assertTrue(s.uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)

    def test_a_candidate_used_after_the_snapshot_is_not_deleted(self):
        s = Swap()
        s.slot(600, base=F["DSP_MIN"], length=0x100)
        s.uc.mem_write(s.sym["ss_cap"], word(0x100))
        source = f"ldr r1, ={PART_BASE + 0x34}\nmov r2, #600\n.word 0xe1c120b0\nmov r0, #600\nbx lr\n.pool"
        s.uc.mem_write(s.sym["victim"], arm.assemble(source, origin=s.sym["victim"]).bytes)
        source = f"ldr r1, ={F['META'] + 600 * 0x45C + 11}\nmov r2, #0\nstrb r2, [r1]\nmov r0, #1\nbx lr\n.pool"
        s.uc.mem_write(F["DELETE"], arm.assemble(source, origin=F["DELETE"]).bytes)
        s.uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
        self.assertEqual(s.call("place", 0x100), 0)
        self.assertFalse(any(call[0] == F["DELETE"] for call in s.calls))
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80, 0)

    def test_names_after_the_last_metadata_record_are_not_a_dsp_extent(self):
        s = Swap()
        after = F["META"] + 999 * 0x45c
        s.uc.mem_write(after, word(F["DSP_MIN"]) + word(0x100) + b'\0\0\0\1')
        self.assertEqual(s.call("first_fit", 0x100), F["DSP_MIN"])

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


class CacheJob(unittest.TestCase):
    def job(self, *, cached=False):
        s = Swap()
        s.uc.mem_map(p.FIRMWARE["TIMER"], 0x1000)
        for name, value in dict(J_STATE=1, J_GEN=7, J_LEN=32, J_SLOT=601,
                                J_BITS=16, J_DST=0 if cached else 1, J_SRC=int(cached),
                                J_ENTRY=p.ARENA_U,
                                J_BASE=p.FIRMWARE["DSP_MIN"] if cached else p.ARENA_L,
                                J_STAGED=32 if cached else 0).items():
            s.set_state(name, value)
        s.uc.mem_write(F["F_READ"], arm.assemble("mov r0, #0\nbx lr", origin=F["F_READ"]).bytes)
        s.uc.mem_write(p.TRANSPORT, arm.assemble("mov r0, #0\nbx lr", origin=p.TRANSPORT).bytes)
        s.uc.mem_write(F["RESERVE"], arm.assemble("mov r0, #1\nbx lr", origin=F["RESERVE"]).bytes)
        s.uc.hook_add(unicorn.UC_HOOK_CODE, s.note, begin=F["RESERVE"], end=F["RESERVE"])
        return s

    def test_card_read_errors_and_short_chunks_invalidate_the_catalogue(self):
        for status, got in ((1, 32), (0, 30)):
            with self.subTest(status=status, got=got):
                s = self.job()
                s.uc.mem_write(F["F_READ"], arm.assemble(
                    f"mov r0, #{status}\nbx lr", origin=F["F_READ"]).bytes)
                s.set_state("GOT", got)
                self.assertEqual(s.read_call("chunk"), 1)
                self.assertEqual(s.state("MODE"), 2)
                self.assertEqual(s.state("J_STATE"), 0)
                self.assertEqual(s.calls, [])

    def test_install_does_not_adopt_a_new_generation_during_placement(self):
        s = self.job(cached=True)
        s.set_state("J_STATE", 0)
        s.slot(601, active=False)
        s.uc.mem_write(p.DIR + 601 * 16, word(p.ARENA_L) + word(32) + word(0) + word(7))
        s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: s.set_state("GEN", 8),
                      begin=s.sym["place"], end=s.sym["place"])
        s.read_call("start_install", 601)
        self.assertEqual(s.state("J_STATE"), 0, "old cache data must not start a new-generation job")
        self.assertEqual(s.state("J_GEN"), 7)
        self.assertEqual(s.calls, [])

    def test_prefetch_does_not_adopt_a_new_generation_during_parse(self):
        s = self.job()
        s.set_state("J_STATE", 0)
        s.set_state("FILE", 1)
        s.set_state("FILEGEN", 7)
        s.uc.mem_write(F["F_LSEEK"], arm.assemble("mov r0, #0\nbx lr", origin=F["F_LSEEK"]).bytes)
        s.uc.mem_write(F["PARSER"], arm.assemble("mov r0, #0x7e\nbx lr", origin=F["PARSER"]).bytes)
        writes = []

        def parsed(uc, *_):
            s.set_state("P_LEN", 32)
            s.set_state("P_BITS", 16)
            s.set_state("GEN", 8)

        s.uc.hook_add(unicorn.UC_HOOK_CODE, parsed, begin=F["PARSER"], end=F["PARSER"])
        s.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, lambda uc, access, at, size, value, data: writes.append(at),
                      begin=p.ARENA_U, end=p.ARENA_U + 0x49F)
        s.read_call("start_prepare", 601)
        self.assertEqual(writes, [])
        self.assertEqual(s.state("J_STATE"), 0)
        self.assertEqual(s.state("J_GEN"), 7)

    def test_the_private_reader_refuses_a_call_without_a_reader_token(self):
        s = self.job()
        entered = []
        s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: entered.append(True),
                      begin=F["F_OPEN"], end=F["F_OPEN"])
        self.assertNotEqual(s.call("ensure_file", regs={R.UC_ARM_REG_R10: 0}), 0)
        self.assertEqual(entered, [])
        self.assertEqual(s.owner(), (0, 0, 0, 0))

    def test_header_invalidation_does_not_relabel_an_open_file(self):
        s = self.job()
        s.uc.mem_write(F["F_OPEN"], arm.assemble("mov r0, #0\nbx lr", origin=F["F_OPEN"]).bytes)
        s.uc.mem_write(F["F_CLOSE"], arm.assemble("mov r0, #0\nbx lr", origin=F["F_CLOSE"]).bytes)
        opened = []
        s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: opened.append(True),
                      begin=F["F_OPEN"], end=F["F_OPEN"])

        def header(uc, *_):
            s.set_state("GOT", 0x1000)
            s.set_state("GEN", 8)

        s.uc.hook_add(unicorn.UC_HOOK_CODE, header, begin=F["F_READ"], end=F["F_READ"])
        self.assertNotEqual(s.read_call("ensure_file"), 0)
        self.assertEqual(s.state("MODE"), 1)
        self.assertEqual(s.state("FILEGEN"), 7)
        self.assertEqual(s.read_call("ensure_file"), 0)
        self.assertEqual(s.state("FILEGEN"), 8)
        self.assertEqual(len(opened), 2, "a new generation must reopen the previous file")

    def test_a_failed_close_prevents_reusing_the_reader_object(self):
        s = self.job()
        s.set_state("FILE", 1)
        s.set_state("FILEGEN", 6)
        s.uc.mem_write(F["F_CLOSE"], arm.assemble('mov r0, #1\nbx lr', origin=F["F_CLOSE"]).bytes)
        opened = []
        s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: opened.append(True), begin=F["F_OPEN"], end=F["F_OPEN"])
        self.assertNotEqual(s.read_call("ensure_file"), 0)
        self.assertEqual(opened, [])
        self.assertEqual((s.state("FILE"), s.state("MODE")), (2, 2))

    def test_an_incomplete_header_closes_its_reader_or_retains_an_uncertain_handle(self):
        for close_status in (0, 1):
            with self.subTest(close_status=close_status):
                s = self.job()
                for at, text in ((F["F_OPEN"], 'mov r0, #0\nbx lr'),
                                 (F["F_CLOSE"], f'mov r0, #{close_status}\nbx lr')):
                    s.uc.mem_write(at, arm.assemble(text, origin=at).bytes)
                closed = []
                s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: closed.append(True), begin=F["F_CLOSE"], end=F["F_CLOSE"])
                s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: s.set_state("GOT", 4092), begin=F["F_READ"], end=F["F_READ"])
                self.assertNotEqual(s.read_call("ensure_file"), 0)
                self.assertEqual(closed, [True])
                self.assertEqual(s.state("FILE"), 2 if close_status else 0)
                self.assertEqual(s.state("MODE"), 2)

    def test_a_mode_change_during_card_read_prevents_cache_writes(self):
        s = self.job()
        writes = []

        def read(uc, *_):
            uc.mem_write(p.STAGE, bytes(range(32)))
            s.set_state("GOT", 32)
            uc.mem_write(MANAGER + 0x24, word(1))

        s.uc.hook_add(unicorn.UC_HOOK_CODE, read, begin=F["F_READ"], end=F["F_READ"])
        s.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, lambda uc, access, at, size, value, data: writes.append(at),
                      begin=p.ARENA_L, end=p.ARENA_L + 0x4BF)
        self.assertEqual(s.read_call("chunk"), 2)
        self.assertEqual(writes, [])
        self.assertEqual(s.state("GEN"), 8)
        self.assertEqual(s.state("J_STATE"), 0)

    def test_native_publication_defers_ui_preemption_and_restores_irqs(self):
        s = self.job(cached=True)
        s.slot(601, base=F["DSP_MIN"], length=32)
        s.uc.mem_write(F["CURSOR"], word(F["DSP_MIN"] + 0x100))
        publication_masks, transfer_masks = [], []

        def preempt(uc, *_):
            masked = bool(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)
            publication_masks.append(masked)
            if not masked:
                s.set_state("GEN", 8)
                uc.mem_write(MANAGER + 0x2C, word(37))

        s.uc.hook_add(unicorn.UC_HOOK_CODE, preempt, begin=F["RESERVE"], end=F["RESERVE"])
        s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: transfer_masks.append(bool(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)),
                      begin=p.TRANSPORT, end=p.TRANSPORT)
        self.assertEqual(s.read_call("chunk"), 1)
        self.assertEqual(publication_masks, [True])
        self.assertEqual(transfer_masks, [False])
        self.assertEqual(s.state("GEN"), 7)
        self.assertEqual(s.state("STAT_COUNT"), 1)
        self.assertEqual(s.u32(F["CURSOR"]), F["DSP_MIN"] + 0x100)
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_CPSR) & 255, 0x13)

    def test_cached_descriptor_corruption_is_refused_before_native_publication(self):
        for offset, data in ((2, b"BAD!"), (44, word(8000000)), (48, word(8000000)), (60, word(8000000))):
            for during_copy in (False, True):
                with self.subTest(offset=offset, during_copy=during_copy):
                    s = self.job(cached=True)
                    s.slot(601, active=False)
                    def corrupt(uc, *_):
                        if uc.reg_read(R.UC_ARM_REG_R0) == p.DESC2:
                            uc.mem_write(p.ARENA_U + offset, data)
                    if during_copy:
                        s.uc.hook_add(unicorn.UC_HOOK_CODE, corrupt, begin=s.sym["copy32"], end=s.sym["copy32"])
                    else:
                        s.uc.mem_write(p.ARENA_U + offset, data)
                    self.assertEqual(s.read_call("chunk"), 1)
                    self.assertEqual(s.calls, [])
                    self.assertEqual(s.state("GEN"), 8)
                    self.assertEqual(s.state("J_STATE"), 0)
                    self.assertEqual(s.state("STAT_COUNT"), 0)
                    self.assertEqual(s.u32(p.STATE + p.FAILED + 4 * (601 >> 5)) & (1 << (601 & 31)), 0)

    def test_a_mode_change_during_transfer_or_descriptor_copy_prevents_publication(self):
        for hook in (p.TRANSPORT, "copy32"):
            with self.subTest(hook=hook):
                s = self.job(cached=True)
                address = s.sym[hook] if isinstance(hook, str) else hook
                s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *args: uc.mem_write(TRANSPORT_OBJECT + 0x308, word(11)),
                              begin=address, end=address)
                self.assertEqual(s.read_call("chunk"), 2)
                self.assertEqual(s.calls, [])
                self.assertEqual(s.state("GEN"), 8)
                self.assertEqual(s.state("J_STATE"), 0)

    def test_invalidation_during_card_read_prevents_cache_writes_and_publication(self):
        s = self.job()
        writes = []

        def read(uc, *_):
            uc.mem_write(p.STAGE, bytes(range(32)))
            s.set_state("GOT", 32)
            s.set_state("GEN", 8)

        s.uc.hook_add(unicorn.UC_HOOK_CODE, read, begin=F["F_READ"], end=F["F_READ"])
        s.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, lambda uc, access, at, size, value, data: writes.append(at),
                      begin=p.ARENA_L, end=p.ARENA_L + 0x4BF)
        self.assertEqual(s.read_call("chunk"), 1)
        self.assertEqual(writes, [], "an invalidated job cannot write into the borrowed buffer")
        self.assertEqual(s.u32(p.DIR + 601 * 16), 0)
        self.assertEqual(s.state("J_STATE"), 0)
        self.assertEqual(s.state("CFILL"), 0)

    def test_invalidation_during_dsp_transfer_prevents_slot_publication(self):
        s = self.job(cached=True)
        s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: s.set_state("GEN", 8),
                      begin=p.TRANSPORT, end=p.TRANSPORT)
        self.assertEqual(s.read_call("chunk"), 1)
        self.assertEqual(s.calls, [], "an old job must not reserve a playable slot")
        self.assertEqual(s.state("J_STATE"), 0)
        self.assertEqual(s.state("STAT_COUNT"), 0)

    def test_invalidation_during_descriptor_copy_prevents_slot_publication(self):
        s = self.job(cached=True)

        def copied(uc, *_):
            if uc.reg_read(R.UC_ARM_REG_R0) == p.DESC2:
                s.set_state("GEN", 8)

        s.uc.hook_add(unicorn.UC_HOOK_CODE, copied, begin=s.sym["copy32"], end=s.sym["copy32"])
        self.assertEqual(s.read_call("chunk"), 1)
        self.assertEqual(s.calls, [])
        self.assertEqual(s.state("J_STATE"), 0)


class CacheHandoff(unittest.TestCase):
    def inject_handoff(self, s, destination, length, *, after_read):
        foreign = bytes([0xA5]) * length
        state = dict(copying=False, pending=False, handed=False, writes=[])

        def code(uc, at, size, _):
            if at == s.sym["copy32"] and uc.reg_read(R.UC_ARM_REG_R0) == destination:
                state["copying"] = True
                state["pending"] = not after_read
            if state["pending"] and not uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80:
                state["pending"] = False
                state["handed"] = True
                s.set_state("GEN", 8)
                s.set_state("SESSION", 0)
                s.set_state("CFILL", 0)
                uc.mem_write(destination, foreign)

        def read(uc, access, at, size, value, _):
            if state["copying"] and not state["handed"]:
                state["pending"] = True

        def write(uc, access, at, size, value, _):
            if state["handed"]:
                state["writes"].append(at)

        s.uc.hook_add(unicorn.UC_HOOK_CODE, code)
        if after_read:
            s.uc.hook_add(unicorn.UC_HOOK_MEM_READ, read,
                          begin=p.STAGE, end=p.STAGE + p.CHUNK - 1)
            s.uc.hook_add(unicorn.UC_HOOK_MEM_READ, read,
                          begin=p.DESC, end=p.DESC + 0x49F)
        s.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write,
                      begin=destination, end=destination + length - 1)
        return state, foreign

    def test_prefetch_pcm_cannot_write_after_work_buffer_handoff(self):
        for after_read in (False, True):
            with self.subTest(after_read=after_read):
                s = CacheJob().job()
                destination = p.ARENA_L + 0x4A0
                for name, value in dict(J_LEN=96, J_STAGED=96).items():
                    s.set_state(name, value)
                s.uc.mem_write(p.STAGE, bytes(range(96)))
                state, foreign = self.inject_handoff(s, destination, 96, after_read=after_read)
                self.assertEqual(s.read_call("chunk"), 1)
                self.assertTrue(state["handed"])
                self.assertEqual(state["writes"], [])
                self.assertEqual(bytes(s.uc.mem_read(destination, 96)), foreign)
                self.assertEqual(s.state("J_STATE"), 0)
                self.assertEqual(s.state("J_DONE"), 0)
                self.assertEqual(s.u32(p.DIR + 601 * 16), 0)

    def test_prefetch_descriptor_cannot_write_after_work_buffer_handoff(self):
        for after_read in (False, True):
            with self.subTest(after_read=after_read):
                s = AllocationBounds().prepared(96)
                s.set_state("CPTR", p.ARENA_L)
                s.set_state("CGEN", 7)
                s.uc.mem_write(p.DESC, bytes((i * 3) % 256 for i in range(0x4A0)))
                state, foreign = self.inject_handoff(s, p.ARENA_L, 0x4A0, after_read=after_read)
                s.read_call("start_prepare", 601)
                self.assertTrue(state["handed"])
                self.assertEqual(state["writes"], [])
                self.assertEqual(bytes(s.uc.mem_read(p.ARENA_L, 0x4A0)), foreign)
                self.assertEqual(s.state("J_STATE"), 0)
                self.assertEqual(s.u32(p.DIR + 601 * 16), 0)

    def test_cache_copy_preserves_registers_and_original_irq_state(self):
        for control in (0x13, 0x93):
            for stale in (False, True):
                with self.subTest(control=control, stale=stale):
                    s = Swap()
                    s.set_state("J_GEN", 6 if stale else 7)
                    payload = bytes(range(96))
                    s.uc.mem_write(p.STAGE, payload)
                    registers = {R.UC_ARM_REG_R4 + i: 0x12340000 + i for i in range(7)}
                    s.call("copy32", p.ARENA_L, p.STAGE, 96,
                           regs={**registers, R.UC_ARM_REG_CPSR: control})
                    self.assertEqual(bytes(s.uc.mem_read(p.ARENA_L, 96)), bytes(96) if stale else payload)
                    self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_CPSR) & 255, control)
                    for reg, value in registers.items():
                        self.assertEqual(s.uc.reg_read(reg), value)

    def test_large_copy_restores_interrupts_between_small_writes(self):
        s = Swap()
        s.set_state("J_GEN", 7)
        payload = bytes((i * 7) % 256 for i in range(p.CHUNK))
        s.uc.mem_write(p.STAGE, payload)
        masked = dict(current=0, longest=0, writes=0)

        def code(uc, *_):
            if uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80:
                masked["current"] += 1
                masked["longest"] = max(masked["longest"], masked["current"])
            else:
                masked["current"] = 0

        def write(uc, *_):
            self.assertTrue(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)
            masked["writes"] += 1

        s.uc.hook_add(unicorn.UC_HOOK_CODE, code)
        s.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write,
                      begin=p.ARENA_L, end=p.ARENA_L + p.CHUNK - 1)
        s.call("copy32", p.ARENA_L, p.STAGE, p.CHUNK)
        self.assertEqual(bytes(s.uc.mem_read(p.ARENA_L, p.CHUNK)), payload)
        self.assertEqual(masked["writes"], p.CHUNK // 4)
        self.assertLessEqual(masked["longest"], 16)
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_CPSR) & 255, 0x13)


class Publication(unittest.TestCase):
    def setup_publication(self):
        s = CacheJob().job(cached=True)
        s.uc.mem_write(F["CURSOR"], word(F["DSP_MIN"] + 0x100))
        return s

    def test_every_exit_preserves_the_original_irq_mask_and_cursor(self):
        for control in (0x13, 0x93):
            for outcome in ("success", "stale", "context", "refusal"):
                with self.subTest(control=control, outcome=outcome):
                    s = self.setup_publication()
                    if outcome == "stale":
                        s.set_state("GEN", 8)
                    elif outcome == "context":
                        s.uc.mem_write(MANAGER + 0x2C, word(37))
                    elif outcome == "refusal":
                        s.uc.mem_write(F["RESERVE"], arm.assemble("mov r0, #0\nbx lr", origin=F["RESERVE"]).bytes)
                    self.assertEqual(s.call("publish", regs={R.UC_ARM_REG_CPSR: control}),
                                     dict(success=0, stale=1, context=2, refusal=3)[outcome])
                    self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_CPSR) & 255, control)
                    self.assertEqual(s.u32(F["CURSOR"]), F["DSP_MIN"] + 0x100)
                    self.assertEqual(len(s.calls), int(outcome in ("success", "refusal")))

    def test_cache_checksum_includes_the_original_descriptor_and_pcm(self):
        s = CacheJob().job()
        descriptor = bytes((i * 3) % 256 for i in range(0x4A0))
        pcm = bytes(range(32))
        s.uc.mem_write(p.DESC, descriptor)
        for name, value in dict(J_STATE=0, P_LEN=32, P_BITS=16, CPTR=p.ARENA_U, CGEN=7).items():
            s.set_state(name, value)
        s.uc.mem_write(s.sym["parse"], arm.assemble("mov r0, #0\nbx lr", origin=s.sym["parse"]).bytes)
        s.read_call("start_prepare", 601)
        descriptor_sum = sum(struct.unpack("<296I", descriptor)) & 0xFFFFFFFF
        self.assertEqual(s.state("J_SUM"), descriptor_sum)

        def read(uc, *_):
            uc.mem_write(p.STAGE, pcm)
            s.set_state("GOT", len(pcm))

        s.uc.hook_add(unicorn.UC_HOOK_CODE, read, begin=F["F_READ"], end=F["F_READ"])
        self.assertEqual(s.read_call("chunk"), 1)
        self.assertEqual(s.u32(p.DIR + 601 * 16 + 8),
                         (descriptor_sum + sum(struct.unpack("<8I", pcm))) & 0xFFFFFFFF)


class Encoding(unittest.TestCase):
    def test_half_word_lines(self):
        text = p.halfword("ldrh r1, [r2, #30]\nstrh r3, [r1]\nldrh r0, [r0, r1]")
        self.assertEqual(text.splitlines(), [".word 0xe1d211be", ".word 0xe1c130b0", ".word 0xe19000b1"])

    def test_the_code_fits_its_areas(self):
        sections, _ = p.build_code(SCREENS)
        for at, data in sections:
            area = next(a for a in p.AREAS if a[0] <= at < a[1])
            self.assertLessEqual(at + len(data), area[1])


class ChangedRows(unittest.TestCase):
    """Rows the user changed since the start (import, sampling, a sample edit) are never moved out."""

    def test_an_edited_row_stays_until_its_signature_is_back(self):
        s = Swap()
        s.slot(600, base=F["DSP_MIN"], length=0x100)
        self.assertEqual(s.call("victim"), 600)
        meta = F["META"] + 600 * 0x45C
        s.uc.mem_write(meta + 0x30, word(0x1234))          # e.g. a loop point changed in SAMPLE EDIT
        self.assertEqual(s.call("victim"), 0)
        self.assertEqual(s.call("can_evict", 600), 0)
        s.uc.mem_write(meta + 0x30, word(0))
        self.assertEqual(s.call("victim"), 600)

    def test_a_renamed_or_reimported_slot_stays(self):
        s = Swap()
        s.slot(600, base=F["DSP_MIN"], length=0x100)
        s.uc.mem_write(F["NAMES"] + 600 * 32, b"imported")
        self.assertEqual(s.call("victim"), 0)

    def test_a_row_the_loader_never_recorded_stays(self):
        s = Swap()
        s.slot(600, base=F["DSP_MIN"], length=0x100)
        s.uc.mem_write(p.SIG + 600 * 4, word(0))
        self.assertEqual(s.call("victim"), 0)

    def test_the_start_records_loaded_rows_only_with_the_swap_on(self):
        for mode in (0, 1, 2):
            with self.subTest(mode=mode):
                s = Swap()
                s.slot(600, base=F["DSP_MIN"], length=0x100)
                s.slot(601, active=False)
                s.uc.mem_write(p.SIG + 600 * 4, word(0))
                s.uc.mem_write(p.SIG + 601 * 4, word(0x55))
                s.set_state("MODE", mode)
                s.call("finish_pins")
                self.assertEqual(s.u32(p.SIG + 600 * 4) != 0, mode == 1)
                self.assertEqual(s.u32(p.SIG + 601 * 4), 0 if mode == 1 else 0x55)
                s.set_state("MODE", 1)
                self.assertEqual(s.call("victim"), 600 if mode == 1 else 0)


class ExportAll(unittest.TestCase):
    def test_export_all_is_refused_while_the_dsp_holds_part_of_the_file(self):
        for mode, refused in ((0, False), (1, True), (2, True), (0xFFFFFFFF, False)):
            with self.subTest(mode=mode):
                s = Swap()
                s.set_state("MODE", mode)
                opened = []
                s.uc.mem_write(F["F_OPEN"], arm.assemble("mov r0, #0\nbx lr", origin=F["F_OPEN"]).bytes)
                s.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: opened.append(1), begin=F["F_OPEN"], end=F["F_OPEN"])
                result = s.call("ss_export_open", 0xC1000000, 0xC1000100, 0x0A)
                self.assertEqual(bool(opened), not refused)
                self.assertEqual(result, 10 if refused else 0)


class NativeGate(unittest.TestCase):
    """The native DSP deadline bounds a transaction only while the swap's own step runs."""

    def taken(self, mode, step):
        s = Swap()
        s.uc.mem_write(p.NATIVE_SCOPE, word(0))
        s.set_state("MODE", mode)
        s.set_state("INSTEP", step)
        acquire = 0xC0000D80
        s.uc.mem_write(acquire, arm.assemble("mov r0, #0\nbx lr", origin=acquire).bytes)
        bounded = []

        def stop(uc, *_):
            bounded.append(1)
            uc.reg_write(R.UC_ARM_REG_PC, TRAP)
        s.uc.hook_add(unicorn.UC_HOOK_CODE, stop, begin=s.sym["native_scope_enter"], end=s.sym["native_scope_enter"])
        s.uc.reg_write(R.UC_ARM_REG_SP, STACK)
        s.uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        s.uc.emu_start(s.sym["native_scope_take"], TRAP, count=10_000)
        return bool(bounded)

    def test_only_the_swaps_step_is_bounded(self):
        for mode, step, bounded in ((1, 1, True), (1, 0, False), (0, 1, False), (2, 1, False), (0, 0, False)):
            with self.subTest(mode=mode, step=step):
                self.assertEqual(self.taken(mode, step), bounded)


if __name__ == "__main__":
    unittest.main()
