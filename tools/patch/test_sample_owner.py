"""File ownership and catalogue recovery on generated ARM code."""
import struct
import unittest

import sample_owner as p
import unicorn
from unicorn import arm_const as R

CODE, STATE, STACK, TRAP = 0xC1000000, 0xC1100000, 0xC1F00000, 0xC1200000


class Machine:
    def __init__(self):
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.uc.mem_map(0xC0000000, 0x02000000)
        code, self.labels = p.build_code(CODE, STATE)
        self.uc.mem_write(CODE, code)
        self.uc.mem_write(STATE, p.INITIAL)
        self.put(p.STARTED, 1)
        self.put(p.IRQ_DEPTH, 0)
        self.saved = {R.UC_ARM_REG_R4 + i: 0x12340000 + i * 0x100 for i in range(8)}

    def put(self, at, value):
        self.uc.mem_write(at, struct.pack('<I', value))

    def state(self):
        return struct.unpack('<4I', self.uc.mem_read(STATE, 16))

    def call(self, label, value, control=0x13):
        self.uc.reg_write(R.UC_ARM_REG_CPSR, control)
        for register, initial in self.saved.items():
            self.uc.reg_write(register, initial)
        self.uc.reg_write(R.UC_ARM_REG_SP, STACK)
        self.uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        self.uc.reg_write(R.UC_ARM_REG_R0, value)
        self.uc.emu_start(self.labels[label], TRAP, count=2000)
        assert self.uc.reg_read(R.UC_ARM_REG_SP) == STACK
        assert self.uc.reg_read(R.UC_ARM_REG_PC) == TRAP
        assert self.uc.reg_read(R.UC_ARM_REG_CPSR) & 255 == control
        assert all(self.uc.reg_read(register) == initial for register, initial in self.saved.items())
        return self.uc.reg_read(R.UC_ARM_REG_R0), self.uc.reg_read(R.UC_ARM_REG_R1)

    def ready(self):
        status, token = self.call('owner_acquire', p.RECOVER)
        assert status == p.OK
        assert self.call('owner_resolve', token)[0] == p.OK
        assert self.call('owner_release', token)[0] == p.OK


class Ownership(unittest.TestCase):
    def test_boot_requires_checked_recovery_before_reading_or_writing(self):
        m = Machine()
        before = m.state()
        self.assertEqual(before, (0, 0, 1, 0))
        for kind in (p.READ, p.WRITE):
            self.assertEqual(m.call('owner_acquire', kind), (p.NEEDS_RECOVERY, 0))
            self.assertEqual(m.state(), before)
        m.ready()
        status, token = m.call('owner_acquire', p.READ)
        self.assertEqual((status, token), (p.OK, 2))

    def test_a_competing_reader_or_writer_cannot_steal_the_current_lease(self):
        m = Machine()
        m.ready()
        status, token = m.call('owner_acquire', p.READ)
        self.assertEqual(status, p.OK)
        before = m.state()
        for kind in (p.READ, p.WRITE, p.RECOVER):
            self.assertEqual(m.call('owner_acquire', kind), (p.BUSY, 0))
            self.assertEqual(m.state(), before)
        self.assertEqual(m.call('owner_release', token)[0], p.OK)

    def test_writer_marks_the_catalogue_uncertain_until_a_checked_resolution(self):
        m = Machine()
        m.ready()
        status, token = m.call('owner_acquire', p.WRITE)
        self.assertEqual(status, p.OK)
        self.assertEqual(m.state(), (token, token, 1, p.WRITE))
        self.assertEqual(m.call('owner_release', token)[0], p.OK)
        for kind in (p.READ, p.WRITE):
            self.assertEqual(m.call('owner_acquire', kind), (p.NEEDS_RECOVERY, 0))
        m.ready()
        status, token = m.call('owner_acquire', p.WRITE)
        self.assertEqual(status, p.OK)
        self.assertEqual(m.call('owner_resolve', token)[0], p.OK)
        self.assertEqual(m.call('owner_release', token)[0], p.OK)
        self.assertEqual(m.call('owner_acquire', p.READ)[0], p.OK)

    def test_wrong_and_stale_tokens_neither_release_nor_resolve_a_new_owner(self):
        m = Machine()
        m.ready()
        _, old = m.call('owner_acquire', p.READ)
        m.call('owner_release', old)
        _, current = m.call('owner_acquire', p.WRITE)
        self.assertNotEqual(old, current)
        before = m.state()
        for token in (0, old, current + 1):
            for label in ('owner_release', 'owner_resolve', 'owner_uncertain'):
                self.assertEqual(m.call(label, token)[0], p.INVALID)
                self.assertEqual(m.state(), before)

    def test_a_reader_cannot_declare_an_uncertain_catalogue_checked(self):
        m = Machine()
        m.ready()
        _, token = m.call('owner_acquire', p.READ)
        m.put(STATE + 8, 1)
        before = m.state()
        self.assertEqual(m.call('owner_resolve', token)[0], p.INVALID)
        self.assertEqual(m.state(), before)
        self.assertEqual(m.call('owner_release', token)[0], p.OK)
        self.assertEqual(m.state()[2], 1)

    def test_a_failed_reader_blocks_following_reads_until_recovery(self):
        m = Machine()
        m.ready()
        _, token = m.call('owner_acquire', p.READ)
        self.assertEqual(m.call('owner_uncertain', token)[0], p.OK)
        self.assertEqual(m.call('owner_release', token)[0], p.OK)
        self.assertEqual(m.call('owner_acquire', p.READ), (p.NEEDS_RECOVERY, 0))
        m.ready()
        self.assertEqual(m.call('owner_acquire', p.READ)[0], p.OK)

    def test_only_the_current_clean_reader_can_use_the_load_path(self):
        m = Machine()
        m.ready()
        _, token = m.call('owner_acquire', p.READ)
        self.assertEqual(m.call('owner_readable', token)[0], p.OK)
        self.assertEqual(m.call('owner_readable', token + 1)[0], p.INVALID)
        m.call('owner_uncertain', token)
        self.assertEqual(m.call('owner_readable', token)[0], p.NEEDS_RECOVERY)
        m.call('owner_release', token)
        _, token = m.call('owner_acquire', p.RECOVER)
        self.assertEqual(m.call('owner_readable', token)[0], p.INVALID)

    def test_lease_tokens_never_wrap_into_a_stale_value(self):
        m = Machine()
        m.ready()
        m.put(STATE + 4, 0xFFFFFFFE)
        self.assertEqual(m.call('owner_acquire', p.READ), (p.OK, 0xFFFFFFFF))
        self.assertEqual(m.call('owner_release', 0xFFFFFFFF)[0], p.OK)
        before = m.state()
        self.assertEqual(m.call('owner_acquire', p.READ), (p.EXHAUSTED, 0))
        self.assertEqual(m.state(), before)

    def test_file_ownership_refuses_invalid_execution_contexts_without_mutation(self):
        for control, depth, started in ((0x93, 0, 1), (0x12, 1, 1), (0x11, 0, 1), (0x10, 0, 1), (0x13, 1, 1), (0x13, 0, 0)):
            with self.subTest(control=control, depth=depth, started=started):
                m = Machine()
                m.put(p.IRQ_DEPTH, depth)
                m.put(p.STARTED, started)
                before = m.state()
                self.assertEqual(m.call('owner_acquire', p.RECOVER, control), (p.CONTEXT, 0))
                self.assertEqual(m.state(), before)

    def test_cleanup_preserves_an_existing_irq_mask(self):
        m = Machine()
        _, token = m.call('owner_acquire', p.RECOVER)
        self.assertEqual(m.call('owner_resolve', token, 0x93)[0], p.OK)
        self.assertEqual(m.call('owner_release', token, 0x93)[0], p.OK)

    def test_acquisition_also_works_in_system_mode(self):
        m = Machine()
        self.assertEqual(m.call('owner_acquire', p.RECOVER, 0x1F), (p.OK, 1))

    def test_invalid_requests_and_uninitialized_state_are_not_silently_repaired(self):
        m = Machine()
        before = m.state()
        for kind in (0, 4, 0xFFFFFFFF):
            self.assertEqual(m.call('owner_acquire', kind), (p.INVALID, 0))
            self.assertEqual(m.state(), before)
        m.uc.mem_write(STATE, bytes([255]) * 16)
        before = m.state()
        self.assertEqual(m.call('owner_acquire', p.RECOVER), (p.BUSY, 0))
        self.assertEqual(m.state(), before)

    def test_acquisition_keeps_the_irq_masked_window_short(self):
        m = Machine()
        steps = []
        m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: steps.append(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80))
        self.assertEqual(m.call('owner_acquire', p.RECOVER), (p.OK, 1))
        self.assertGreater(sum(bool(step) for step in steps), 0)
        self.assertLess(sum(bool(step) for step in steps), 80)


if __name__ == '__main__':
    unittest.main()
