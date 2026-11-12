"""Native save/delete use a checked catalogue and generated runtime descriptors."""
import struct
import unittest

import unicorn
from unicorn import arm_const as R

import arm
import sample_swap as p
import test_sample_swap as support

F, TRANSPORT, TRAP, word = support.F, support.TRANSPORT_OBJECT, support.TRAP, support.word


class NativePersistence(unittest.TestCase):
    def test_blechy_compiler_cannot_grow_into_the_persistence_code(self):
        from tools.patch import script_hooks
        self.assertLessEqual(script_hooks.BLECHY_BLOCK_END, p.PERSISTENCE_CODE)

    def setup(self, *, status=0, commit=True, deleting=False, transport=0):
        s = support.CatalogueOwnership().setup_writer(size=16384)
        s.set_state("MODE", 0)
        s.uc.mem_write(p.native_dsp_acquire.CURRENT_TASK, word(p.native_sample_import.COMMAND_TASK))
        s.uc.mem_write(p.native_sample_import.TRANSPORT_PTR, word(TRANSPORT))
        s.uc.mem_write(TRANSPORT + 0x308, word(transport))
        s.raw = bytes((i * 19 + 7) % 256 for i in range(1172))
        s.operations = []

        def stub(label, code, callback=None):
            at = s.sym[label] if isinstance(label, str) else label
            s.uc.mem_write(at, arm.assemble(code, origin=at).bytes)
            if callback is not None:
                s.uc.hook_add(unicorn.UC_HOOK_CODE, callback, begin=at, end=at)
        s.stub = stub
        stub("resident", "mov r0, #1\nbx lr")
        stub(0xC004E4EC, "ldr r0, =601\nbx lr\n.pool")
        stub(0xC004EF94, "ldr r0, =500\nbx lr\n.pool")

        def store(uc, *_):
            self.assertEqual(s.owner()[3], p.sample_owner.RECOVER)
            self.assertEqual(s.u32(p.IMPORT_LOCK), 1)
            self.assertEqual(uc.reg_read(R.UC_ARM_REG_SP) % 8, 0)
            s.operations.append("delete" if deleting else "save")
            uc.mem_write(p.PERSIST_RAW, s.raw)
            if commit:
                header = bytearray(s.header)
                struct.pack_into("<I", header, 2016, 0 if deleting else 8192)
                s.header = bytes(header)

        stub("store_delete" if deleting else "store_snapshot", f"mov r0, #{status}\nbx lr", store)
        return s

    def test_saved_and_failed_snapshots_preserve_mode_and_report_confirmed_state(self):
        for status, commit in ((0, True), (1, False), (1, True), (0, False)):
            for mode in (0, 1):
                with self.subTest(status=status, commit=commit, mode=mode):
                    s = self.setup(status=status, commit=commit)
                    s.set_state("MODE", mode)
                    self.assertEqual(s.call("persist_save", 500), 0 if status == 0 else 4)
                    self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_R1), int(status == 0 or commit))
                    self.assertEqual(s.u32(p.STATE + p.OFF["MODE"]), mode)
                    self.assertEqual(s.u32(p.IMPORT_LOCK), 0)
                    self.assertEqual(s.owner()[0], 0)

    def test_command_confirms_only_a_durable_raw_snapshot(self):
        for status, commit in ((0, True), (1, False), (1, True)):
            with self.subTest(status=status, commit=commit):
                s = self.setup(status=status, commit=commit)
                command = 0xC1003000
                old = b"\xa5" * 1172
                s.uc.mem_write(0xC0345A2C, old)
                s.uc.mem_write(0xC0345A20, b"\1")
                s.stub(0xC0039748, f"ldr pc, ={TRAP}\n.pool")
                s.call("native_save_command", regs={R.UC_ARM_REG_R4: command, R.UC_ARM_REG_R5: 500})
                self.assertEqual(bytes(s.uc.mem_read(command + 24, 1)), bytes([0 if status == 0 else 4]))
                saved = bytes(s.uc.mem_read(0xC0345A2C, 1172))
                self.assertEqual(saved, s.raw if status == 0 or commit else old)

    def test_capture_confirmation_refuses_a_slot_already_on_card(self):
        s = self.setup(transport=12)
        self.assertEqual(s.call("persist_save", 500), 4)
        self.assertEqual(s.operations, [])
        self.assertEqual(s.u32(p.IMPORT_LOCK), 0)
        self.assertEqual(s.owner()[0], 0)

    def test_delete_removes_native_row_only_after_confirmed_index(self):
        for status, commit in ((0, True), (1, False), (1, True)):
            with self.subTest(status=status, commit=commit):
                s = self.setup(status=status, commit=commit, deleting=True)
                self.assertEqual(s.call("persist_delete", 500), 0 if status == 0 else 4)
                self.assertEqual(len(s.calls), int(commit))
                if commit:
                    self.assertEqual(s.calls[0][0:2], (F["DELETE"], 601))
                self.assertEqual(s.u32(p.IMPORT_LOCK), 0)
                self.assertEqual(s.owner()[0], 0)

    def test_delete_refuses_a_surviving_resident_alias_before_card_changes(self):
        s = self.setup(deleting=True)
        s.slot(500, active=True, base=F["DSP_MIN"], length=128)
        s.uc.mem_write(F["NAMES"] + 501 * 32 + 30, struct.pack("<H", 550))
        old = s.header
        self.assertEqual(s.call("persist_delete", 500), 4)
        self.assertEqual(s.header, old)
        self.assertEqual(s.operations, [])
        self.assertEqual(s.calls, [])
        self.assertEqual(s.u32(p.IMPORT_LOCK), 0)
        self.assertEqual(s.owner()[0], 0)

    def test_capture_exit_never_deletes_the_library_record(self):
        s = self.setup(deleting=True, transport=12)
        old = s.header
        self.assertEqual(s.call("persist_delete", 500), 0)
        self.assertEqual(s.header, old)
        self.assertEqual(s.operations, [])
        self.assertEqual(s.calls[0][0:2], (F["DELETE"], 601))
        self.assertEqual(s.u32(p.IMPORT_LOCK), 0)

    def test_running_transport_cannot_start_a_card_mutation(self):
        for label in ("persist_save", "persist_delete"):
            with self.subTest(label=label):
                s = self.setup(transport=1)
                self.assertEqual(s.call(label, 500), 4)
                self.assertEqual(s.operations, [])
                self.assertEqual(s.u32(p.IMPORT_LOCK), 0)
                self.assertEqual(s.owner()[0], 0)

    def test_capture_allocator_excludes_offloaded_library_slots(self):
        s = self.setup()
        s.set_state("MODE", 1)
        s.slot(500, active=False, base=F["DSP_MIN"], length=128)
        s.slot(501, active=False, base=F["DSP_MIN"] + 128, length=128)
        header = bytearray(s.header)
        struct.pack_into("<I", header, 16 + 501 * 4, 8192)
        s.uc.mem_write(p.HDR, bytes(header))
        s.stub("resident", "mov r0, #0\nbx lr")
        self.assertEqual(s.call("persist_capture_slot"), 502)
        self.assertEqual(s.operations, [])
        s.uc.mem_write(p.FILE_OWNER + 8, word(1))
        self.assertEqual(s.call("persist_capture_slot"), 0xFFFFFFFF)

    def test_capture_allocator_excludes_an_inactive_row_owned_by_an_indexed_alias(self):
        s = self.setup()
        s.set_state("MODE", 1)
        s.slot(500, active=False, base=F["DSP_MIN"], length=128)
        s.uc.mem_write(F["NAMES"] + 501 * 32 + 30, struct.pack("<H", 550))
        header = bytearray(s.header)
        struct.pack_into("<I", header, 16 + 500 * 4, 0)
        struct.pack_into("<I", header, 16 + 501 * 4, 8192)
        s.uc.mem_write(p.HDR, bytes(header))
        s.stub("resident", "mov r0, #0\nbx lr")
        self.assertEqual(s.call("persist_capture_slot"), 502)
        self.assertEqual(s.operations, [])

    def test_capture_allocator_excludes_intermediate_mapping_rows_owned_by_an_indexed_alias(self):
        for mode in (0, 1):
            with self.subTest(mode=mode):
                s = self.setup()
                s.set_state("MODE", mode)
                s.slot(500, active=False, base=F["DSP_MIN"], length=128)
                s.uc.mem_write(F["NAMES"] + 501 * 32 + 30, struct.pack("<H", 650))
                s.uc.mem_write(F["MAP_A"] + 600 * 32 + 16, struct.pack("<H", 700))
                s.uc.mem_write(F["MAP_B"] + 700 * 16 + 8, struct.pack("<H", 500))
                s.uc.mem_write(F["MAP_C"] + 500 * 8 + 2, struct.pack("<H", 503))
                header = bytearray(s.header)
                struct.pack_into("<I", header, 16 + 500 * 4, 0)
                struct.pack_into("<I", header, 16 + 501 * 4, 8192)
                s.uc.mem_write(p.HDR, bytes(header))
                s.stub("resident", "mov r0, #0\nbx lr")
                self.assertEqual(s.call("persist_capture_slot"), 502)

    def test_an_absent_catalogue_clears_stale_cached_offsets(self):
        s = self.setup()
        s.uc.mem_write(p.HDR, s.header)
        s.stub(F["F_OPEN"], "mov r0, #4\nbx lr")
        self.assertEqual(s.call("catalogue_begin_import"), 0)
        self.assertEqual(bytes(s.uc.mem_read(p.HDR, 4096)), bytes(4096))

    def test_initial_missing_library_is_checked_before_capture_can_allocate(self):
        for opened in (4, 1):
            with self.subTest(opened=opened):
                s = self.setup()
                s.set_state("MODE", 0xFFFFFFFF)
                s.uc.mem_write(p.NATIVE_SCOPE, word(0xFFFFFFFF))
                s.uc.mem_write(p.FILE_OWNER + 8, word(1))
                s.stub(0xC0035440, "mov r0, #0\nbx lr")
                s.stub(F["F_OPEN"], f"mov r0, #{opened}\nbx lr")
                s.stub("persist_enter", f"ldr r1, ={p.STATE}\nmov r0, #0\nstr r0, [r1]\nldr r1, ={p.NATIVE_SCOPE}\nstr r0, [r1]\nbx lr\n.pool")
                self.assertEqual(s.call("persist_library_probe"), 0)
                self.assertEqual(s.u32(p.FILE_OWNER + 8), int(opened != 4))
                self.assertEqual(s.u32(p.IMPORT_LOCK), 0)
                self.assertEqual(s.owner()[0], 0)
                if opened == 4:
                    self.assertEqual(bytes(s.uc.mem_read(p.HDR, 4096)), bytes(4096))
                else:
                    self.assertEqual(s.u32(p.STATE + p.OFF["MODE"]), 2)

    def test_capture_refuses_an_invalid_indexed_mapping(self):
        s = self.setup()
        s.set_state("MODE", 1)
        s.uc.mem_write(p.HDR, s.header)
        s.stub("resident", "mov r0, #0\nbx lr")
        self.assertEqual(s.call("persist_capture_slot"), 0xFFFFFFFF)

    def test_confirmed_save_cleans_only_a_uniquely_named_row(self):
        for alias in (False, True):
            with self.subTest(alias=alias):
                s = support.Swap()
                s.slot(500, active=True, base=F["DSP_MIN"], length=128)
                s.call("protection_init")
                if alias:
                    s.uc.mem_write(F["NAMES"] + 501 * 32 + 30, struct.pack("<H", 550))
                s.call("protection_bit", 500, 1)
                revision = s.u32(p.PROTECTION_REV)
                s.call("persist_mark_clean", 500, revision)
                self.assertEqual(s.call("protection_dirty", 500), int(alias))
                self.assertEqual(s.u32(p.SIG + 500 * 4) != 0, not alias)

    def test_capture_mapping_scan_runs_after_the_native_stop(self):
        s = self.setup()
        calls = []
        s.stub(0xC004F270, "bx lr", lambda *_: calls.append("stop"))
        s.stub("persist_capture_slot", "mov r0, #500\nadd r0, r0, #2\nbx lr",
               lambda *_: calls.append("slot"))
        s.stub(0xC0082DDC, f"bl 0xC004F270\nb {TRAP}")
        s.stub(0xC0082DE4, f"b {TRAP}")
        s.call("capture_stop_command")
        self.assertEqual(calls, ["stop", "slot"])
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_R5), 502)

    def test_foreign_task_cannot_start_a_card_mutation(self):
        s = self.setup()
        s.uc.mem_write(p.native_dsp_acquire.CURRENT_TASK, word(0))
        self.assertEqual(s.call("persist_save", 500), 4)
        self.assertEqual(s.operations, [])
        self.assertEqual(s.u32(p.IMPORT_LOCK), 0)
