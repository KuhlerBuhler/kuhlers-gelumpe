"""Generated ARM926 table candidates, without firmware or hardware."""
import importlib
import importlib.util
import struct
import unittest
from unittest.mock import patch

import sample_ram_canary as canary


class Tables(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('sample_ram_mmu'), 'the diagnostic module is required')
        self.m = importlib.import_module('sample_ram_mmu')
        self.cpu = dict(operation='info', control=0x5107D, ttbr=0xC200003F,
                        domain_control=0xFFFFFFFF, fcse=0x02000000, cpu_id=0x41069265,
                        cache_type=0x1D112152, dtcm_region=0xA, itcm_region=0x1000C)
        self.table = bytearray(0x4000)
        for index in range(0xC00, 0xC40):
            struct.pack_into('<I', self.table, index * 4, index << 20 | 0xC12)

    def test_section_candidates_clip_the_range_and_decode_attributes(self):
        struct.pack_into('<I', self.table, 0xC27 * 4, 0xC2700C1E)
        result = self.m.decode_table(self.table, 0xC2000000, self.cpu)
        self.assertTrue(result['table_alias_consistent'])
        self.assertFalse(result['effective_mapping_proven'])
        self.assertEqual(result['regions'][0], dict(start=canary.START, end=0xC2800000,
            descriptor=0xC2700C1E, kind='section', resolved=True, physical_start=canary.START,
            physical_end=0xC2800000, identity=True, cacheable=True, bufferable=True,
            domain=0, domain_access='manager', ap=3, policy='write_back'))
        self.assertEqual(result['regions'][-1]['end'], canary.END)
        self.assertEqual(sum(r['end'] - r['start'] for r in result['regions']), canary.END - canary.START)
        self.assertEqual(result['regions'][1]['policy'], 'uncached_unbuffered')

    def test_coarse_fine_and_faults_remain_unresolved(self):
        for descriptor, kind in [(0, 'fault'), (0xC1000011, 'coarse'), (0xC1000013, 'fine')]:
            with self.subTest(kind=kind):
                struct.pack_into('<I', self.table, 0xC27 * 4, descriptor)
                row = self.m.decode_table(self.table, 0xC2000000, self.cpu)['regions'][0]
                self.assertEqual(row['kind'], kind)
                self.assertFalse(row['resolved'])
                self.assertNotIn('physical_start', row)

    def test_reserved_or_missing_section_bits_are_not_accepted(self):
        for descriptor in (0xC2700C02, 0xC2700E12, 0xC2701C12, 0xC2740C12):
            with self.subTest(descriptor=hex(descriptor)):
                struct.pack_into('<I', self.table, 0xC27 * 4, descriptor)
                row = self.m.decode_table(self.table, 0xC2000000, self.cpu)['regions'][0]
                self.assertEqual(row['kind'], 'invalid_section')
                self.assertFalse(row['resolved'])

    def test_a_wrong_alias_is_explicitly_inconsistent(self):
        struct.pack_into('<I', self.table, 0xC20 * 4, 0xC2100C12)
        result = self.m.decode_table(self.table, 0xC2000000, self.cpu)
        self.assertFalse(result['table_alias_consistent'])
        self.assertFalse(result['effective_mapping_proven'])

    def test_relocated_sections_do_not_appear_identity_mapped(self):
        struct.pack_into('<I', self.table, 0xC27 * 4, 0xC1200C12)
        row = self.m.decode_table(self.table, 0xC2000000, self.cpu)['regions'][0]
        self.assertFalse(row['identity'])
        self.assertEqual(row['physical_start'], 0xC124F000)

    def test_other_cpus_and_truncated_tables_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ARM926'):
            self.m.decode_table(self.table, 0xC2000000, {**self.cpu, 'cpu_id': 0x410FC090})
        with self.assertRaisesRegex(ValueError, '16 KiB'):
            self.m.decode_table(self.table[:-4], 0xC2000000, self.cpu)

    def test_a_physical_ttbr_is_never_automatically_used_as_a_virtual_pointer(self):
        class Reader:
            def read(self, address, size):
                raise AssertionError('no explicit virtual alias was supplied')
        result = self.m.inspect_layout(Reader(), self.cpu, None)
        self.assertEqual(result['status'], 'not_read')
        self.assertEqual(result['table_physical'], 0xC2000000)

    def test_unaligned_or_non_dram_aliases_are_rejected_before_read(self):
        class Reader:
            def read(self, address, size):
                raise AssertionError('invalid alias must not reach READ')
        for address in (0, 0x80020000, 0xC2001000, 0xC4000000):
            with self.subTest(address=hex(address)), self.assertRaisesRegex(ValueError, 'virtual table'):
                self.m.inspect_layout(Reader(), self.cpu, address)

    def test_the_table_is_read_twice_and_changes_abort_decoding(self):
        reads, table = [], bytes(self.table)
        class Reader:
            def read(self, address, size):
                reads.append((address, size))
                return table if len(reads) == 1 else bytes(len(table))
        with patch.object(canary, 'quiescent'), self.assertRaisesRegex(ValueError, 'table changed'):
            self.m.inspect_layout(Reader(), self.cpu, 0xC2000000)
        self.assertEqual(reads, [(0xC2000000, 0x4000)] * 2)

    def test_mmu_disabled_does_not_read_an_inactive_table(self):
        class Reader:
            def read(self, address, size):
                raise AssertionError('an inactive table must not be read')
        self.assertEqual(self.m.inspect_layout(Reader(), {**self.cpu, 'control': 0}, 0xC2000000)['status'],
                         'mmu_disabled')

    def test_register_changes_abort_and_each_capture_resets_restoration_state(self):
        states, table = [], bytes(self.table)
        class Reader:
            def read(self, address, size):
                return table
        def capture(link, vsb, operation, emit, restored):
            row = {**self.cpu, 'domain_control': 0} if len(states) > 2 else self.cpu
            emit(row)
            restored()
        with patch.object(canary, 'quiescent'), patch.object(canary, 'measure', side_effect=capture), \
             self.assertRaisesRegex(ValueError, 'CPU registers changed'):
            self.m.diagnose(Reader(), b'', 0xC2000000, restored=states.append)
        self.assertEqual(states, [False, True, False, True])

    def test_unconfirmed_second_capture_does_not_restore_or_continue(self):
        states, calls, table = [], [], bytes(self.table)
        class Reader:
            def read(self, address, size):
                return table
        def capture(link, vsb, operation, emit, restored):
            calls.append(operation)
            if len(calls) == 2:
                raise RuntimeError('EXEC marker unconfirmed')
            emit(self.cpu)
            restored()
        with patch.object(canary, 'quiescent'), patch.object(canary, 'measure', side_effect=capture), \
             self.assertRaisesRegex(RuntimeError, 'unconfirmed'):
            self.m.diagnose(Reader(), b'', 0xC2000000, restored=states.append)
        self.assertEqual(states, [False, True, False])
        self.assertEqual(calls, ['info', 'info'])

    def test_unpredictable_low_ttbr_bits_do_not_change_the_table_base(self):
        states, table = [], bytes(self.table)
        class Reader:
            def read(self, address, size):
                return table
        def capture(link, vsb, operation, emit, restored):
            emit({**self.cpu, 'ttbr': 0xC2000004} if len(states) > 2 else self.cpu)
            restored()
        with patch.object(canary, 'quiescent'), patch.object(canary, 'measure', side_effect=capture):
            result = self.m.diagnose(Reader(), b'', 0xC2000000, restored=states.append)
        self.assertEqual(result['layout']['table_physical'], 0xC2000000)
        self.assertFalse(result['effective_mapping_proven'])

    def test_sram_tables_use_bounded_capture_and_show_the_uncached_mirror(self):
        cpu = {**self.cpu, 'ttbr': 0x8001C03F}
        table = bytearray(0x4000)
        struct.pack_into('<I', table, 0x800 * 4, 0x80000C1E)
        for index in range(0xC00, 0xC40):
            struct.pack_into('<I', table, index*4, index << 20 | 0xC1E)
            struct.pack_into('<I', table, (index+0x40)*4, index << 20 | 0xC12)
        class Reader:
            def read(self, address, size):
                raise AssertionError('BLECH READ cannot access SRAM')
        states, spans = [], []
        def capture(link, vsb, operation, emit, restored, span):
            self.assertEqual(operation, 'table')
            self.assertEqual(span, (0x8001C000, 0x80020000))
            spans.append(span)
            for offset in range(0, len(table), 224):
                part = bytes(table[offset:offset + 224])
                emit(dict(operation='table', start=span[0]+offset, end=span[0]+offset+len(part),
                          ttbr=0x8001C000, control=0x5107D, data=part))
            restored()
        with patch.object(canary, 'quiescent'), patch.object(canary, 'measure', side_effect=capture):
            result = self.m.inspect_layout(Reader(), cpu, 0x8001C000, vsb=b'own generated image', restored=states.append)
        self.assertEqual(len(spans), 2)
        self.assertEqual(states, [False, True, False, True])
        self.assertTrue(result['table_alias_consistent'])
        self.assertTrue(result['mirror_matches_target'])
        self.assertEqual(result['mirror_regions'][0]['physical_start'], canary.START)
        self.assertEqual(result['mirror_regions'][0]['policy'], 'uncached_unbuffered')
        self.assertFalse(result['effective_mapping_proven'])


if __name__ == '__main__':
    unittest.main()
