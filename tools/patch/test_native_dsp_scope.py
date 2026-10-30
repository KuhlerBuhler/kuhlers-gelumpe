"""Recovery from generated FP-based void calls, without firmware bytes."""
import struct
import unittest

import unicorn
from unicorn import arm_const as R

import arm
import native_dsp_scope as p

CODE, STATE, STACK, TRAP = 0xC1000000, 0xC1100000, 0xC1F00000, 0xC1200000
RELEASE = CODE + 0x4000
ACQUIRE = CODE + 0x4100
SCOPE, FAULT, MODE, GEN = (STATE + i * 4 for i in range(4))
RELEASES, SUCCESS, ARG_CHECK, SEMA = STATE + 16, STATE + 20, STATE + 0x100, STATE + 28


def word(value):
    return struct.pack('<I', value & 0xFFFFFFFF)


class Machine:
    def __init__(self, *, polls=5, clock=True, step=0, start=0, irq=False):
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.uc.mem_map(0xC0000000, 0x02000000)
        self.uc.mem_map(p.TIMER, 4096)
        code, self.symbols = p.build_code(CODE, scope=SCOPE, fault=FAULT, mode=MODE,
                                          generation=GEN, release=RELEASE, acquire=ACQUIRE, poll_budget=polls)
        self.uc.mem_write(CODE, code)
        self.uc.mem_write(TRAP, word(0xE1A00000))
        self.put(MODE, 1)
        self.put(GEN, 7)
        self.put(SEMA, 0)
        self.put(p.TIMER + 0x18, p.TIMER_HZ - 1)
        self.put(p.TIMER + 0x20, 0x80 if clock else 0)
        self.put(p.TIMER + 0x24, 1 if clock else 0)
        self.counter, self.step = start, step
        self.put(p.TIMER + 0x10, self.counter)
        self.uc.hook_add(unicorn.UC_HOOK_MEM_READ, self.read_clock,
                         begin=p.TIMER + 0x10, end=p.TIMER + 0x13)
        self.releases = []
        self.acquires = []
        self.uc.mem_write(RELEASE, arm.assemble('bx lr', origin=RELEASE).bytes)
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.release, begin=RELEASE, end=RELEASE)
        self.uc.mem_write(ACQUIRE, arm.assemble('bx lr', origin=ACQUIRE).bytes)
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.acquire, begin=ACQUIRE, end=ACQUIRE)
        self.initial = {R.UC_ARM_REG_R0 + i: 0x12340000 + i * 0x100 for i in range(4, 12)}
        self.initial[R.UC_ARM_REG_R11] = 0xC1D00000
        self.control = 0x93 if irq else 0x13

    def put(self, at, value):
        self.uc.mem_write(at, word(value))

    def u32(self, at):
        return struct.unpack('<I', self.uc.mem_read(at, 4))[0]

    def read_clock(self, uc, *args):
        self.put(p.TIMER + 0x10, self.counter)
        self.counter = (self.counter + self.step) % p.TIMER_HZ

    def release(self, uc, *args):
        control = uc.reg_read(R.UC_ARM_REG_CPSR) & 0xFF
        self.releases.append(dict(index=uc.reg_read(R.UC_ARM_REG_R0), scope=self.u32(SCOPE), control=control))
        if not control & 0x80:
            self.put(SEMA, self.u32(SEMA) + 1)

    def acquire(self, uc, *args):
        status = -25 if uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80 else 0
        self.acquires.append((uc.reg_read(R.UC_ARM_REG_R0), status))
        if status == 0:
            self.put(SEMA, self.u32(SEMA) - 1)
        uc.reg_write(R.UC_ARM_REG_R0, status & 0xFFFFFFFF)

    def run(self, ticks=1, deep=False, borrowed=False, refused=False, intruder=False,
            native=False, close=False, bare=False):
        entry = CODE + 0x3000
        label = 'native_scope_take' if native else ('native_scope_refused' if refused else ('native_scope_enter_borrowed' if borrowed else 'native_scope_enter'))
        text = f'''
            push {{r11, lr}}
            add r11, sp, #4
            {'' if bare else 'sub sp, sp, #32'}
            mov r0, #10
            mov r1, #11
            mov r2, #12
            mov r3, #13
            {'mov r0, #1' if native else ''}
            bl {self.symbols[label]}
            ldr r12, ={ARG_CHECK}
            stmia r12, {{r0-r3}}
            mov r3, #99
            str r3, [sp]
            str r3, [sp, #12]
        '''
        ticks_code = ''.join(f"bl {self.symbols['native_scope_tick']}\n" for _ in range(ticks))
        if intruder:
            text += 'bl intruder_interrupt\n'
        text += "bl deep_call\n" if deep else ticks_code
        release = (f'mov r0, #1\nbl {self.symbols["native_scope_close"]}' if close or native else
                   f'bl {self.symbols["native_scope_leave"]}\n' + ('' if borrowed or refused else f'mov r0, #1\nbl {RELEASE}'))
        text += f'''
            ldr r0, ={SUCCESS}
            mov r1, #1
            str r1, [r0]
            {release}
            {'' if bare else 'sub sp, r11, #4'}
            pop {{r11, pc}}
            .pool
        '''
        if deep:
            text += f"""
            deep_call:
                push {{r4, r5, r11, lr}}
                add r11, sp, #12
                sub sp, sp, #24
                mov r4, #24
                mov r5, #25
                {ticks_code}
                sub sp, r11, #12
                pop {{r4, r5, r11, pc}}
            """
        if intruder:
            text += f'''
            intruder_interrupt:
                push {{r4, lr}}
                .word 0xe10f4000
                orr r12, r4, #0x80
                .word 0xe121f00c
                bl intruder_call
                .word 0xe121f004
                pop {{r4, pc}}
            intruder_call:
                push {{r11, lr}}
                add r11, sp, #4
                sub sp, sp, #32
                bl {self.symbols['native_scope_refused']}
                sub sp, r11, #4
                pop {{r11, pc}}
            '''
        self.uc.mem_write(entry, arm.assemble(text, origin=entry).bytes)
        self.uc.reg_write(R.UC_ARM_REG_CPSR, self.control)
        for register, value in self.initial.items():
            self.uc.reg_write(register, value)
        self.uc.reg_write(R.UC_ARM_REG_SP, STACK)
        self.uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        self.uc.emu_start(entry, TRAP, count=100_000)


class Startup(unittest.TestCase):
    def initialize(self, m):
        self.assertIn('native_scope_init', m.symbols)
        m.uc.reg_write(R.UC_ARM_REG_CPSR, m.control)
        for register, value in m.initial.items():
            m.uc.reg_write(register, value)
        m.uc.reg_write(R.UC_ARM_REG_SP, STACK)
        m.uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        m.uc.emu_start(m.symbols['native_scope_init'], TRAP, count=10000)
        self.assertEqual(m.uc.reg_read(R.UC_ARM_REG_PC), TRAP)
        self.assertEqual(m.uc.reg_read(R.UC_ARM_REG_SP), STACK)
        self.assertEqual(m.uc.reg_read(R.UC_ARM_REG_CPSR) & 255, m.control)
        for register, value in m.initial.items():
            self.assertEqual(m.uc.reg_read(register), value)

    def test_initialization_is_atomic_and_preserves_the_original_irq_state(self):
        for irq in (False, True):
            with self.subTest(irq=irq):
                m = Machine(irq=irq)
                m.put(SCOPE, 0xFFFFFFFF)
                m.put(FAULT, 0xFFFFFFFF)
                writes = []
                m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,
                             lambda uc, access, at, size, value, _: writes.append(
                                 (at, bool(uc.reg_read(R.UC_ARM_REG_CPSR) & 0x80))),
                             begin=SCOPE, end=FAULT + 3)
                self.initialize(m)
                self.assertEqual((m.u32(SCOPE), m.u32(FAULT), m.u32(MODE), m.u32(GEN)), (0, 0, 1, 7))
                self.assertEqual({at for at, _ in writes}, {SCOPE, FAULT})
                self.assertTrue(all(masked for _, masked in writes))

    def test_initialization_preserves_a_live_scope_and_any_latched_fault(self):
        for pointer, fault in ((0, 0), (0, 1), (STATE + 0x500, 0), (STATE + 0x500, 1), (0xFFFFFFFF, 1)):
            with self.subTest(pointer=pointer, fault=fault):
                m = Machine()
                m.put(SCOPE, pointer)
                m.put(FAULT, fault)
                self.initialize(m)
                self.assertEqual(m.u32(SCOPE), 0 if pointer == 0xFFFFFFFF else pointer)
                self.assertEqual(m.u32(FAULT), fault)
                self.assertEqual((m.u32(MODE), m.u32(GEN)), (1, 7))

    def test_native_transactions_keep_original_behavior_before_initialization(self):
        m = Machine()
        for address in (SCOPE, FAULT, MODE, GEN):
            m.put(address, 0xFFFFFFFF)
        m.put(SEMA, 1)
        m.run(native=True)
        self.assertEqual(m.uc.reg_read(R.UC_ARM_REG_PC), TRAP)
        self.assertEqual(m.uc.reg_read(R.UC_ARM_REG_SP), STACK)
        self.assertEqual(m.u32(SUCCESS), 1)
        self.assertEqual([m.u32(address) for address in (SCOPE, FAULT, MODE, GEN)], [0xFFFFFFFF] * 4)
        self.assertEqual(m.u32(SEMA), 1)
        self.assertEqual(m.acquires, [(1, 0)])
        self.assertEqual(m.releases, [dict(index=1, scope=0xFFFFFFFF, control=m.control)])


class PollDriver(unittest.TestCase):
    def machine(self):
        m = Machine()
        self.assertTrue(hasattr(p, 'build_driver_code'))
        code, m.symbols = p.build_driver_code(CODE, scope=SCOPE, fault=FAULT, mode=MODE,
                                             generation=GEN, release=RELEASE, acquire=ACQUIRE)
        m.uc.mem_write(CODE, code)
        return m

    def call(self, m, label, arguments):
        m.uc.reg_write(R.UC_ARM_REG_CPSR, m.control)
        for register, value in arguments.items():
            m.uc.reg_write(register, value)
        m.uc.reg_write(R.UC_ARM_REG_SP, STACK)
        m.uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        m.uc.emu_start(m.symbols[label], TRAP, count=10000)
        self.assertEqual(m.uc.reg_read(R.UC_ARM_REG_PC), TRAP)
        self.assertEqual(m.uc.reg_read(R.UC_ARM_REG_SP), STACK)
        self.assertEqual(m.uc.reg_read(R.UC_ARM_REG_CPSR) & 255, m.control)

    def test_control_poll_reads_the_native_halfword_and_preserves_live_registers(self):
        m = self.machine()
        m.uc.mem_map(0x60000000, 4096)
        m.uc.mem_write(0x60000002, struct.pack('<H', 0x85))
        registers = {R.UC_ARM_REG_R0 + i: 0x12340000 + i for i in range(13)}
        registers[R.UC_ARM_REG_R3] = 0x60000002
        self.call(m, 'native_scope_control', registers)
        for register, value in registers.items():
            self.assertEqual(m.uc.reg_read(register), 0x85 if register == R.UC_ARM_REG_R3 else value)
        self.assertEqual(m.releases, [])

    def test_gpio_poll_keeps_the_native_call_and_its_result(self):
        m = self.machine()
        m.uc.mem_write(0xC00145F0, arm.assemble('mov r0, #1\nbx lr', origin=0xC00145F0).bytes)
        registers = {R.UC_ARM_REG_R0 + i: 0x12340000 + i for i in range(13)}
        self.call(m, 'native_scope_gpio', registers)
        for register, value in registers.items():
            self.assertEqual(m.uc.reg_read(register), 1 if register == R.UC_ARM_REG_R0 else value)
        self.assertEqual(m.releases, [])


class Recovery(unittest.TestCase):
    def overwrite_released_context(self, machine):
        observed = dict(context=0, overwritten=False)

        def interrupt(uc, *_):
            pointer = machine.u32(SCOPE)
            if pointer:
                observed['context'] = pointer
            pointer = observed['context']
            if pointer and not observed['overwritten'] and uc.reg_read(R.UC_ARM_REG_SP) >= pointer + 80:
                uc.mem_write(pointer, bytes(80))
                observed['overwritten'] = True

        machine.uc.hook_add(unicorn.UC_HOOK_CODE, interrupt, begin=CODE, end=CODE + 0x3000 - 1)
        return observed

    def assert_returned(self, machine, released=True, scope=0, available=None):
        self.assertEqual(machine.uc.reg_read(R.UC_ARM_REG_PC), TRAP)
        self.assertEqual(machine.uc.reg_read(R.UC_ARM_REG_SP), STACK)
        self.assertEqual(machine.uc.reg_read(R.UC_ARM_REG_CPSR) & 0xFF, machine.control)
        for register, value in machine.initial.items():
            self.assertEqual(machine.uc.reg_read(register), value, f'register {register}')
        expected = [dict(index=1, scope=0, control=machine.control & ~0x80)] if released else []
        self.assertEqual(machine.releases, expected)
        self.assertEqual(machine.u32(SEMA), int(released) if available is None else available)
        self.assertEqual(machine.u32(SCOPE), scope)

    def test_normal_return_preserves_arguments_and_outgoing_stack_space(self):
        m = Machine()
        m.run()
        self.assert_returned(m)
        self.assertEqual(m.u32(SUCCESS), 1)
        self.assertEqual([m.u32(ARG_CHECK + i * 4) for i in range(4)], [10, 11, 12, 13])
        self.assertEqual((m.u32(FAULT), m.u32(MODE), m.u32(GEN)), (0, 1, 7))

    def test_take_and_close_restore_bare_and_allocated_native_frames(self):
        for bare in (False, True):
            with self.subTest(bare=bare):
                m = Machine()
                m.put(SEMA, 1)
                m.run(native=True, bare=bare)
                self.assert_returned(m)
                self.assertEqual(m.acquires, [(1, 0)])
                self.assertEqual(m.u32(SUCCESS), 1)

    def test_close_snapshots_the_lease_before_an_interrupt_reuses_the_freed_stack(self):
        for bare in (False, True):
            with self.subTest(bare=bare):
                m = Machine()
                m.put(SEMA, 1)
                interrupted = self.overwrite_released_context(m)
                m.run(native=True, bare=bare)
                self.assertTrue(interrupted['overwritten'])
                self.assert_returned(m)
                self.assertEqual(m.u32(FAULT), 0)

    def test_abort_restores_saved_registers_before_an_interrupt_reuses_the_freed_stack(self):
        m = Machine(polls=1)
        interrupted = self.overwrite_released_context(m)
        m.run(deep=True)
        self.assertTrue(interrupted['overwritten'])
        self.assert_returned(m)
        self.assertEqual((m.u32(SUCCESS), m.u32(FAULT)), (0, 1))

    def test_borrowed_close_restores_the_stack_without_releasing_the_lease(self):
        for bare in (False, True):
            with self.subTest(bare=bare):
                m = Machine(irq=True)
                m.run(borrowed=True, close=True, bare=bare)
                self.assert_returned(m, released=False)
                self.assertEqual(m.u32(SUCCESS), 1)

    def test_native_refusal_keeps_the_free_resource_count_unchanged(self):
        m = Machine(irq=True)
        m.put(SEMA, 1)
        m.run(native=True, bare=True)
        self.assert_returned(m, released=False, available=1)
        self.assertEqual(m.acquires, [(1, -25)])
        self.assertEqual((m.u32(SUCCESS), m.u32(FAULT)), (0, 1))

    def test_poll_exhaustion_exits_the_void_call_without_publishing_success(self):
        for irq in (False, True):
            with self.subTest(irq=irq):
                m = Machine(polls=3, irq=irq)
                m.run(ticks=3)
                self.assert_returned(m)
                self.assertEqual(m.u32(SUCCESS), 0)
                self.assertEqual((m.u32(FAULT), m.u32(MODE), m.u32(GEN)), (1, 2, 8))

    def test_a_timeout_unwinds_deeper_native_frames_and_their_callee_saved_registers(self):
        m = Machine(polls=3)
        m.run(ticks=3, deep=True)
        self.assert_returned(m)
        self.assertEqual(m.u32(SUCCESS), 0)

    def test_an_inactive_poll_does_not_release_another_resource_or_latch_a_fault(self):
        for pointer in (0, 0xFFFFFFFF):
            with self.subTest(pointer=pointer):
                m = Machine()
                m.put(SCOPE, pointer)
                m.uc.reg_write(R.UC_ARM_REG_SP, STACK)
                m.uc.reg_write(R.UC_ARM_REG_LR, TRAP)
                m.uc.emu_start(m.symbols['native_scope_tick'], TRAP, count=1000)
                self.assertEqual(m.releases, [])
                self.assertEqual(m.u32(FAULT), 0)
                self.assertEqual(m.u32(GEN), 7)

    def test_a_borrowed_resource_remains_owned_by_its_outer_caller(self):
        for irq in (False, True):
            for ticks, failed in ((1, False), (3, True)):
                with self.subTest(ticks=ticks, irq=irq):
                    m = Machine(polls=3, irq=irq)
                    m.run(ticks=ticks, borrowed=True)
                    self.assert_returned(m, released=False)
                    self.assertEqual(m.u32(SUCCESS), int(not failed))
                    self.assertEqual(m.u32(FAULT), int(failed))

    def test_refused_acquisition_aborts_without_releasing_any_resource(self):
        for irq in (False, True):
            with self.subTest(irq=irq):
                m = Machine(irq=irq)
                m.run(refused=True)
                self.assert_returned(m, released=False)
                self.assertEqual(m.u32(SUCCESS), 0)
                self.assertEqual((m.u32(FAULT), m.u32(MODE), m.u32(GEN)), (1, 2, 8))

    def test_a_refused_intruder_preserves_the_active_owners_recovery_frame(self):
        m = Machine(irq=True)
        outer = STATE + 0x500
        m.put(SCOPE, outer)
        m.run(refused=True)
        self.assert_returned(m, released=False, scope=outer)
        self.assertEqual((m.u32(SUCCESS), m.u32(FAULT)), (0, 1))

    def test_the_owner_unwinds_after_a_refused_interrupt_without_a_second_fault(self):
        m = Machine()
        m.run(intruder=True, deep=True)
        self.assert_returned(m)
        self.assertEqual(m.u32(SUCCESS), 0)
        self.assertEqual((m.u32(FAULT), m.u32(MODE), m.u32(GEN)), (1, 2, 8))

    def test_deadline_exits_before_the_poll_budget(self):
        m = Machine(polls=100, step=p.DEADLINE_TICKS)
        m.run()
        self.assert_returned(m)
        self.assertEqual(m.u32(SUCCESS), 0)
        self.assertEqual(m.u32(FAULT), 1)

    def test_a_timer_wrap_keeps_a_short_operation_valid(self):
        m = Machine(step=10, start=p.TIMER_HZ - 5)
        m.run()
        self.assert_returned(m)
        self.assertEqual(m.u32(SUCCESS), 1)

    def test_disabled_timer_still_has_an_independent_poll_bound(self):
        m = Machine(polls=3, clock=False)
        m.run(ticks=3)
        self.assert_returned(m)
        self.assertEqual(m.u32(SUCCESS), 0)
        self.assertEqual(m.u32(FAULT), 1)

    def test_a_preexisting_fault_does_not_advance_the_generation_again(self):
        m = Machine()
        m.put(FAULT, 1)
        m.run()
        self.assert_returned(m)
        self.assertEqual(m.u32(SUCCESS), 0)
        self.assertEqual(m.u32(GEN), 7)


if __name__ == '__main__':
    unittest.main()
