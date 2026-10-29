"""Recovery runs as ARM against generated journals and a file API model."""
import binascii
import struct
import unittest
import sys
from pathlib import Path

import unicorn
from unicorn import arm_const as R

import sample_store as p
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "emu"))
import sampleset

ORIGIN, STATE, STACK, TRAP = 0xC1000000, 0xC2000000, 0xC2101000, 0xC0001000
LIBRARY = b"SD:/KORG/blechtribe/Sample/e2sSample.all"
JOURNAL = LIBRARY[:-3] + b"txn"


def word(value):
    return struct.pack("<I", value)


def header():
    out = bytearray(4096)
    out[:16] = b"e2s sample all\x1a\0"
    struct.pack_into("<I", out, 16 + 500 * 4, 4096)
    return out


def transaction(old, payload=b"RIFF" + bytes(range(256)) * 600, delete=False):
    new_header = bytearray(old[:4096])
    struct.pack_into("<I", new_header, 16 + 500 * 4, 0 if delete else len(old))
    record = bytearray(4160)
    record[:8] = b"BLECHTX1"
    values = [1, 2 if delete else 1, 500, len(old), len(old) if delete else len(old) + len(payload),
              0 if delete else len(old), 0 if delete else len(payload),
              0 if delete else binascii.crc32(payload), binascii.crc32(old[:4096]), binascii.crc32(new_header)]
    struct.pack_into("<10I", record, 8, *values)
    record[64:] = old[:4096]
    struct.pack_into("<I", record, 60, binascii.crc32(record))
    return bytes(record), bytes(new_header)


class SparseFile:
    def __init__(self, prefix, size):
        self.size = size
        self.blocks = [(0, bytes(prefix))]

    def __len__(self):
        return self.size

    def __getitem__(self, span):
        start, stop, step = span.indices(self.size)
        assert step == 1 and stop - start <= 65536
        out = bytearray(stop - start)
        for at, data in self.blocks:
            lo, hi = max(start, at), min(stop, at + len(data))
            if hi > lo:
                out[lo - start:hi - start] = data[lo - at:hi - at]
        return out

    def __setitem__(self, span, data):
        assert span.step is None and span.stop - span.start == len(data)
        self.blocks.append((span.start, bytes(data)))
        self.size = max(self.size, span.stop)


class Machine:
    def __init__(self, library, journal=None):
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        for at, size in ((0xC0000000, 0x100000), (ORIGIN, 0x10000), (STATE, 0x20000), (STACK - 0x1000, 0x2000)):
            self.uc.mem_map(at, size)
        code, self.symbols = p.build_code(ORIGIN, STATE)
        self.uc.mem_write(ORIGIN, code)
        self.path = STATE + 0x1F000
        self.uc.mem_write(self.path, LIBRARY + b"\0")
        self.files = {LIBRARY: library if isinstance(library, SparseFile) else bytearray(library)}
        if journal is not None:
            self.files[JOURNAL] = bytearray(journal)
        self.handles, self.calls, self.writes = {}, [], []
        self.read_error = False
        self.short_write = False
        self.close_error_at = None
        self.close_error_status = 1
        self.close_count = 0
        self.unlink_error = False
        self.source = b""
        self.descriptor = STATE + 0x1D000
        source_at = 0xC0002000
        self.uc.mem_write(self.descriptor, word(source_at) + word(0))
        self.uc.mem_write(source_at, word(0xE12FFF1E))
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.reader, begin=source_at, end=source_at)
        for name, at in p.API.items():
            self.uc.mem_write(at, word(0xE12FFF1E))
            self.uc.hook_add(unicorn.UC_HOOK_CODE, self.native, name, begin=at, end=at)

    def string(self, at):
        return bytes(self.uc.mem_read(at, 128)).split(b"\0")[0]

    def native(self, uc, at, size, name):
        self.assert_aligned(uc)
        r = [uc.reg_read(R.UC_ARM_REG_R0 + i) for i in range(4)]
        self.calls.append(name)
        result = 0
        if name == "OPEN":
            path = self.string(r[1])
            if r[2] & 8:
                self.files[path] = bytearray()
            elif path not in self.files and r[2] & 16:
                self.files[path] = bytearray()
            if path not in self.files:
                result = 4
            else:
                self.handles[r[0]] = [path, 0, r[2]]
                uc.mem_write(r[0] + 12, word(len(self.files[path])))
        elif name == "READ":
            path, offset, mode = self.handles[r[0]]
            if self.read_error and path == LIBRARY and offset >= 4096:
                result = 1
            else:
                data = self.files[path][offset:offset + r[2]]
                uc.mem_write(r[1], bytes(data))
                uc.mem_write(r[3], word(len(data)))
                self.handles[r[0]][1] += len(data)
        elif name == "SEEK":
            self.handles[r[0]][1] = r[1]
        elif name == "WRITE":
            path, offset, mode = self.handles[r[0]]
            assert mode & 2
            length = r[2] - int(self.short_write)
            self.files[path][offset:offset + length] = uc.mem_read(r[1], length)
            self.handles[r[0]][1] += length
            uc.mem_write(r[3], word(length))
            self.writes.append((path, offset, length))
        elif name == "CLOSE":
            self.handles.pop(r[0])
            self.close_count += 1
            if self.close_count == self.close_error_at:
                result = self.close_error_status
        elif name == "UNLINK":
            if self.unlink_error:
                result = 1
            else:
                self.files.pop(self.string(r[0]), None)
        uc.reg_write(R.UC_ARM_REG_R0, result)
        uc.reg_write(R.UC_ARM_REG_PC, uc.reg_read(R.UC_ARM_REG_LR))

    def assert_aligned(self, uc):
        assert uc.reg_read(R.UC_ARM_REG_SP) % 8 == 0

    def reader(self, uc, *_):
        self.assert_aligned(uc)
        at, destination, length = [uc.reg_read(R.UC_ARM_REG_R0 + i) for i in (1, 2, 3)]
        data = self.source[at:at + length]
        uc.mem_write(destination, data)
        uc.reg_write(R.UC_ARM_REG_R0, 0)
        uc.reg_write(R.UC_ARM_REG_R1, len(data))
        uc.reg_write(R.UC_ARM_REG_PC, uc.reg_read(R.UC_ARM_REG_LR))

    def call(self, name, *args):
        for index in range(4, 12):
            self.uc.reg_write(R.UC_ARM_REG_R0 + index, 0xA000 + index)
        for i, value in enumerate(args):
            self.uc.reg_write(R.UC_ARM_REG_R0 + i, value)
        self.uc.reg_write(R.UC_ARM_REG_SP, STACK)
        self.uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        self.uc.emu_start(self.symbols[name], TRAP, count=30_000_000)
        assert self.uc.reg_read(R.UC_ARM_REG_PC) == TRAP
        assert self.uc.reg_read(R.UC_ARM_REG_SP) == STACK
        for index in range(4, 12):
            assert self.uc.reg_read(R.UC_ARM_REG_R0 + index) == 0xA000 + index
        return self.uc.reg_read(R.UC_ARM_REG_R0)

    def recover(self):
        return self.call("store_recover", self.path)


class Recovery(unittest.TestCase):
    def original(self):
        return bytes(header()) + b"RIFF" + bytes(range(128)) * 8

    def test_no_journal_changes_nothing(self):
        old = self.original()
        machine = Machine(old)
        self.assertEqual(machine.recover(), 0)
        self.assertEqual(machine.files[LIBRARY], old)
        self.assertEqual(machine.writes, [])

    def test_verified_append_repairs_a_torn_index_sector(self):
        old = self.original()
        payload = b"RIFF" + bytes(range(256)) * 600
        journal, new_header = transaction(old, payload)
        library = bytearray(old + payload)
        library[1536:2048] = b"\xA5" * 512
        machine = Machine(library, journal)
        self.assertEqual(machine.recover(), 0)
        self.assertEqual(machine.files[LIBRARY], new_header + old[4096:] + payload)
        self.assertNotIn(JOURNAL, machine.files)
        self.assertEqual(machine.recover(), 0)

    def test_a_bad_or_short_append_restores_the_old_header(self):
        old = self.original()
        payload = b"RIFF" + bytes(range(256)) * 600
        journal, new_header = transaction(old, payload)
        for tail in (payload[:-1], payload[:-1] + b"X"):
            machine = Machine(new_header + old[4096:] + tail, journal)
            self.assertEqual(machine.recover(), 0)
            self.assertEqual(machine.files[LIBRARY][:4096], old[:4096])
            self.assertNotIn(JOURNAL, machine.files)

    def test_delete_recovery_does_not_remove_the_audio_blocks(self):
        old = self.original()
        journal, new_header = transaction(old, delete=True)
        machine = Machine(old, journal)
        self.assertEqual(machine.recover(), 0)
        self.assertEqual(machine.files[LIBRARY], new_header + old[4096:])

    def test_bad_journal_and_foreign_header_are_refused_without_writes(self):
        old = self.original()
        journal, _ = transaction(old)
        bad = bytearray(journal)
        bad[100] ^= 1
        changed = bytearray(old)
        changed[20] ^= 1
        for library, record in ((old, bad), (changed, journal), (old, journal[:-1])):
            machine = Machine(library, record)
            self.assertNotEqual(machine.recover(), 0)
            self.assertEqual(machine.writes, [])
            self.assertIn(JOURNAL, machine.files)


    def test_io_errors_keep_the_journal(self):
        old = self.original()
        payload = b"RIFF" + bytes(range(256)) * 600
        journal, _ = transaction(old, payload)
        for problem in ("read_error", "short_write"):
            machine = Machine(old + payload, journal)
            setattr(machine, problem, True)
            self.assertNotEqual(machine.recover(), 0)
            self.assertIn(JOURNAL, machine.files)


class Store(unittest.TestCase):
    def test_automatic_slot_selection_uses_the_card_index(self):
        old = sampleset.build({500: ("on card", 100), 501: ("also on card", 200)})
        machine = Machine(old)
        self.assertEqual(machine.call("store_select", machine.path, 0xFFFFFFFF), 0)
        self.assertEqual(machine.uc.reg_read(R.UC_ARM_REG_R1), 502)
        self.assertEqual(machine.writes, [])
        self.assertEqual(machine.files[LIBRARY], old)

    def test_selection_of_a_replacement_or_missing_library_does_not_write(self):
        machine = Machine(sampleset.build({500: ("old", 100)}))
        self.assertEqual(machine.call("store_select", machine.path, 500), 0)
        self.assertEqual(machine.uc.reg_read(R.UC_ARM_REG_R1), 500)
        machine.files.pop(LIBRARY)
        self.assertEqual(machine.call("store_select", machine.path, 0xFFFFFFFF), 0)
        self.assertEqual(machine.uc.reg_read(R.UC_ARM_REG_R1), 500)
        self.assertEqual(machine.writes, [])

    def test_damaged_index_and_failed_close_do_not_choose_a_slot(self):
        old = sampleset.build({500: ("old", 100)})
        for problem in ("signature", "offset", "close"):
            with self.subTest(problem=problem):
                machine = Machine(old)
                if problem == "signature":
                    machine.files[LIBRARY][0] ^= 1
                elif problem == "offset":
                    struct.pack_into("<I", machine.files[LIBRARY], 2016, len(old) - 1)
                else:
                    machine.close_error_at = 1
                self.assertNotEqual(machine.call("store_select", machine.path, 0xFFFFFFFF), 0)
                self.assertEqual(machine.uc.reg_read(R.UC_ARM_REG_R1), 0xFFFFFFFF)
                self.assertEqual(machine.writes, [])

    def test_full_index_and_invalid_replacement_are_refused(self):
        old = bytearray(sampleset.build({500: ("old", 100)}))
        for slot in range(500, 999):
            struct.pack_into("<I", old, 16 + slot * 4, 4096)
        machine = Machine(old)
        for slot in (0xFFFFFFFF, 499, 999):
            with self.subTest(slot=slot):
                self.assertNotEqual(machine.call("store_select", machine.path, slot), 0)
                self.assertEqual(machine.uc.reg_read(R.UC_ARM_REG_R1), 0xFFFFFFFF)
                self.assertEqual(machine.writes, [])

    def test_native_offsets_cross_protocol_boundaries_without_large_buffers(self):
        old = sampleset.build({500: ("old", 100), 501: ("other", 200)})
        entry = sampleset.wav(500, "new", 100)
        for size in (0x10000000, 0x40000000, 0x80000000, 0xFFFFFFFF - len(entry)):
            with self.subTest(size=size):
                machine = Machine(SparseFile(old, size))
                machine.source = entry
                self.assertEqual(machine.call("store_put", machine.path, machine.descriptor,
                                              500, len(entry)), 0)
                actual = machine.files[LIBRARY]
                self.assertEqual(len(actual), size + len(entry))
                self.assertEqual(struct.unpack_from("<I", actual[:4096], 2016)[0], size)
                self.assertEqual(actual[size:size + len(entry)], entry)
                self.assertEqual(actual[4096:len(old)], old[4096:])
                self.assertNotIn(JOURNAL, machine.files)

    def test_native_file_size_overflow_is_refused_before_writes(self):
        old = sampleset.build({500: ("old", 100)})
        entry = sampleset.wav(500, "new", 100)
        machine = Machine(SparseFile(old, 0xFFFFFFFF - len(entry) + 1))
        machine.source = entry
        self.assertNotEqual(machine.call("store_put", machine.path, machine.descriptor,
                                         500, len(entry)), 0)
        self.assertEqual(machine.writes, [])

    def test_every_close_failure_keeps_a_recoverable_index(self):
        old = sampleset.build({500: ("old", 100), 501: ("other", 200)})
        old_index = struct.unpack_from("<I", old, 2016)[0]
        for phase in range(1, 7):
            with self.subTest(close=phase):
                machine = Machine(old)
                machine.source = sampleset.wav(500, "new", 100)
                machine.close_error_at = phase
                self.assertNotEqual(machine.call("store_put", machine.path, machine.descriptor,
                                                 500, len(machine.source)), 0)
                self.assertEqual(machine.files[LIBRARY][4096:len(old)], old[4096:])
                actual_index = struct.unpack_from("<I", machine.files[LIBRARY], 2016)[0]
                self.assertEqual(actual_index, len(old) if phase >= 5 else old_index)
                self.assertEqual(JOURNAL in machine.files, phase >= 3)
                machine.close_error_at = None
                self.assertEqual(machine.recover(), 0)
                recovered_index = struct.unpack_from("<I", machine.files[LIBRARY], 2016)[0]
                self.assertEqual(recovered_index, len(old) if phase >= 3 else old_index)
                self.assertNotIn(JOURNAL, machine.files)

    def test_failed_journal_removal_does_not_report_success(self):
        old = sampleset.build({500: ("old", 100), 501: ("other", 200)})
        machine = Machine(old)
        machine.source = sampleset.wav(500, "new", 100)
        machine.unlink_error = True
        self.assertNotEqual(machine.call("store_put", machine.path, machine.descriptor,
                                         500, len(machine.source)), 0)
        self.assertIn(JOURNAL, machine.files)
        self.assertEqual(machine.files[LIBRARY][4096:len(old)], old[4096:])
        self.assertEqual(struct.unpack_from("<I", machine.files[LIBRARY], 2016)[0], len(old))
        machine.unlink_error = False
        self.assertEqual(machine.recover(), 0)
        self.assertNotIn(JOURNAL, machine.files)

    def test_a_slot_is_appended_and_committed_without_rewriting_other_audio(self):
        old = sampleset.build({500: ("old", 100), 501: ("other", 200)})
        machine = Machine(old)
        machine.source = sampleset.wav(500, "new", 70000)
        self.assertEqual(machine.call("store_put", machine.path, machine.descriptor, 500, len(machine.source)), 0)
        actual = machine.files[LIBRARY]
        self.assertEqual(actual[4096:len(old)], old[4096:])
        self.assertEqual(actual[len(old):], machine.source)
        self.assertEqual(struct.unpack_from("<I", actual, 16 + 500 * 4)[0], len(old))
        writes = [(at, length) for path, at, length in machine.writes if path == LIBRARY]
        self.assertEqual(sum(length for at, length in writes), len(machine.source) + 4)
        self.assertNotIn(JOURNAL, machine.files)

    def test_deleting_changes_only_the_index(self):
        old = sampleset.build({500: ("old", 100), 501: ("other", 200)})
        machine = Machine(old)
        self.assertEqual(machine.call("store_delete", machine.path, 500), 0)
        self.assertEqual(machine.files[LIBRARY][4096:], old[4096:])
        self.assertEqual(struct.unpack_from("<I", machine.files[LIBRARY], 16 + 500 * 4)[0], 0)
        self.assertEqual([(at, length) for path, at, length in machine.writes if path == LIBRARY], [(2016, 4)])
        self.assertNotIn(JOURNAL, machine.files)

    def test_first_import_creates_a_library_when_the_directory_exists(self):
        machine = Machine(b"")
        machine.files.pop(LIBRARY)
        machine.source = sampleset.wav(500, "new", 100)
        self.assertEqual(machine.call("store_put", machine.path, machine.descriptor, 500, len(machine.source)), 0)
        self.assertEqual(machine.files[LIBRARY][4096:], machine.source)

    def test_invalid_sources_and_slots_never_modify_the_existing_library(self):
        old = sampleset.build({500: ("old", 100)})
        for slot, data in ((499, sampleset.wav(499, "wrong", 100)), (500, bytes(2000)),
                           (500, sampleset.wav(501, "wrong slot", 100))):
            machine = Machine(old)
            machine.source = data
            self.assertNotEqual(machine.call("store_put", machine.path, machine.descriptor, slot, len(data)), 0)
            self.assertEqual(machine.writes, [])

    def test_unsupported_pcm_sources_are_refused_before_writes(self):
        old = sampleset.build({500: ("old", 100)})
        for at, value in ((20, 3), (22, 3), (34, 8)):
            machine = Machine(old)
            data = bytearray(sampleset.wav(500, "new", 100))
            data[at] = value
            machine.source = bytes(data)
            self.assertNotEqual(machine.call("store_put", machine.path, machine.descriptor, 500, len(data)), 0)
            self.assertEqual(machine.writes, [])

if __name__ == "__main__":
    unittest.main()
