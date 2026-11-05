"""Physical sample protection on generated ARM code and synthetic tables."""
import struct
import unittest

import arm
import unicorn
from unicorn import arm_const as R
from test_sample_swap import F, Swap, word
import sample_swap as p
import sample_protection as guard
import sample_seek

PLAYBACK = 0xC0362EE8


def alias(swap, logical, physical):
    swap.uc.mem_write(F['NAMES'] + logical * 32 + 30, struct.pack('<H', physical + 50))
    swap.uc.mem_write(p.HDR + 16 + logical * 4, word(0x1000 + logical))
    swap.call('mark_clean', logical, swap.u32(p.PROTECTION_REV))


class PhysicalProtection(unittest.TestCase):
    def test_changed_playback_points_protect_the_physical_row(self):
        for offset in (0, 4, 8, 12):
            with self.subTest(offset=offset):
                s = Swap()
                s.slot(600, base=F['DSP_MIN'], length=0x100)
                s.uc.mem_write(PLAYBACK + 600 * 16 + offset, word(256))
                self.assertEqual(s.call('can_evict', 600), 0)
                self.assertEqual(s.call('victim'), 0)

    def test_a_dirty_alias_protects_the_shared_row_but_not_other_rows(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        alias(s, 601, 600)
        s.slot(602, base=F['DSP_MIN'] + 0x100, length=0x100)
        s.uc.mem_write(F['NAMES'] + 601 * 32 + 12, b'Changed')
        self.assertEqual(s.call('can_evict', 600), 0)
        self.assertEqual(s.call('can_evict', 601), 0)
        self.assertEqual(s.call('can_evict', 602), 1)
        self.assertEqual(s.call('victim'), 602)

    def test_observed_unsaved_changes_do_not_unlock_when_values_return(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        at = PLAYBACK + 600 * 16 + 4
        s.uc.mem_write(at, word(256))
        self.assertEqual(s.call('victim'), 0)
        s.uc.mem_write(at, word(0))
        self.assertEqual(s.call('victim'), 0)

    def test_a_native_replacement_is_dirty_even_with_equal_metadata_and_length(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        alias(s, 601, 600)
        descriptor = 0xC100A000
        s.uc.mem_write(descriptor, struct.pack('<H', 600))
        reached = []

        def native(uc, *_):
            reached.append(uc.reg_read(R.UC_ARM_REG_R0))
            uc.reg_write(R.UC_ARM_REG_PC, uc.reg_read(R.UC_ARM_REG_LR))

        at = s.sym['protect_reserve_native']
        s.uc.hook_add(unicorn.UC_HOOK_CODE, native, begin=at, end=at)
        s.call('protect_reserve', descriptor)
        self.assertEqual(reached, [descriptor])
        self.assertEqual(s.call('slot_clean', 600), 1)
        self.assertEqual(s.call('can_evict', 600), 0)
        self.assertEqual(s.call('can_evict', 601), 0)

    def test_display_getters_do_not_dirty_a_sample(self):
        for label in ('protect_start', 'protect_end', 'protect_loop'):
            for delta in (0, 1, -1):
                with self.subTest(label=label, delta=delta):
                    s = Swap()
                    s.slot(600, base=F['DSP_MIN'], length=0x100)
                    at = s.sym[label + '_native']
                    s.uc.hook_add(unicorn.UC_HOOK_CODE,
                                  lambda uc, *_: uc.reg_write(R.UC_ARM_REG_PC, uc.reg_read(R.UC_ARM_REG_LR)),
                                  begin=at, end=at)
                    s.call(label, 600, delta)
                    self.assertEqual(s.call('can_evict', 600), int(delta == 0))

    def test_a_mutation_after_the_scan_prevents_the_atomic_delete(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        self.assertEqual(s.call('victim'), 600)
        s.call('protection_import', 600)
        self.assertEqual(s.call('evict_prepared', 600), 0)
        self.assertFalse(any(row[0] == F['DELETE'] for row in s.calls))

    def test_revision_exhaustion_cannot_revalidate_an_old_view(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        self.assertEqual(s.call('victim'), 600)
        s.uc.mem_write(p.PROTECTION + guard.REV, word(0xFFFFFFFF))
        s.call('protection_import', 600)
        self.assertEqual(s.call('protection_current'), 0)
        self.assertEqual(s.call('victim'), 0)


class ProtectionBudget(unittest.TestCase):
    def test_free_dsp_space_does_not_require_a_hash_scan_after_slow_io(self):
        s = Swap()
        s.uc.mem_map(F['TIMER'], 4096)
        s.set_state('INSTEP', 1)
        s.set_state('T0', 0)
        s.uc.mem_write(F['TIMER'] + 0x10, word(p.BUDGET))
        self.assertEqual(s.call('place', 32), F['DSP_MIN'])

    def test_a_deferred_scan_runs_before_another_slow_card_parse(self):
        s = Swap()
        s.slot(500, base=F['DSP_MIN'], length=256)
        s.uc.mem_write(s.sym['ss_cap'], word(256))
        s.uc.mem_map(F['TIMER'], 4096)
        s.set_state('INSTEP', 1)
        source = f'''ldr r1, ={F['TIMER'] + 0x10}
        ldr r2, [r1]
        ldr r3, ={p.BUDGET}
        add r2, r2, r3
        str r2, [r1]
        mov r0, #32
        str r0, [r11, #{p.OFF['P_LEN']}]
        mov r0, #16
        str r0, [r11, #{p.OFF['P_BITS']}]
        mov r0, #0
        bx lr
        .pool'''
        s.uc.mem_write(s.sym['parse'], arm.assemble(source, origin=s.sym['parse']).bytes)
        s.uc.hook_add(unicorn.UC_HOOK_CODE,
                      lambda uc, *_: uc.mem_write(F['META'] + 500 * 0x45C + 11, b'\0'),
                      begin=F['DELETE'], end=F['DELETE'])
        s.set_state('T0', 0)
        self.assertEqual(s.call('start_install', 501), 0)
        self.assertEqual(s.state('J_STATE'), 0)
        s.set_state('T0', s.u32(F['TIMER'] + 0x10))
        self.assertEqual(s.call('start_install', 501), 1)
        self.assertEqual(s.state('J_STATE'), 1)
        self.assertEqual(s.state('J_SLOT'), 501)

    def test_many_evictions_share_one_signature_scan(self):
        s = Swap()
        for slot in range(500, 504):
            s.slot(slot, base=F['DSP_MIN'] + (slot - 500) * 32, length=32)
        s.uc.mem_write(s.sym['ss_cap'], word(128))
        hashes, masks = [], []

        def signature(uc, *_):
            hashes.append(uc.reg_read(R.UC_ARM_REG_R0))
            masks.append(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)

        def remove(uc, *_):
            physical = uc.reg_read(R.UC_ARM_REG_R0)
            uc.mem_write(F['META'] + physical * 0x45C + 11, b'\0')

        at = s.sym['slot_sig']
        s.uc.hook_add(unicorn.UC_HOOK_CODE, signature, begin=at, end=at)
        s.uc.hook_add(unicorn.UC_HOOK_CODE, remove, begin=F['DELETE'], end=F['DELETE'])
        self.assertEqual(s.call('place', 128), F['DSP_MIN'])
        self.assertEqual(hashes, list(range(500, 504)))
        self.assertEqual(masks, [0] * 4)

    def test_all_499_user_rows_yield_and_resume_without_rehashing(self):
        s = Swap()
        for slot in range(500, 999):
            s.slot(slot, base=F['DSP_MIN'] + (slot - 500) * 32, length=32)
        s.uc.mem_map(F['TIMER'], 4096)
        s.set_state('INSTEP', 1)
        ticks, seen, masked = [0], [], []

        def signature(uc, *_):
            seen.append(uc.reg_read(R.UC_ARM_REG_R0))
            masked.append(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)
            ticks[0] += p.BUDGET // 4
            uc.mem_write(F['TIMER'] + 0x10, word(ticks[0]))

        at = s.sym['slot_sig']
        s.uc.hook_add(unicorn.UC_HOOK_CODE, signature, begin=at, end=at)
        steps = 0
        while steps < 130:
            s.set_state('T0', ticks[0])
            steps += 1
            if s.call('victim'):
                break
            self.assertLessEqual(len(seen), steps * 4)
        self.assertGreater(steps, 1)
        self.assertLess(steps, 130)
        self.assertEqual(seen, list(range(500, 999)))
        self.assertFalse(any(masked))


class VerifiedBaseline(unittest.TestCase):
    def test_exhaustion_during_hashing_cannot_acknowledge_a_version(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        s.call('protection_import', 600)
        s.uc.mem_write(p.PROTECTION_REV, word(0xFFFFFFFF))
        at = s.sym['slot_sig']
        s.uc.hook_add(unicorn.UC_HOOK_CODE,
                      lambda uc, *_: uc.mem_write(p.PROTECTION + guard.EXHAUSTED, word(1)),
                      begin=at, end=at)
        self.assertEqual(s.call('mark_clean', 600, 0xFFFFFFFF), 0)
        self.assertEqual(s.call('protection_dirty', 600), 1)

    def test_a_mutation_during_hashing_cannot_be_acknowledged_as_clean(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        s.call('protection_import', 600)
        revision = s.u32(p.PROTECTION_REV)
        saved = s.u32(p.SIG + 600 * 4)
        at = s.sym['slot_sig']

        def mutate(uc, *_):
            uc.mem_write(p.PROTECTION_REV, word(revision + 1))
            uc.mem_write(PLAYBACK + 600 * 16 + 4, word(123))

        s.uc.hook_add(unicorn.UC_HOOK_CODE, mutate, begin=at, end=at)
        self.assertEqual(s.call('mark_clean', 600, revision), 0)
        self.assertEqual(s.u32(p.SIG + 600 * 4), saved)
        self.assertEqual(s.call('protection_dirty', 600), 1)

    def boot_parser(self, *, anchor, concurrent, mode):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        s.slot(601, base=F['DSP_MIN'] + 0x100, length=0x100)
        s.uc.mem_write(p.SIG + 600 * 4, word(0))
        descriptor, file, checkpoint = 0xC100A000, 0xC100B000, 0xC100C000
        s.uc.mem_write(descriptor, struct.pack('<H', 600))
        parser = f'''push {{r4-r11, lr}}
        sub sp, sp, #0x4C0
        sub sp, sp, #12
        mov r0, r1
        b 0xC003629C'''
        s.uc.mem_write(F['PARSER'], arm.assemble(parser, origin=F['PARSER']).bytes)
        returned = 'push {r0, r12}\nldr r0, =601\nbl protection_import\npop {r0, r12}\n' if concurrent else ''
        returned += 'mov r0, #0\nadd sp, sp, #0x4C0\nadd sp, sp, #12\npop {r4-r11, pc}\n.pool'
        returned = returned.replace('protection_import', str(s.sym['protection_import']))
        at = 0xC003629C
        s.uc.mem_write(at, arm.assemble(f"bl {s.sym['protect_reserve']}\n" + returned, origin=at).bytes)
        if anchor:
            code = sample_seek.parser_source(F['PARSER'] + 4)
            s.uc.mem_write(checkpoint, arm.assemble(code, origin=checkpoint).bytes)
            s.uc.mem_write(F['PARSER'], arm.assemble(f'b {checkpoint}', origin=F['PARSER']).bytes)
        at = s.sym['protect_reserve_native']

        def reserve(uc, *_):
            uc.reg_write(R.UC_ARM_REG_R0, 1)
            uc.reg_write(R.UC_ARM_REG_PC, uc.reg_read(R.UC_ARM_REG_LR))

        s.uc.hook_add(unicorn.UC_HOOK_CODE, reserve, begin=at, end=at)
        s.set_state('MODE', mode)
        header = 0xC100F000
        result = s.call('ss_boot_parse', file, descriptor, 0xFFFFFFFF, 0,
                        regs={R.UC_ARM_REG_R5: header, R.UC_ARM_REG_R8: header + 20 + 600 * 4})
        return s, result

    def test_boot_stamps_belong_to_their_own_parser_call_in_both_modes(self):
        for anchor in (False, True):
            for mode in (0, 1):
                with self.subTest(anchor=anchor, mode=mode):
                    s, status = self.boot_parser(anchor=anchor, concurrent=False, mode=mode)
                    self.assertEqual(status, 0)
                    self.assertNotEqual(s.u32(p.SIG + 600 * 4), 0)
                    self.assertEqual(s.call('protection_dirty', 600), 0)
                    s.set_state('MODE', 1)
                    self.assertEqual(s.call('can_evict', 600), 1)

    def test_another_mutation_does_not_replace_the_parser_owned_stamp(self):
        for anchor in (False, True):
            with self.subTest(anchor=anchor):
                s, status = self.boot_parser(anchor=anchor, concurrent=True, mode=1)
                self.assertEqual(status, 0)
                self.assertEqual(s.u32(p.SIG + 600 * 4), 0)
                self.assertEqual(s.call('can_evict', 600), 0)


if __name__ == '__main__':
    unittest.main()
