# SPDX-License-Identifier: GPL-2.0-only
"""Executable research contracts; these tests do not execute firmware."""

import importlib
import json
from pathlib import Path
import subprocess
import struct
import unittest

try:
    contract = importlib.import_module("tools.patch.project_contract")
except ModuleNotFoundError as error:
    if error.name != "tools.patch.project_contract":
        raise
    contract = None

ROOT = Path(__file__).resolve().parents[2]
BLOCK = 0x4000
BANK_BYTES = 250 * BLOCK


def bank(label):
    data = bytearray(BANK_BYTES)
    for index in range(250):
        at = index * BLOCK
        data[at:at + 8] = b"PTST\x00\x40\x00\x00"
        name = f"{label}-{index:03}".encode("ascii")
        data[at + 16:at + 16 + len(name)] = name
        data[at + 0x3BFC:at + 0x3C00] = b"PTED"
    return bytes(data)


def pattern_file(data):
    prefix = bytearray(0x10100)
    prefix[:4] = b"KORG"
    prefix[16:25] = b"e2sampler"
    prefix[0x100:0x104] = b"GLST"
    prefix[0x1FC:0x200] = b"GLED"
    return bytes(prefix) + data


class ContractCase(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(contract, "The project research contract is not implemented")


class ProjectDifferenceTests(ContractCase):
    @classmethod
    def setUpClass(cls):
        cls.a = bank("A")

    def test_flash_equal_has_no_writes_even_when_ram_differs(self):
        live_ram = bank("unsaved")
        self.assertNotEqual(live_ram, self.a)
        self.assertEqual(contract.changed_slots(self.a, self.a), [])

    def test_only_one_different_slot_is_selected(self):
        candidate = bytearray(self.a)
        candidate[137 * BLOCK + 34] ^= 1
        self.assertEqual(contract.changed_slots(self.a, candidate), [137])

    def test_every_slot_including_last_can_differ(self):
        self.assertEqual(contract.changed_slots(self.a, bank("B")), list(range(250)))

    def test_invalid_bank_lengths_are_rejected(self):
        for left, right in ((self.a[:-1], self.a), (self.a, self.a + b"x"), (b"", b"")):
            with self.subTest(lengths=(len(left), len(right))), self.assertRaises(ValueError):
                contract.changed_slots(left, right)

    def test_pattern_file_preserves_records_and_ignores_globals(self):
        raw = bytearray(pattern_file(self.a))
        raw[0x140] = 0xA7
        self.assertEqual(contract.pattern_bank(raw), self.a)

    def test_pattern_header_and_each_record_frame_are_checked(self):
        good = pattern_file(self.a)
        for offset in (0, 4, 16, 25, 0x10100, 0x10100 + BLOCK + 4, 0x10100 + 249 * BLOCK + 0x3BFC):
            raw = bytearray(good)
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                contract.pattern_bank(raw)

    def test_truncated_and_extended_pattern_files_are_rejected(self):
        good = pattern_file(self.a)
        for raw in (good[:-1], good + b"x"):
            with self.assertRaises(ValueError):
                contract.pattern_bank(raw)


class ProjectBoundsTests(ContractCase):
    def test_ranges_cannot_wrap_or_cross_the_source(self):
        for values in ((-1, 2, 10), (1, -1, 10), (9, 2, 10), (0xFFFFFFF0, 32, 0xFFFFFFFF),
                       (True, 1, 4), (0, 0x100000000, 0xFFFFFFFF)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                contract.bounded_range(*values)
        self.assertEqual(contract.bounded_range(8, 2, 10), (8, 10))

    def test_direct_child_project_names_include_spaces(self):
        self.assertEqual(contract.project_path("B live 02", "e2sSample.all", capacity=128),
                         "SD:KORG/blechtribe/Projects/B live 02/e2sSample.all")

    def test_traversal_and_invalid_names_are_rejected(self):
        for name in ("", ".", "..", "../A", "A/B", "A\\B", "SD:A", "A\x00B", "A.", " A", "A ", "A*"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                contract.project_path(name, "e2sSample.all", capacity=128)
        with self.assertRaises(ValueError):
            contract.project_path("A", "../e2sSample.all", capacity=128)

    def test_capacity_counts_the_terminating_nul(self):
        path = contract.project_path("A", "e2sPattern.all", capacity=128)
        with self.assertRaises(ValueError):
            contract.project_path("A", "e2sPattern.all", capacity=len(path.encode("utf8")))


class ProjectSourceTests(ContractCase):
    def test_every_consumed_range_is_bound_to_preflight_bytes(self):
        source = b"header-PCM-0123456789"
        identity = contract.SourceIdentity.from_ranges(source, [(0, 7), (7, 4), (11, 10)])
        for offset, length in ((7, 4), (0, 7), (11, 10)):
            identity.observe(offset, source[offset:offset + length])
        self.assertTrue(identity.complete())

    def test_same_length_mutation_is_latched_even_after_source_changes_back(self):
        source = b"AAAA"
        identity = contract.SourceIdentity.from_ranges(source, [(0, 4)])
        identity.observe(0, source)
        with self.assertRaises(ValueError):
            identity.observe(0, b"BBBB")
        with self.assertRaises(ValueError):
            identity.observe(0, source)
        with self.assertRaises(ValueError):
            identity.complete()

    def test_unchecked_reads_and_incomplete_coverage_fail(self):
        identity = contract.SourceIdentity.from_ranges(b"12345678", [(0, 4), (4, 4)])
        with self.assertRaises(ValueError):
            identity.complete()
        with self.assertRaises(ValueError):
            identity.observe(1, b"2345")

    def test_range_contract_is_bounded(self):
        with self.assertRaises(ValueError):
            contract.SourceIdentity.from_ranges(b"1234", [(0, 5)])
        with self.assertRaises(ValueError):
            contract.SourceIdentity.from_ranges(b"1234", [(0, 1), (1, 1)], max_ranges=1)


class ProjectOperationTests(ContractCase):
    @classmethod
    def setUpClass(cls):
        cls.a = bank("A")
        cls.aprime = bytearray(cls.a)
        cls.aprime[9 * BLOCK + 34] = 73
        cls.aprime = bytes(cls.aprime)

    def capture(self, operation, flash=None, ram=None):
        operation.capture(flash=self.aprime if flash is None else flash,
                          ram=self.a if ram is None else ram,
                          editor=self.a[:BLOCK], selection=9, mfx=b"dirty-MFX")

    def test_no_snapshot_before_confirmation_and_exclusive_owner(self):
        operation = contract.ImportOperation()
        operation.confirmation()
        with self.assertRaises(ValueError):
            self.capture(operation)

    def test_snapshot_budget_includes_bounded_source_fingerprints(self):
        operation = contract.ImportOperation()
        operation.acquire(operation.confirmation())
        leaves_no_source_space = bytes(contract.ARENA_LIMIT - contract.SNAPSHOT_BYTES)
        with self.assertRaises(ValueError):
            operation.capture(flash=self.aprime, ram=self.a, editor=self.a[:BLOCK],
                              selection=9, mfx=leaves_no_source_space)

    def test_write_and_selection_during_confirmation_require_reconfirmation(self):
        operation = contract.ImportOperation()
        token = operation.confirmation()
        operation.mutation("WRITE")
        operation.mutation("pattern-select")
        with self.assertRaises(ValueError):
            operation.acquire(token)
        operation.acquire(operation.confirmation())
        self.capture(operation)
        self.assertEqual(operation.flash_before, self.aprime)
        self.assertTrue(operation.locked)

    def test_write_is_normal_outside_operation_and_serialized_inside(self):
        operation = contract.ImportOperation()
        operation.mutation("WRITE")
        operation.acquire(operation.confirmation())
        for action in ("WRITE", "second-import", "pattern-select", "sample", "plugin-file"):
            with self.subTest(action=action), self.assertRaises(ValueError):
                operation.mutation(action)

    def test_failed_write_is_marked_before_result_and_uses_flash_not_stale_sd(self):
        operation = contract.ImportOperation()
        operation.acquire(operation.confirmation())
        self.capture(operation)
        operation.mark_attempt(9)
        partial = bytearray(self.aprime)
        partial[9 * BLOCK + 100] ^= 0xFF
        restoration = operation.rollback_targets(partial)
        self.assertEqual(restoration, {9: self.aprime[9 * BLOCK:10 * BLOCK]})
        self.assertNotEqual(restoration[9], self.a[9 * BLOCK:10 * BLOCK])

    def test_attempt_marks_slot_before_calling_a_failing_writer(self):
        operation = contract.ImportOperation()
        operation.acquire(operation.confirmation())
        self.capture(operation)

        def failing_writer(index):
            self.assertIn(index, operation.touched)
            raise OSError("simulated partial program failure")

        with self.assertRaises(OSError):
            operation.attempt(9, failing_writer)
        self.assertEqual(operation.touched, {9})

    def test_failed_recovery_stays_locked_and_cannot_report_success(self):
        operation = contract.ImportOperation()
        operation.acquire(operation.confirmation())
        self.capture(operation)
        with self.assertRaises(ValueError):
            operation.recovered(self.a)
        self.assertTrue(operation.locked)
        with self.assertRaises(ValueError):
            operation.mutation("WRITE")

    def test_verified_recovery_reloads_editor_from_authoritative_flash(self):
        operation = contract.ImportOperation()
        operation.acquire(operation.confirmation())
        self.capture(operation)
        restored = operation.recovered(self.aprime)
        self.assertEqual(restored["bank"], self.aprime)
        self.assertEqual(restored["editor"], self.aprime[9 * BLOCK:10 * BLOCK])
        self.assertEqual(restored["mfx"], b"dirty-MFX")
        self.assertFalse(operation.locked)
        operation.mutation("WRITE")

    def test_slot_indices_are_bounded(self):
        operation = contract.ImportOperation()
        operation.acquire(operation.confirmation())
        self.capture(operation)
        for index in (-1, 250, True):
            with self.subTest(index=index), self.assertRaises(ValueError):
                operation.mark_attempt(index)


class ProjectOwnershipTests(ContractCase):
    @classmethod
    def setUpClass(cls):
        code = """import fs from 'node:fs'; import protectedMap from './data/protected.mjs';
import { selectFor } from './src/patch.mjs';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const result={physicalStart:protectedMap.ram.window.start,physicalBytes:protectedMap.ram.mirror.distance,owners:{}};
for(const build of ['stock','hacktribe','synth']){
 const set=read(build==='synth'?'data/patches/blech-synth.json':'data/patches/blech.json');
 const patches=selectFor(set.patches.map(read),build).patches;
 result.owners[build]=[...protectedMap.regions.filter(r=>r.space==='ram').map(r=>({start:r.start,end:r.end,name:r.id})),
 ...patches.flatMap(p=>(p.ram??[]).map(r=>({start:Number(r.at),end:Number(r.at)+r.length,name:p.id})))];
} console.log(JSON.stringify(result));"""
        cls.maps = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", code], cwd=ROOT, text=True))

    def test_candidate_above_native_owners_fits_declarations_only(self):
        self.assertEqual(contract.RAM_START, self.maps["physicalStart"])
        self.assertEqual(contract.RAM_END - contract.RAM_START, self.maps["physicalBytes"])
        for build, owners in self.maps["owners"].items():
            with self.subTest(build=build):
                self.assertEqual(contract.project_area_errors(0xC3000000, 13 * 1024 * 1024, owners), [])

    def test_sample_buffer_and_patch_owner_collisions_are_rejected(self):
        owners = self.maps["owners"]["hacktribe"]
        self.assertTrue(contract.project_area_errors(0xC1000000, 13 * 1024 * 1024, owners))
        occupied = owners + [dict(start=0xC3000000, end=0xC3001000, name="another-owner")]
        self.assertTrue(any("another-owner" in error for error in
                            contract.project_area_errors(0xC3000000, 13 * 1024 * 1024, occupied)))

    def test_upper_mirror_overflow_and_budget_excess_are_rejected(self):
        owners = self.maps["owners"]["stock"]
        for start, length in ((0xC4000000, 13 * 1024 * 1024), (0xC3800000, 13 * 1024 * 1024),
                              (0xC3000000, 14 * 1024 * 1024), (0xFFFFFFF0, 0x1000000),
                              (0xC3000000, 4096)):
            with self.subTest(start=start, length=length):
                self.assertTrue(contract.project_area_errors(start, length, owners))

    def test_arena_must_also_reserve_source_fingerprint_metadata(self):
        self.assertTrue(contract.project_area_errors(0xC3000000, contract.SNAPSHOT_BYTES,
                                                   self.maps["owners"]["stock"]))


class NativeSampleReadPlanTests(ContractCase):
    """Expected file ranges come from WAV metadata and the documented native walk."""

    def setUp(self):
        super().setUp()
        self.assertTrue(callable(getattr(contract, "native_sample_read_ranges", None)),
                        "Metadata-derived native sample read planning is not implemented")
        self.read_plan = contract.native_sample_read_ranges
        from tools.emu import sampleset
        self.samples = sampleset

    def file(self, frames=8192, kind="pcm16", slot=500):
        return self.samples.build({slot: ("OWN", frames, 48000, kind)})

    def wrap(self, chunks):
        head = bytearray(self.samples.build({}))
        struct.pack_into("<I", head, 16 + 500 * 4, 4096)
        body = b"WAVE" + chunks
        return bytes(head) + b"RIFF" + struct.pack("<I", len(body)) + body

    def test_canonical_read_plan_is_metadata_derived_and_unique(self):
        self.assertEqual(self.read_plan(self.file()), [
            (0, 4096), (4096, 8), (4104, 4), (4108, 8), (4132, 8),
            (20524, 8), (20532, 8), (4116, 16), (20540, 1172), (4140, 16384),
        ])

    def test_pcm16_splits_at_64k_input_bytes(self):
        ranges = self.read_plan(self.file(32769))
        self.assertIn((4140, 65536), ranges)
        self.assertIn((4140 + 65536, 2), ranges)

    def test_stereo16_reads_interleaved_input_without_halving_length(self):
        self.assertIn((4140, 4 * 17), self.read_plan(self.file(17, "stereo16")))

    def test_pcm24_uses_96k_input_and_does_not_align_odd_chunk_sizes(self):
        ranges = self.read_plan(self.file(32769, "pcm24"))
        self.assertIn((4140, 98304), ranges)
        self.assertIn((4140 + 98304, 3), ranges)
        self.assertIn((4096 + 44 + 3 * 32769, 8), ranges)

    def test_empty_bank_has_only_the_native_table_read(self):
        self.assertEqual(self.read_plan(self.samples.build({})), [(0, 4096)])

    def test_last_reachable_slot_is_998(self):
        self.assertIn((4140, 2), self.read_plan(self.file(1, slot=998)))

    def test_native_ignored_table_entries_are_rejected(self):
        for slot in (999, 1000, 1019):
            data = bytearray(self.file(1))
            struct.pack_into("<I", data, 16 + slot * 4, 4096)
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                self.read_plan(data)

    def test_invalid_all_header_and_truncated_wave_are_rejected(self):
        for data in (bytes(4096), self.file()[:-1], self.file()[:4090]):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                self.read_plan(data)

    def test_riff_overflow_is_rejected(self):
        data = bytearray(self.file(1))
        struct.pack_into("<I", data, 4100, 0xFFFFFFFF)
        with self.assertRaises(ValueError):
            self.read_plan(data)

    def test_unsupported_sample_formats_are_rejected_before_native_load(self):
        for kind in ("pcm8", "pcm32", "float32"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.read_plan(self.file(16, kind))

    def test_duplicate_fmt_header_is_ambiguous(self):
        wave = self.file(16)[4096:]
        chunks = wave[12:] + wave[12:36]
        with self.assertRaises(ValueError):
            self.read_plan(self.wrap(chunks))

    def test_missing_esli_is_unsupported_for_whole_sample_sets(self):
        wave = self.file(16)[4096:]
        with self.assertRaises(ValueError):
            self.read_plan(self.wrap(wave[12:44 + 32]))

    def test_duplicate_slot_offsets_are_rejected(self):
        data = bytearray(self.file(16))
        struct.pack_into("<I", data, 16 + 501 * 4, 4096)
        with self.assertRaises(ValueError):
            self.read_plan(data)

    def test_record_index_must_match_its_table_slot(self):
        data = bytearray(self.file(16))
        struct.pack_into("<H", data, 4096 + 60 + 32, 501)
        with self.assertRaises(ValueError):
            self.read_plan(data)

    def test_unbounded_chunk_metadata_is_rejected(self):
        wave = self.file(16)[4096:]
        junk = b"JUNK" + struct.pack("<I", 0)
        with self.assertRaises(ValueError):
            self.read_plan(self.wrap(junk * 16384 + wave[12:]))

    def test_full_user_bank_exceeds_old_4096_range_limit(self):
        data = self.samples.build({slot: ("OWN", 1) for slot in range(500, 999)})
        ranges = self.read_plan(data)
        self.assertEqual(len(ranges), 1 + 9 * 499)
        identity = contract.SourceIdentity.from_ranges(data, ranges)
        for offset, length in ranges:
            identity.observe(offset, data[offset:offset + length])
        self.assertTrue(identity.complete())

    def test_serialized_fingerprint_budget_fits_beside_three_banks(self):
        self.assertEqual(contract.NATIVE_SAMPLE_MAX_RANGES, 16384)
        self.assertEqual(contract.SOURCE_IDENTITY_BYTES, 16384 * 40 + 2048)
        self.assertLessEqual(contract.SNAPSHOT_BYTES + contract.SOURCE_IDENTITY_BYTES, contract.ARENA_LIMIT)


if __name__ == "__main__":
    unittest.main()
