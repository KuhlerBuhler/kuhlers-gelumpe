"""Bounded resource acquisition with generated ARM and synthetic kernel state."""
import struct
import unittest

import unicorn
from unicorn import arm_const as R

import arm
import native_dsp_acquire as p

CODE, DATA, STACK, TRAP = 0xC1000000, 0xC1100000, 0xC1F00000, 0xC1200000
FAULT, MODE, GEN, GATE, SESSION = (DATA + i * 4 for i in range(5))
OWNER, TASK, SCOPE, SEMA, TICK, DEPTH, STARTED = DATA + 20, DATA + 36, DATA + 40, DATA + 44, DATA + 48, DATA + 52, DATA + 56
DELAY, RELEASE = CODE + 0x5000, CODE + 0x5100


class Machine:
    def __init__(self, *, free=True, attempts=4, timeout=5, tick=0, step=1, delay_action=None):
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.uc.mem_map(0xC0000000, 0x02000000)
        code, self.sym = p.build_code(CODE, fault=FAULT, mode=MODE, generation=GEN, gate=GATE,
                                      session=SESSION, owner=OWNER, current_task=TASK, scope=SCOPE,
                                      sema=SEMA, tick=TICK, irq_depth=DEPTH, started=STARTED,
                                      delay=DELAY, release=RELEASE, attempts=attempts, timeout_ms=timeout, gate_owner=DATA + 60)
        self.uc.mem_write(CODE, code)
        for at in (TRAP, DELAY, RELEASE):
            self.uc.mem_write(at, arm.assemble('bx lr', origin=at).bytes)
        self.put(MODE, 1)
        self.put(GEN, 7)
        self.put(GATE, 1)
        self.put(SESSION, 3)
        self.put(TASK, 0xC06A2524)
        self.put(STARTED, 1)
        self.put(SEMA, int(free))
        self.put(TICK, tick)
        self.step, self.delay_action = step, delay_action
        self.yields, self.releases = [], []
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.delay, begin=DELAY, end=DELAY)
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.release, begin=RELEASE, end=RELEASE)
        self.registers = {R.UC_ARM_REG_R4 + i: 0x12340000 + i * 0x100 for i in range(8)}

    def put(self, at, value):
        self.uc.mem_write(at, struct.pack('<I', value & 0xFFFFFFFF))

    def u32(self, at):
        return struct.unpack('<I', self.uc.mem_read(at, 4))[0]

    def delay(self, uc, *_):
        self.yields.append((uc.reg_read(R.UC_ARM_REG_R0), uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80))
        self.put(TICK, self.u32(TICK) + self.step)
        if self.delay_action:
            self.delay_action(self)
        uc.reg_write(R.UC_ARM_REG_R0, 0)

    def release(self, uc, *_):
        self.releases.append((uc.reg_read(R.UC_ARM_REG_R0), uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80))
        self.put(SEMA, self.u32(SEMA) + 1)
        uc.reg_write(R.UC_ARM_REG_R0, 0)

    def run(self, policy=1, index=1, control=0xA0000013):
        for register, value in self.registers.items():
            self.uc.reg_write(register, value)
        self.uc.reg_write(R.UC_ARM_REG_R0, index)
        self.uc.reg_write(R.UC_ARM_REG_R1, policy)
        self.uc.reg_write(R.UC_ARM_REG_SP, STACK)
        self.uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        self.uc.reg_write(R.UC_ARM_REG_CPSR, control)
        self.uc.emu_start(self.sym['native_resource_take'], TRAP, count=100_000)
        result = self.uc.reg_read(R.UC_ARM_REG_R0)
        assert self.uc.reg_read(R.UC_ARM_REG_PC) == TRAP
        assert self.uc.reg_read(R.UC_ARM_REG_SP) == STACK
        assert {register: self.uc.reg_read(register) for register in self.registers} == self.registers
        assert self.uc.reg_read(R.UC_ARM_REG_CPSR) == (control | 0x80 if result == 0 else control)
        return result


class BoundedAcquisition(unittest.TestCase):
    def test_free_resource_hands_off_one_lease_with_irqs_masked(self):
        m = Machine()
        self.assertEqual(m.run(), p.OK)
        self.assertEqual((m.u32(SEMA), m.yields, m.releases), (0, [], []))

    def test_contention_yields_and_allows_the_owner_to_release(self):
        m = Machine(free=False, delay_action=lambda m: m.put(SEMA, 1))
        self.assertEqual(m.run(), p.OK)
        self.assertEqual(m.yields, [(1, 0)])
        self.assertEqual((m.u32(SEMA), m.releases), (0, []))

    def test_attempts_and_deadline_bound_a_stopped_tick_when_the_yield_returns(self):
        for step, attempts, timeout in ((0, 4, 5), (2, 20, 5), (1, 20, 5)):
            m = Machine(free=False, step=step, attempts=attempts, timeout=timeout)
            self.assertEqual(m.run(), p.BUSY)
            self.assertLessEqual(len(m.yields), min(attempts, 5 if step else attempts))
            self.assertEqual((m.u32(SEMA), m.releases), (0, []))
            self.assertTrue(all(ms == 1 and irq == 0 for ms, irq in m.yields))

    def test_tick_wrap_preserves_a_short_valid_wait(self):
        m = Machine(free=False, tick=0xFFFFFFFF, delay_action=lambda m: m.put(SEMA, 1))
        self.assertEqual(m.run(), p.OK)

    def test_library_or_task_changes_during_wait_cancel_without_poisoning_globals(self):
        for at in (MODE, GEN, GATE, SESSION, OWNER, OWNER + 4, OWNER + 8, OWNER + 12, TASK, DATA + 60):
            with self.subTest(at=at):
                def change(m):
                    m.put(SEMA, 1)
                    m.put(at, m.u32(at) + 1)
                m = Machine(free=False, delay_action=change)
                self.assertEqual(m.run(), p.STALE)
                self.assertEqual(m.u32(SEMA), 1)
                self.assertEqual(m.releases, [])
                self.assertEqual(m.u32(FAULT), 0)
                self.assertEqual(m.u32(SCOPE), 0)

    def test_plain_calls_do_not_bind_to_an_unrelated_library(self):
        def change(m):
            for at in (MODE, GEN, GATE, SESSION, OWNER, OWNER + 4):
                m.put(at, m.u32(at) + 1)
            m.put(SEMA, 1)
        m = Machine(free=False, delay_action=change)
        self.assertEqual(m.run(policy=0), p.OK)

    def test_inflight_completion_is_not_a_latched_fault(self):
        def complete(m):
            m.put(FAULT, 0)
            m.put(SEMA, 1)
        m = Machine(free=False, delay_action=complete)
        m.put(FAULT, 1)
        self.assertEqual(m.run(), p.OK)
        m = Machine()
        m.put(FAULT, 2)
        self.assertEqual(m.run(), p.STALE)
        self.assertEqual((m.u32(SEMA), m.releases), (1, []))

    def test_a_post_grant_change_releases_exactly_its_own_lease(self):
        m = Machine()
        m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,
                      lambda uc, access, at, size, value, _: m.put(GEN, 8) if value == 0 else None,
                      begin=SEMA, end=SEMA + 3)
        self.assertEqual(m.run(), p.STALE)
        self.assertEqual(m.releases, [(1, 0)])
        self.assertEqual((m.u32(SEMA), m.u32(FAULT), m.u32(SCOPE)), (1, 0, 0))

    def test_an_active_scope_is_never_replaced_or_released(self):
        m = Machine()
        m.put(SCOPE, DATA + 0x800)
        self.assertEqual(m.run(), p.STALE)
        self.assertEqual((m.u32(SCOPE), m.u32(SEMA), m.releases), (DATA + 0x800, 1, []))

    def test_bad_context_or_invalid_arguments_never_touch_a_resource(self):
        for field, value in ((DEPTH, 1), (STARTED, 0), (TASK, 0)):
            m = Machine()
            m.put(field, value)
            self.assertEqual(m.run(), p.CONTEXT)
            self.assertEqual((m.u32(SEMA), m.yields, m.releases), (1, [], []))
        for index, policy in ((0, 1), (2, 1), (1, 2)):
            self.assertEqual(Machine().run(index=index, policy=policy), p.INVALID)
        self.assertEqual(Machine().run(control=0xA0000093), p.CONTEXT)


if __name__ == '__main__':
    unittest.main()
