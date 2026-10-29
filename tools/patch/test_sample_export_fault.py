"""Native export error routing on generated ARM frames."""
import struct
import unittest

import arm
import sample_export_fault
import unicorn
from unicorn import arm_const as R

CODE, FAULT, DATA = 0xC1000000, 0xC1100000, 0xC1100100
STACK, TRAP, READ = 0xC11F0000, 0xC1101000, CODE + 0x4000


class ExportFault(unittest.TestCase):
    def machine(self):
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        uc.mem_map(0xC0000000, 0x02000000)
        code, labels = sample_export_fault.build_code(CODE, fault=FAULT)
        uc.mem_write(CODE, code)
        uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
        uc.reg_write(R.UC_ARM_REG_SP, STACK)
        uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        return uc, labels

    def test_high_entry_refuses_before_open_and_forwards_the_native_error_mapper(self):
        for fault in (0, 1, 0xFFFFFFFF):
            with self.subTest(fault=fault):
                uc, labels = self.machine()
                uc.mem_write(FAULT, struct.pack('<I', fault))
                for at, text in {
                    0xC0039CC8: f'ldr r12, ={DATA}\nmov r0, #1\nstr r0, [r12]\nmov r0, #0\npop {{r4-r10, pc}}\n.pool',
                    0xC0035428: 'add r0, r0, #10\nbx lr',
                }.items():
                    uc.mem_write(at, arm.assemble(text, origin=at).bytes)
                uc.emu_start(labels['export_sample_entry'], TRAP, count=1000)
                self.assertEqual(uc.reg_read(R.UC_ARM_REG_SP), STACK)
                self.assertEqual(uc.reg_read(R.UC_ARM_REG_R0), 11 if fault == 1 else 0)
                self.assertEqual(struct.unpack('<I', uc.mem_read(DATA, 4))[0], int(fault != 1))

    def test_failed_read_skips_pcm_and_trailer_then_releases_the_work_buffer(self):
        for initial, during in ((0, 0), (0xFFFFFFFF, 0), (1, 0), (0, 1)):
            with self.subTest(initial=initial, during=during):
                uc, labels = self.machine()
                uc.mem_write(FAULT, struct.pack('<I', initial))
                pieces = {
                    0xC0039B30: f'sub sp, sp, #0x4c\nldr r12, ={DATA}\nmov r0, #1\nstr r0, [r12]\nmov r6, #73\nbl {READ}\nb {labels["export_sample_read"]}\n.pool',
                    0xC0039C34: f'ldr r12, ={DATA + 4}\nstr r0, [r12]\nmov r5, #0\nb 0xc0039c58\n.pool',
                    0xC0039C58: f'ldr r12, ={DATA + 8}\nldr r0, [r12]\nadd r0, r0, #1\nstr r0, [r12]\nmov r0, r5\nadd sp, sp, #0x4c\npop {{r4-r11, pc}}\n.pool',
                    READ: f'ldr r12, ={FAULT}\nmov r0, #{during}\nstr r0, [r12]\nbx lr\n.pool',
                }
                for at, text in pieces.items():
                    uc.mem_write(at, arm.assemble(text, origin=at).bytes)
                saved = {R.UC_ARM_REG_R4 + i: 0x1000 + i for i in range(8)}
                for register, value in saved.items():
                    uc.reg_write(register, value)
                uc.emu_start(labels['export_writer_entry'], TRAP, count=1000)
                words = struct.unpack('<3I', uc.mem_read(DATA, 12))
                self.assertEqual(words, (0, 0, 0) if initial == 1 else (1, 0 if during else 73, 1))
                self.assertEqual(uc.reg_read(R.UC_ARM_REG_R0), int(initial == 1 or during == 1))
                self.assertEqual(uc.reg_read(R.UC_ARM_REG_SP), STACK)
                for register, value in saved.items():
                    self.assertEqual(uc.reg_read(register), value)


if __name__ == '__main__':
    unittest.main()
