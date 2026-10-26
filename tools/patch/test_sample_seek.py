import struct
import unittest
from importlib.util import find_spec

import arm
import sample_seek


@unittest.skipUnless(find_spec('unicorn'), 'Unicorn not installed')
class SeekTests(unittest.TestCase):
    def run_seek(self, current=90000, target=70000, anchor=65000, flags=1, error=0, other_file=False, via_parser=False):
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR
        uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        for addr in [0xC0180000, 0xC0090000, 0xC2000000]:
            uc.mem_map(addr, 0x10000)
        source = sample_seek.seek_source(0xC009E404, 'test')
        if via_parser:
            source += '.org 0xC0183500\n' + sample_seek.parser_source(0xC0183600, 'test')
            source += '''
.org 0xC0183600
    sub sp, sp, #0x4C0
    sub sp, sp, #12
    ldr r2, =90000
    str r2, [r0, #8]
    ldr r2, =900
    str r2, [r0, #0x14]
    ldr r1, =70000
    bl test_seek
    add sp, sp, #0x4C0
    add sp, sp, #12
    pop {r4-r11, pc}
.pool
'''
        code = arm.assemble(source, 0xC0183400)
        for at, data in code.sections:
            uc.mem_write(at, data)
        # The callee records the cursor and cluster it receives, then seeks.
        callee = arm.assemble('''
    ldr r2, [r0, #8]
    str r2, [r0, #0x100]
    ldr r2, [r0, #0x14]
    str r2, [r0, #0x104]
    str r1, [r0, #8]
    mov r0, #0
    bx lr
''', 0xC009E404).bytes
        uc.mem_write(0xC009E404, callee)
        fil, stack = 0xC2000000, 0xC2007000
        uc.mem_write(fil + 6, bytes([flags, error]))
        uc.mem_write(fil + 8, struct.pack('<I', anchor if via_parser else current))
        uc.mem_write(fil + 0x14, struct.pack('<I', 650 if via_parser else 900))
        uc.mem_write(fil + 0x18, struct.pack('<I', 12345))
        uc.mem_write(stack + sample_seek.FRAME, struct.pack('<3I', fil + (4 if other_file else 0), anchor, 650))
        uc.reg_write(UC_ARM_REG_SP, stack)
        uc.reg_write(UC_ARM_REG_LR, 0xC200FFF0)
        uc.reg_write(UC_ARM_REG_R0, fil)
        uc.reg_write(UC_ARM_REG_R1, target)
        uc.emu_start(code.symbols['test_entry' if via_parser else 'test_seek'], 0xC200FFF0, count=200)
        self.assertEqual(uc.reg_read(UC_ARM_REG_R0), 0)
        self.assertEqual(uc.reg_read(UC_ARM_REG_SP), stack)
        self.assertEqual(struct.unpack('<I', uc.mem_read(fil + 8, 4))[0], target)
        self.assertEqual(struct.unpack('<I', uc.mem_read(fil + 0x18, 4))[0], 12345)
        return struct.unpack('<2I', uc.mem_read(fil + 0x100, 8))

    def test_backward_seek_starts_at_sample_anchor(self):
        self.assertEqual(self.run_seek(), (65000, 650))

    def test_anchor_is_owned_by_the_parser_stack_frame(self):
        self.assertEqual(self.run_seek(via_parser=True), (65000, 650))

    def test_forward_seek_keeps_current_cursor(self):
        self.assertEqual(self.run_seek(target=100000), (90000, 900))

    def test_target_before_anchor_is_left_to_fatfs(self):
        self.assertEqual(self.run_seek(target=64000), (90000, 900))

    def test_write_handle_error_and_other_file_are_left_to_fatfs(self):
        for args in [{'flags': 3}, {'flags': 0}, {'error': 1}, {'other_file': True}]:
            with self.subTest(args=args):
                self.assertEqual(self.run_seek(**args), (90000, 900))


if __name__ == '__main__':
    unittest.main()
