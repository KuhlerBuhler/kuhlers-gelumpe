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


class DirectMetadataStores(unittest.TestCase):
    def store(self, label, physical, value, *, mode=1, flags=0xA8000013, initial=0):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        alias(s, 601, 600)
        s.slot(602, base=F['DSP_MIN'] + 0x100, length=0x100)
        s.set_state('MODE', mode)
        site, pointer, value_reg, offset, width, bias, instruction = {
            'protect_tune': (0xC007F9F0, R.UC_ARM_REG_R3, R.UC_ARM_REG_R2, 20, 2, 0, '.word 0xE1C321B4'),
            'protect_level': (0xC007F94C, R.UC_ARM_REG_R6, R.UC_ARM_REG_R5, 10, 1, 0, 'strb r5, [r6, #10]'),
            'protect_tune_increment': (0xC007F0EC, R.UC_ARM_REG_R6, R.UC_ARM_REG_R3, 20, 2, 16, '.word 0xE1C630B4'),
            'protect_level_increment': (0xC007EFE8, R.UC_ARM_REG_R6, R.UC_ARM_REG_R5, 10, 1, 8, 'strb r5, [r6, #2]'),
        }[label]
        row = F['META'] + physical * 0x45C
        s.uc.mem_write(row + offset, initial.to_bytes(width, 'little'))
        if physical == 600:
            s.call('mark_clean', 600, s.u32(p.PROTECTION_REV))
            s.call('mark_clean', 601, s.u32(p.PROTECTION_REV))
        expected = {R.UC_ARM_REG_R0 + i: 0x12340000 + i for i in range(13)}
        expected.update({pointer: row + bias, value_reg: value & 0xFFFFFFFF,
                         R.UC_ARM_REG_R11: p.STATE})
        s.uc.mem_write(site, arm.assemble(instruction + '\nbx lr', origin=site).bytes)
        for hook, _, _, name, *_ in p.SITES:
            if hook == site:
                s.uc.mem_write(site, arm.assemble(f'b {s.sym[name]:#x}', origin=site).bytes)
        before = []
        at = s.sym['protection_bit']
        s.uc.hook_add(unicorn.UC_HOOK_CODE,
                      lambda uc, *_: before.append(bytes(uc.mem_read(row + offset, width))),
                      begin=at, end=at)
        row_irq = []
        resolve = s.sym['protection_row_index']
        s.uc.hook_add(unicorn.UC_HOOK_CODE,
                      lambda uc, *_: row_irq.append(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80),
                      begin=resolve, end=resolve)
        store_irq = []
        s.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,
                      lambda uc, access, address, size, value, data:
                      store_irq.append(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)
                      if address == row + offset else None)
        s.uc.reg_write(R.UC_ARM_REG_CPSR, flags)
        s.call(site, regs=expected)
        for reg, val in expected.items():
            self.assertEqual(s.uc.reg_read(reg), val, f'{label} register {reg}')
        self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_CPSR), flags)
        self.assertEqual(int.from_bytes(s.uc.mem_read(row + offset, width), 'little'),
                         value & ((1 << (width * 8)) - 1))
        s.store_irq = store_irq
        s.row_irq = row_irq
        return s, before

    def test_changed_tune_and_level_protect_the_actual_row_and_all_aliases(self):
        for label, value in (('protect_tune', -256), ('protect_level', 9)):
            for physical in (500, 600, 998):
                with self.subTest(label=label, physical=physical):
                    s, before = self.store(label, physical, value)
                    self.assertEqual(before, [bytes(2 if label == 'protect_tune' else 1)])
                    self.assertEqual(s.call('protection_dirty', physical), 1)
                    self.assertEqual(s.call('protection_dirty', 602), 0)
                    if physical == 600:
                        self.assertEqual(s.call('can_evict', 600), 0)
                        self.assertEqual(s.call('can_evict', 601), 0)

    def test_incremental_stores_protect_the_resolved_row_and_preserve_flags(self):
        for label, value in (('protect_tune_increment', -256), ('protect_level_increment', 7)):
            with self.subTest(label=label):
                s, before = self.store(label, 600, value)
                self.assertEqual(before, [bytes(2 if 'tune' in label else 1)])
                self.assertEqual(s.call('protection_dirty', 600), 1)
                self.assertEqual(s.call('can_evict', 601), 0)
                self.assertEqual(s.store_irq, [0x80])
                self.assertEqual(s.row_irq, [0])
                s, before = self.store(label, 600, 0)
                self.assertEqual(before, [])
                self.assertEqual(s.call('can_evict', 600), 1)

    def test_identical_truncated_values_do_not_dirty_the_row(self):
        for label, value in (('protect_tune', 0xFFFF0000), ('protect_level', 0x100)):
            with self.subTest(label=label):
                s, before = self.store(label, 600, value)
                self.assertEqual(before, [])
                self.assertEqual(s.call('can_evict', 600), 1)

    def test_unchanged_negative_tune_is_compared_as_a_halfword(self):
        s, before = self.store('protect_tune', 600, -256, initial=0xFF00)
        self.assertEqual(before, [])
        self.assertEqual(s.call('can_evict', 600), 1)

    def test_restoring_a_native_value_does_not_clear_its_protection(self):
        s, _ = self.store('protect_tune', 600, -256)
        s.call(0xC007F9F0, regs={R.UC_ARM_REG_R3: F['META'] + 600 * 0x45C,
                                R.UC_ARM_REG_R2: 0})
        self.assertEqual(s.call('slot_clean', 600), 1)
        self.assertEqual(s.call('can_evict', 601), 0)

    def test_marker_and_store_share_the_same_short_irq_commit(self):
        for label, value in (('protect_tune', 256), ('protect_level', 1)):
            with self.subTest(label=label):
                s, _ = self.store(label, 600, value)
                self.assertEqual(s.store_irq, [0x80])
                self.assertEqual(s.row_irq, [0])

    def test_masked_interrupt_state_is_preserved(self):
        s, before = self.store('protect_tune', 600, 256, flags=0x58000093)
        self.assertEqual(s.call('protection_dirty', 600), 1)
        self.assertEqual(before, [bytes(2)])

    def test_native_stores_also_protect_small_and_faulted_libraries(self):
        for mode in (0, 2):
            with self.subTest(mode=mode):
                s, before = self.store('protect_tune', 600, 256, mode=mode)
                self.assertEqual(before, [bytes(2)])
                self.assertEqual(s.call('protection_dirty', 600), 1)

    def test_an_invalid_row_pointer_does_not_mark_an_unrelated_sample(self):
        for offset in (-4, 1, 999 * 0x45C):
            with self.subTest(offset=offset):
                s = Swap()
                s.slot(600, base=F['DSP_MIN'], length=0x100)
                revision = s.u32(p.PROTECTION_REV)
                s.call('protection_row_index', F['META'] + offset)
                self.assertEqual(s.u32(p.PROTECTION_REV), revision)
                self.assertEqual(s.call('can_evict', 600), 1)

    def test_inactive_swap_does_not_mark_a_native_store(self):
        s, before = self.store('protect_level', 600, 4, mode=3)
        self.assertEqual(before, [])
        self.assertEqual(s.call('protection_dirty', 600), 0)


class TransportBaseline(unittest.TestCase):
    def test_terminal_dsp_fault_cannot_certify_a_row_before_or_during_hashing(self):
        for during in (False, True):
            with self.subTest(during=during):
                s = Swap()
                s.slot(600, base=F['DSP_MIN'], length=0x100)
                previous = s.u32(p.SIG + 600 * 4)
                s.uc.mem_write(F['META'] + 600 * 0x45C + 20, b'\0\1')
                if during:
                    at = s.sym['slot_sig']
                    s.uc.hook_add(unicorn.UC_HOOK_CODE,
                        lambda *_: s.set_state('TSTATE', 2), begin=at, end=at)
                else:
                    s.set_state('TSTATE', 2)
                self.assertEqual(s.call('mark_clean', 600, s.u32(p.PROTECTION_REV)), 0)
                self.assertEqual(s.u32(p.SIG + 600 * 4), previous)

    def test_a_terminal_fault_invalidates_a_prepared_eviction(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        self.assertEqual(s.call('victim'), 600)
        s.set_state('TSTATE', 2)
        self.assertEqual(s.call('evict_prepared', 600), 0)
        self.assertFalse(any(call[0] == F['DELETE'] for call in s.calls))

    def test_another_inflight_transfer_does_not_mean_terminal_failure(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        s.set_state('TSTATE', 1)
        self.assertEqual(s.call('mark_clean', 600, s.u32(p.PROTECTION_REV)), 1)


class NativePcmResults(unittest.TestCase):
    def hooks(self, s, site, original):
        s.uc.mem_write(site, arm.assemble(original + '\nbx lr', origin=site).bytes)
        for at, _, _, name, *_ in p.SITES:
            if at == site:
                s.uc.mem_write(site, arm.assemble(f'b {s.sym[name]:#x}', origin=site).bytes)

    def test_parser_write_failures_use_the_normal_cleanup_without_advancing(self):
        data = 0xC100C000
        for site in (0xC0036320, 0xC00363E4):
            for result in (0, 1, 4):
                with self.subTest(site=site, result=result):
                    s = Swap()
                    self.hooks(s, site, 'add r5, r5, r10')
                    cleanup = 0xC003639C
                    source = f'ldr r1, ={data}\nstr r3, [r1]\nmov r0, r3\nbx lr\n.pool'
                    s.uc.mem_write(cleanup, arm.assemble(source, origin=cleanup).bytes)
                    returned = s.call(site, result, regs={R.UC_ARM_REG_R5: 100, R.UC_ARM_REG_R10: 32})
                    self.assertEqual(s.u32(data), 4 if result else 0)
                    self.assertEqual(returned, 4 if result else 0)
                    self.assertEqual(s.uc.reg_read(R.UC_ARM_REG_R5), 100 if result else 132)

    def test_a_failed_short_write_read_cannot_continue_to_copy_or_write(self):
        entry, data, site = 0xC100B000, 0xC100C000, 0xC004EF58
        for result in (0, 4):
            with self.subTest(result=result):
                s = Swap()
                self.hooks(s, site, 'mov r3, #0')
                resume = f'ldr r1, ={data}\nmov r0, #1\nstr r0, [r1]\nmov r0, #0\nadd sp, sp, #32\npop {{r4-r6, pc}}\n.pool'
                s.uc.mem_write(site + 4, arm.assemble(resume, origin=site + 4).bytes)
                source = f'push {{r4-r6, lr}}\nsub sp, sp, #32\nmov r0, #{result}\nb {site}'
                s.uc.mem_write(entry, arm.assemble(source, origin=entry).bytes)
                regs = {R.UC_ARM_REG_R4 + i: 0x12340000 + i for i in range(3)}
                self.assertEqual(s.call(entry, regs=regs), result)
                self.assertEqual(s.u32(data), int(result == 0))
                for register, value in regs.items():
                    self.assertEqual(s.uc.reg_read(register), value)


class AcquiredJobValidation(unittest.TestCase):
    def prepared(self):
        s = Swap()
        s.slot(601, active=False)
        for name, value in dict(J_STATE=1, J_DST=0, J_GEN=7, J_BASE=F['DSP_MIN'],
                                J_DONE=32, J_STAGED=32, J_LEN=64, J_SLOT=601).items():
            s.set_state(name, value)
        self.assertEqual(s.call('owner_acquire', p.sample_owner.READ), 0)
        return s, s.uc.reg_read(R.UC_ARM_REG_R1)

    def test_acquired_write_matches_the_current_staged_job_and_reader(self):
        s, token = self.prepared()
        self.assertEqual(s.call('transfer_job_ok', p.STAGE, F['DSP_MIN'] + 32, 16, token), 1)

    def test_a_full_native_swap_chunk_is_accepted_without_a_smaller_private_limit(self):
        s, token = self.prepared()
        s.set_state('J_LEN', p.CHUNK * 2)
        s.set_state('J_DONE', 0)
        s.set_state('J_STAGED', p.CHUNK)
        self.assertEqual(s.call('transfer_job_ok', p.STAGE, F['DSP_MIN'], p.CHUNK // 2, token), 1)
        s.set_state('J_STAGED', p.CHUNK + 32)
        self.assertEqual(s.call('transfer_job_ok', p.STAGE, F['DSP_MIN'], (p.CHUNK + 32) // 2, token), 0)

    def test_cancelled_replaced_and_busy_jobs_cannot_start_a_write(self):
        for name, value in dict(J_STATE=0, J_DST=1, J_GEN=6, J_BASE=F['DSP_MIN'] + 32,
                                J_DONE=0, J_STAGED=0, J_LEN=32, MODE=2, TSTATE=2).items():
            with self.subTest(field=name):
                s, token = self.prepared()
                s.set_state(name, value)
                self.assertEqual(s.call('transfer_job_ok', p.STAGE, F['DSP_MIN'] + 32, 16, token), 0)
        for arg, value in ((0, p.STAGE + 32), (1, F['DSP_MIN']), (2, 32), (3, 0)):
            with self.subTest(argument=arg):
                s, token = self.prepared()
                args = [p.STAGE, F['DSP_MIN'] + 32, 16, token]
                args[arg] = value
                self.assertEqual(s.call('transfer_job_ok', *args), 0)


class MutationDuringSwap(unittest.TestCase):
    def test_a_native_change_cancels_the_active_job_without_discarding_other_cache_entries(self):
        s = Swap()
        s.slot(600, base=F['DSP_MIN'], length=0x100)
        for name, value in dict(J_STATE=1, J_STAGED=32, SESSION=1, CFILL=1).items():
            s.set_state(name, value)
        s.call('protection_import', 600)
        self.assertEqual(s.state('J_STATE'), 0)
        self.assertEqual(s.state('J_STAGED'), 0)
        self.assertEqual(s.state('GEN'), 7)
        self.assertEqual(s.state('SESSION'), 1)
        self.assertEqual(s.call('job_ok'), 0)
        self.assertEqual(s.state('GEN'), 7)
        self.assertEqual(s.state('CFILL'), 1)

    def test_a_native_reservation_after_placement_prevents_the_atomic_commit(self):
        s = Swap()
        s.slot(500, active=False)
        s.slot(501, active=False, base=F['DSP_MIN'], length=32)
        source = f'''mov r0, #32
        str r0, [r11, #{p.OFF['P_LEN']}]
        mov r0, #16
        str r0, [r11, #{p.OFF['P_BITS']}]
        mov r0, #0
        bx lr'''
        s.uc.mem_write(s.sym['parse'], arm.assemble(source, origin=s.sym['parse']).bytes)
        returns = []
        for at in range(s.sym['start_install'], s.sym['start_prepare'], 4):
            instruction = s.u32(at)
            if instruction >> 24 == 0xEB:
                offset = ((instruction & 0xFFFFFF) ^ 0x800000) - 0x800000
                if at + 8 + offset * 4 == s.sym['place']:
                    returns.append(at + 4)
        self.assertEqual(len(returns), 1)
        observed = []

        def reserve(uc, *_):
            observed.append(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)
            uc.mem_write(F['META'] + 501 * 0x45C + 11, b'\1')
            uc.mem_write(p.PROTECTION_REV, word(s.u32(p.PROTECTION_REV) + 1))

        s.uc.hook_add(unicorn.UC_HOOK_CODE, reserve, begin=returns[0], end=returns[0])
        cursor = s.u32(F['CURSOR'])
        self.assertEqual(s.call('start_install', 500), 0)
        self.assertEqual(observed, [0])
        self.assertEqual(s.state('J_STATE'), 0)
        self.assertEqual(s.u32(F['CURSOR']), cursor)

    def test_a_native_change_during_job_setup_cannot_resurrect_the_canceled_load(self):
        for point in ('job_common', 'jc_sum'):
            with self.subTest(point=point):
                s = Swap()
                s.slot(500, active=False)
                source = f'''mov r0, #32
                str r0, [r11, #{p.OFF['P_LEN']}]
                mov r0, #16
                str r0, [r11, #{p.OFF['P_BITS']}]
                mov r0, #0
                bx lr'''
                s.uc.mem_write(s.sym['parse'], arm.assemble(source, origin=s.sym['parse']).bytes)

                def mutate(uc, *_):
                    self.assertFalse(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80)
                    uc.mem_write(p.PROTECTION_REV, word(s.u32(p.PROTECTION_REV) + 1))
                    s.set_state('J_STATE', 0)
                    s.set_state('J_STAGED', 0)

                at = s.sym[point]
                s.uc.hook_add(unicorn.UC_HOOK_CODE, mutate, begin=at, end=at)
                self.assertEqual(s.call('start_install', 500), 0)
                self.assertEqual(s.state('J_STATE'), 0)

    def test_placement_does_not_accept_a_hole_computed_before_a_native_mutation(self):
        s = Swap()
        at = s.sym['first_fit']
        source = f'''push {{r4, lr}}
        mov r0, #600
        bl {s.sym['protection_touch']}
        ldr r0, ={F['DSP_MIN']}
        pop {{r4, pc}}
        .pool'''
        s.uc.mem_write(at, arm.assemble(source, origin=at).bytes)
        self.assertEqual(s.call('place', 32), 0)


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
