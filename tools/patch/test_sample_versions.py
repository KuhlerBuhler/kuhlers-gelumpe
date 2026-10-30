"""Version tags identify which indexed entry occupies a physical DSP row."""
import importlib.util
import struct
import unittest

import unicorn
from unicorn import arm_const as R

versions = None
if importlib.util.find_spec('sample_versions') is not None:
    import sample_versions as versions

CODE, TABLE, HEADER, STACK, TRAP = 0xC1000000, 0xC2001000, 0xC2003000, 0xC200F000, 0xC200E000
COUNT = 999


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(versions, 'the physical-row version table is missing')
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.uc.mem_map(CODE, 0x10000)
        self.uc.mem_map(0xC2000000, 0x10000)
        code, self.symbols = versions.build_code(CODE, TABLE, HEADER, count=COUNT)
        self.uc.mem_write(CODE, code)
        self.uc.mem_write(TABLE - 4, b'HEAD' + b'\xFF' * (COUNT * 4) + b'TAIL')
        self.call('versions_clear')

    def call(self, name, *args, cpsr=0x13):
        u = self.uc
        u.reg_write(R.UC_ARM_REG_CPSR, cpsr)
        u.reg_write(R.UC_ARM_REG_SP, STACK)
        for i in range(4, 12):
            u.reg_write(R.UC_ARM_REG_R0 + i, 0xA000 + i)
        for i, value in enumerate(args):
            u.reg_write(R.UC_ARM_REG_R0 + i, value)
        u.reg_write(R.UC_ARM_REG_LR, TRAP)
        u.emu_start(self.symbols[name], TRAP, count=10000)
        self.assertEqual(u.reg_read(R.UC_ARM_REG_PC), TRAP)
        self.assertEqual(u.reg_read(R.UC_ARM_REG_SP), STACK)
        self.assertEqual(u.reg_read(R.UC_ARM_REG_CPSR) & 0xFF, cpsr)
        for i in range(4, 12):
            self.assertEqual(u.reg_read(R.UC_ARM_REG_R0 + i), 0xA000 + i)
        self.assertEqual(bytes(u.mem_read(TABLE - 4, 4)), b'HEAD')
        self.assertEqual(bytes(u.mem_read(TABLE + COUNT * 4, 4)), b'TAIL')
        return u.reg_read(R.UC_ARM_REG_R0)

    def index(self, slot, offset):
        self.uc.mem_write(HEADER + 16 + slot * 4, struct.pack('<I', offset))

    def test_new_table_has_no_saved_versions(self):
        self.index(500, 4096)
        self.assertEqual(self.call('version_get', 500), 0)
        self.assertEqual(self.call('version_matches', 500, 500), 0)

    def test_new_file_version_does_not_match_old_loaded_pcm(self):
        self.index(500, 4096)
        self.assertEqual(self.call('version_set', 600, 4096), 0)
        self.assertEqual(self.call('version_matches', 500, 600), 1)
        self.index(500, 0x123450)
        self.assertEqual(self.call('version_matches', 500, 600), 0)
        self.assertEqual(self.call('version_get', 600), 4096)

    def test_loading_a_new_row_keeps_the_previous_rows_version(self):
        self.index(500, 0x123450)
        self.call('version_set', 600, 4096)
        self.call('version_set', 601, 0x123450)
        self.assertEqual(self.call('version_matches', 500, 600), 0)
        self.assertEqual(self.call('version_matches', 500, 601), 1)
        self.assertEqual(self.call('version_get', 600), 4096)

    def test_aliases_match_the_saved_entry_rather_than_the_logical_number(self):
        self.index(500, 0x23456)
        self.index(602, 0x23456)
        self.call('version_set', 700, 0x23456)
        self.assertEqual(self.call('version_matches', 500, 700), 1)
        self.assertEqual(self.call('version_matches', 602, 700), 1)
        self.index(602, 0x56789)
        self.assertEqual(self.call('version_matches', 602, 700), 0)
        self.assertEqual(self.call('version_matches', 500, 700), 1)

    def test_empty_index_and_unregistered_rows_never_match(self):
        self.assertEqual(self.call('version_matches', 500, 600), 0)
        self.call('version_set', 600, 4096)
        self.assertEqual(self.call('version_matches', 500, 600), 0)
        self.index(500, 4095)
        self.assertEqual(self.call('version_matches', 500, 600), 0)

    def test_clearing_for_a_different_library_forgets_even_equal_offsets(self):
        self.index(500, 4096)
        self.call('version_set', 998, 4096)
        self.assertEqual(self.call('version_matches', 500, 998), 1)
        self.call('versions_clear')
        self.assertEqual(self.call('version_matches', 500, 998), 0)

    def test_single_row_can_be_invalidated_without_changing_others(self):
        self.call('version_set', 500, 4096)
        self.call('version_set', 501, 0x2000)
        self.assertEqual(self.call('version_set', 500, 0), 0)
        self.assertEqual(self.call('version_get', 500), 0)
        self.assertEqual(self.call('version_get', 501), 0x2000)

    def test_unsigned_offsets_and_the_last_real_slot_are_supported(self):
        for offset in (4096, 4097, 0x10000000, 0x80000000, 0xFFFFF000):
            self.index(998, offset)
            self.assertEqual(self.call('version_set', 998, offset), 0)
            self.assertEqual(self.call('version_matches', 998, 998), 1)
            self.assertEqual(self.call('version_get', 998), offset)

    def test_bad_rows_offsets_and_slots_do_not_change_a_recorded_version(self):
        self.call('version_set', 500, 4096)
        for row in (999, 0xFFFFFFFF):
            self.assertNotEqual(self.call('version_set', row, 0x2000), 0)
            self.assertEqual(self.call('version_get', row), 0)
            self.assertEqual(self.call('version_matches', 500, row), 0)
            self.assertEqual(self.call('version_matches', row, 500), 0)
        for offset in (1, 4095):
            self.assertNotEqual(self.call('version_set', 500, offset), 0)
        self.assertEqual(self.call('version_get', 500), 4096)

    def test_irq_mask_is_preserved_on_every_operation(self):
        self.index(500, 4096)
        for mask in (0x13, 0x93):
            self.call('version_set', 600, 4096, cpsr=mask)
            self.call('version_get', 600, cpsr=mask)
            self.call('version_matches', 500, 600, cpsr=mask)
            self.call('versions_clear', cpsr=mask)

    def test_code_and_state_must_not_overlap_or_overflow(self):
        for origin, table, header, count in (
                (CODE + 2, TABLE, HEADER, COUNT), (CODE, TABLE + 1, HEADER, COUNT),
                (CODE, HEADER, HEADER, COUNT), (TABLE, TABLE, HEADER, COUNT),
                (CODE, TABLE, HEADER, 1021), (CODE, 0xFFFFFFFC, HEADER, COUNT),
                (0xFFFFFFFC, TABLE, HEADER, COUNT)):
            with self.subTest(origin=origin, table=table, count=count):
                with self.assertRaises(ValueError):
                    versions.build_code(origin, table, header, count=count)


if __name__ == '__main__':
    unittest.main()
