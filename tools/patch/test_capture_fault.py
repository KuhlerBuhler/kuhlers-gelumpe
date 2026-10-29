"""Capture failure branches on generated ARM frames, without firmware data."""
import struct
import unittest

import arm
import capture_fault
import unicorn
from unicorn import arm_const as R

CODE, FAULT, DATA = 0xC1000000, 0xC1100000, 0xC1100100
STACK, TRAP, CONTROL = 0xC11F0000, 0xC1101000, DATA + 16
READ, STOP = CODE + 0x4000, CODE + 0x4100


class Guards(unittest.TestCase):
    def test_start_and_poll_entries_refuse_faults_and_preserve_native_prologues(self):
        for label, resume, body in (
            ('capture_start_entry', 0xC0082F20, 'mov r0, #1\npop {r3-r7, pc}'),
            ('capture_poll_entry', 0xC004F210, 'mov r0, #1\nadd sp, sp, #8\npop {r4, pc}'),
        ):
            for fault in (0, 1, 0xFFFFFFFF):
                with self.subTest(label=label, fault=fault):
                    uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
                    uc.mem_map(0xC0000000, 0x02000000)
                    code, labels = capture_fault.build_code(CODE, fault=FAULT)
                    uc.mem_write(CODE, code)
                    uc.mem_write(FAULT, struct.pack('<I', fault))
                    uc.mem_write(resume, arm.assemble(body, origin=resume).bytes)
                    uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
                    uc.reg_write(R.UC_ARM_REG_SP, STACK)
                    uc.reg_write(R.UC_ARM_REG_LR, TRAP)
                    uc.emu_start(labels[label], TRAP, count=1000)
                    self.assertEqual(uc.reg_read(R.UC_ARM_REG_SP), STACK)
                    self.assertEqual(uc.reg_read(R.UC_ARM_REG_PC), TRAP)
                    self.assertEqual(uc.reg_read(R.UC_ARM_REG_R0), int(fault != 1))

    def run_capture(self, fault=0, during=0):
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        uc.mem_map(0xC0000000, 0x02000000)
        code, labels = capture_fault.build_code(CODE, fault=FAULT)
        uc.mem_write(CODE, code)
        uc.mem_write(FAULT, struct.pack('<I', fault))
        uc.mem_write(CONTROL, struct.pack('<I', during))
        pieces = {
            0xC004F12C: f"sub sp, sp, #20\nmov r7, r0\nbl {READ}\nb {labels['capture_finish_read']}",
            0xC004F160: f"ldr r12, ={DATA}\nmov r0, #1\nstr r0, [r12]\nb 0xc004f1f4\n.pool",
            0xC004F1F4: "add sp, sp, #20\npop {r4-r11, pc}",
            0xC004EF94: "ldr r0, =501\nbx lr\n.pool",
            0xC0082D40: f"push {{r0-r2, r4-r9, lr}}\nb {labels['capture_stop_record']}",
            0xC0082DAC: f"bl {STOP}\nb {labels['capture_stop_command']}",
            0xC0082DDC: f"ldr r0, =501\nbl {labels['capture_finish_entry']}\nb {labels['capture_stop_finish']}\n.pool",
            0xC0082E60: f"bne normal\nldr r12, ={DATA + 12}\nmov r0, #99\nstr r0, [r12]\nnormal:\nldr r12, ={DATA + 8}\nmov r0, #12\nstr r0, [r12]\nb 0xc0082f08\n.pool",
            0xC0082F08: "add sp, sp, #12\npop {r4-r9, pc}",
            STOP: f"ldr r12, ={CONTROL}\nldr r0, [r12]\ncmp r0, #1\nldreq r12, ={FAULT}\nstreq r0, [r12]\nbx lr\n.pool",
            READ: f"ldr r12, ={DATA + 4}\nmov r0, #1\nstr r0, [r12]\nldr r12, ={CONTROL}\nldr r0, [r12]\ncmp r0, #2\nldreq r12, ={FAULT}\nmoveq r0, #1\nstreq r0, [r12]\nmov r0, #400\nbx lr\n.pool",
        }
        for address, assembly in pieces.items():
            uc.mem_write(address, arm.assemble(assembly, origin=address).bytes)
        uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
        uc.reg_write(R.UC_ARM_REG_SP, STACK)
        uc.reg_write(R.UC_ARM_REG_LR, TRAP)
        initial = {R.UC_ARM_REG_R4 + i: 0x1000 + i for i in range(8)}
        for register, value in initial.items():
            uc.reg_write(register, value)
        uc.emu_start(0xC0082D40, TRAP, count=10_000)
        self.assertEqual(uc.reg_read(R.UC_ARM_REG_PC), TRAP)
        self.assertEqual(uc.reg_read(R.UC_ARM_REG_SP), STACK)
        self.assertEqual(uc.reg_read(R.UC_ARM_REG_CPSR) & 0xFF, 0x13)
        for register, value in initial.items():
            self.assertEqual(uc.reg_read(register), value)
        return struct.unpack('<4I', uc.mem_read(DATA, 16))

    def test_a_healthy_or_uninitialized_transport_keeps_native_completion(self):
        for fault in (0, 0xFFFFFFFF):
            with self.subTest(fault=fault):
                self.assertEqual(self.run_capture(fault), (1, 1, 12, 0))

    def test_a_preexisting_fault_does_not_begin_capture_completion(self):
        self.assertEqual(self.run_capture(1), (0, 0, 0, 0))

    def test_a_failed_stop_does_not_read_an_end_pointer_or_publish_a_sample(self):
        self.assertEqual(self.run_capture(during=1), (0, 0, 0, 0))

    def test_a_failed_end_read_does_not_publish_metadata_or_recorded_state(self):
        self.assertEqual(self.run_capture(during=2), (0, 1, 0, 0))


if __name__ == '__main__':
    unittest.main()
