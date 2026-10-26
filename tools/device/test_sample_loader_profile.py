import struct
import unittest
import zlib
from importlib.util import find_spec

import sample_loader_profile as profile


class RelocationTests(unittest.TestCase):
    def test_calls_outside_copy_keep_destination(self):
        old, new, target = 0xC0035B10, 0xC1004000, 0xC009DD74
        code = profile.branch(old, target, link=True)
        relocated = profile.relocate(code, old, new, [(old, old + 4)], {})
        self.assertEqual(profile.destination(new, struct.unpack('<I', relocated)[0]), target)

    def test_internal_calls_and_literals_stay_relative(self):
        old, new = 0xC0035B10, 0xC1004000
        code = profile.branch(old, old + 8, link=True) + struct.pack('<II', 0xE59F0000, 0xEA123456)
        relocated = profile.relocate(code, old, new, [(old, old + 8)], {})
        self.assertEqual(relocated, code)

    def test_only_selected_calls_are_instrumented(self):
        old, new, target, wrapper = 0xC0035B10, 0xC1004000, 0xC009DD74, 0xC1001000
        code = profile.branch(old, target, link=True)
        relocated = profile.relocate(code, old, new, [(old, old + 4)], {target: wrapper})
        self.assertEqual(profile.destination(new, struct.unpack('<I', relocated)[0]), wrapper)

    def test_branch_range_is_checked(self):
        with self.assertRaises(ValueError):
            profile.branch(0xC1000000, 0x1000)


class CleanupTests(unittest.TestCase):
    class Link:
        idle = True

        def __init__(self, failure=None, uncertain=False):
            self.failure, self.uncertain = failure, uncertain
            self.executions, self.restored = 0, False

        def read(self, address, length):
            return bytes([0xA5]) * length if address == profile.STUB else struct.pack('<I', 1)

        def execute(self, source):
            self.executions += 1
            return 0xC0700000 if self.executions == 1 else 0

        def upload(self, address, data):
            if self.uncertain:
                self.idle = False
            if self.failure:
                raise self.failure

        def write(self, data):
            self.restored = data == bytes([0xA5]) * 1024

    def test_transport_start_frees_allocation_and_restores_stub(self):
        link = self.Link()
        with self.assertRaisesRegex(ValueError, 'transport started'):
            profile.measure(link, bytes(0x200000), False, False, False)
        self.assertEqual(link.executions, 2)
        self.assertTrue(link.restored)

    def test_timeout_never_frees_or_writes_again(self):
        link = self.Link(TimeoutError('no answer'))
        with self.assertRaises(TimeoutError):
            profile.measure(link, bytes(0x200000), False, False, False)
        self.assertEqual(link.executions, 1)
        self.assertFalse(link.restored)

    def test_uncertain_exec_never_frees_or_writes_again(self):
        link = self.Link(ValueError('unexpected EXEC address'), uncertain=True)
        with self.assertRaisesRegex(ValueError, 'unexpected EXEC'):
            profile.measure(link, bytes(0x200000), False, False, False)
        self.assertEqual(link.executions, 1)
        self.assertFalse(link.restored)


@unittest.skipUnless(find_spec('unicorn'), 'Unicorn not installed')
class ExecutionTests(unittest.TestCase):
    def machine(self):
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_MEM_READ
        from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR
        machine = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        for address, size in [(profile.STUB, 0x10000), (0xC2000000, 0x10000),
                              (0xC0090000, 0x10000), (0xC0040000, 0x10000),
                              (0xC06A0000, 0x10000), (profile.TIMER, 0x1000)]:
            machine.mem_map(address, size)
        machine.mem_write(profile.STUB, profile.build(bytes(0x200000)))
        machine.mem_write(profile.TIMER + 0x18, struct.pack('<I', 149999999))
        machine.reg_write(UC_ARM_REG_SP, 0xC200F000)
        machine.reg_write(UC_ARM_REG_LR, 0xC200FFF0)
        self.clock = 149999750

        def clock(uc, access, address, size, value, user):
            self.clock = (self.clock + 150) % 150000000
            uc.mem_write(address, struct.pack('<I', self.clock))

        machine.hook_add(UC_HOOK_MEM_READ, clock, begin=profile.TIMER + 0x10, end=profile.TIMER + 0x10)
        return machine

    def test_read_wrapper_preserves_arguments_and_registers(self):
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4
        machine = self.machine()
        body = profile.arm.assemble('str r2, [r3]\nmov r0, #0\nbx lr', 0xC009DD74).bytes
        machine.mem_write(0xC009DD74, body)
        machine.reg_write(UC_ARM_REG_R2, 1234)
        machine.reg_write(UC_ARM_REG_R3, 0xC2000000)
        machine.reg_write(UC_ARM_REG_R4, 0x12345678)
        machine.emu_start(profile.STUB + 0x800, 0xC200FFF0, count=500)
        self.assertEqual(machine.reg_read(UC_ARM_REG_R0), 0)
        self.assertEqual(machine.reg_read(UC_ARM_REG_R4), 0x12345678)
        self.assertEqual(struct.unpack('<3I', machine.mem_read(profile.RESULT + 0x40, 12)), (1, 150, 1234))

    def test_conversion_preserves_pcm_and_counts_only_its_span(self):
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R7, UC_ARM_REG_R9
        machine = self.machine()
        source = bytes((n * 37) % 256 for n in range(93))
        machine.mem_write(0xC2000000, source + b'guard')
        machine.reg_write(UC_ARM_REG_R0, 0)
        machine.reg_write(UC_ARM_REG_R7, 0xC2000000)
        machine.reg_write(UC_ARM_REG_R9, len(source) // 3)
        machine.emu_start(profile.STUB + 0xD00, 0xC200FFF0, count=2000)
        expected = b''.join(source[at + 1:at + 3] for at in range(0, len(source), 3))
        self.assertEqual(bytes(machine.mem_read(0xC2000000, len(expected))), expected)
        self.assertEqual(bytes(machine.mem_read(0xC2000000 + len(source), 5)), b'guard')
        self.assertEqual(struct.unpack('<3I', machine.mem_read(profile.RESULT + 0x90, 12)), (1, 150, 62))

    def test_dsp_checksum_matches_crc32(self):
        from unicorn.arm_const import UC_ARM_REG_R0
        machine = self.machine()
        data = bytes((n * 37) % 256 for n in range(64))
        machine.mem_write(0xC2000000, data)
        read = profile.arm.assemble('''
    ldr r1, =0xC2000000
    mov r2, r2, lsl #1
copy:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne copy
    bx lr
.pool
''', 0xC004EDDC).bytes
        machine.mem_write(0xC004EDDC, read)
        machine.reg_write(UC_ARM_REG_R0, 0x365EC0 + len(data))
        machine.emu_start(profile.STUB + 0x2800, 0xC200FFF0, count=5000)
        self.assertEqual(machine.reg_read(UC_ARM_REG_R0), zlib.crc32(data))


if __name__ == '__main__':
    unittest.main()
