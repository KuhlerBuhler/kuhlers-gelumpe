"""Display calibration on synthetic RAM and global settings."""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.patch.arm import assemble
from tools.patch.script_vm import build
from tools.patch.test_script_vm import UNICORN_AVAILABLE, contract_data


@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native ARM tests')
class DisplayCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vm = build(contract_data()['include'], origin=0xC0100000)
        constants = f'''
.equ SCREEN_MANAGER, 0xC0300000
.equ SCRIPT_DISPLAY_RAM, 0xC0301000
.equ HOOK_RUNTIME, 0xC0302000
.equ RT_FRAMES, 0
.equ MENU_STATE, 0xC0307000
.equ M_CAL_ON, 0xFA
.equ UI_REDRAW, 0xC0307100
.equ SCRIPT_FONT, {cls.vm.symbols['script_font']}
'''
        cls.code = assemble(constants + (ROOT/'tools/patch/script_calibrate.s').read_text(), origin=0xC018D000)

    def setUp(self):
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
        from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(0xC0000000, 0x400000)
        self.uc.mem_write(self.vm.origin, self.vm.bytes)
        self.uc.mem_write(self.code.origin, self.code.bytes)
        self.uc.reg_write(UC_ARM_REG_SP, 0xC03FF000)
        self.uc.reg_write(UC_ARM_REG_LR, 0xC0000100)
        for at, value in [(0xC033E6A0,0xC0303000),(0xC0300000,0xC0304000),(0xC0304020,0xC0305000),
                          (0xC0304024,0),(0xC030402C,9),(0xC030502C,12)]:
            self.word(at,value)
        self.uc.mem_write(0xC0303022, bytes([31]))
        self.uc.mem_write(0xC0300FF0, bytes([0xA5])*1056)

    def word(self, at, value):
        self.uc.mem_write(at,struct.pack('<I',value & 0xFFFFFFFF))

    def render(self, frame=7):
        from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC
        self.word(0xC0302000,frame)
        self.uc.reg_write(UC_ARM_REG_LR,0xC0000100)
        self.uc.emu_start(self.code.symbols['display_calibrate'],0xC0000100,count=20000)
        self.assertEqual(self.uc.reg_read(UC_ARM_REG_PC),0xC0000100)
        return bytes(self.uc.mem_read(0xC0301000,1024))

    def test_three_balls_have_different_speeds(self):
        picture=self.render(7)
        ball=bytes([0x1C,0x3E,0x7F,0x7F,0x7F,0x3E,0x1C])
        for page,position in [(3,8),(4,14),(5,27)]:
            row=picture[page*128:(page+1)*128]
            self.assertEqual(row,bytes(position)+ball+bytes(128-position-7))
        self.assertEqual(self.render(263),picture)

    def test_only_the_middle_six_display_pages_are_written(self):
        from unicorn import UC_HOOK_MEM_WRITE
        writes=[]
        self.uc.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,at,size,value,data:writes.append((at,size)))
        picture=self.render()
        self.assertEqual(picture[:128],bytes([0xA5])*128)
        self.assertEqual(picture[-128:],bytes([0xA5])*128)
        self.assertTrue(all(0xC0301080<=at and at+size<=0xC0301380 or
                            0xC03FEF00<=at and at+size<=0xC03FF000 or
                            (at,size)==(0xC03070FA,1) for at,size in writes))
        self.assertEqual(bytes(self.uc.mem_read(0xC0303022,1)),bytes([31]))
        self.assertEqual(bytes(self.uc.mem_read(0xC03070FA,1)),bytes([1]))

    def test_every_ball_stays_inside_its_row_across_frame_wrap(self):
        for frame in [*range(256),0x7FFFFFFF,0xFFFFFFFF]:
            picture=self.render(frame)
            for page in [3,4,5]:
                row=picture[page*128:(page+1)*128]
                on=[i for i,value in enumerate(row) if value]
                self.assertEqual(len(on),7)
                self.assertGreaterEqual(on[0],2)
                self.assertLessEqual(on[-1],124)

    def test_other_pages_and_dialogs_keep_their_picture(self):
        for at,value in [(0xC033E6A0,0),(0xC033E6A0,0xFFFFFFFF),
                         (0xC0300000,0),(0xC0300000,0xFFFFFFFF),(0xC0304020,0),
                         (0xC0304024,1),(0xC030402C,1),(0xC030402C,8),
                         (0xC030502C,11),(0xC030502C,13)]:
            with self.subTest(at=at,value=value):
                old=bytes(self.uc.mem_read(at,4));self.word(at,value)
                before=bytes(self.uc.mem_read(0xC0301000,1024))
                self.assertEqual(self.render(),before)
                self.uc.mem_write(at,old)

    def test_contrast_limits_and_value_change_only_affect_the_number(self):
        images=[]
        for value in range(18,43):
            self.uc.mem_write(0xC0303022,bytes([value]));images.append(self.render())
        self.assertEqual(len({im[256:384] for im in images}),25)
        self.assertEqual(len({im[:256]+im[384:] for im in images}),1)
        for value in [0,17,43,255]:
            self.uc.mem_write(0xC0303022,bytes([value]))
            before=bytes(self.uc.mem_read(0xC0301000,1024))
            self.assertEqual(self.render(),before)

    def test_registers_stack_and_instruction_budget(self):
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R4,UC_ARM_REG_SP
        values=[0x12340000+i for i in range(8)]
        for i,value in enumerate(values):self.uc.reg_write(UC_ARM_REG_R4+i,value)
        instructions=[]
        self.uc.hook_add(UC_HOOK_CODE,lambda u,at,size,data:instructions.append(at))
        self.render()
        self.assertEqual([self.uc.reg_read(UC_ARM_REG_R4+i) for i in range(8)],values)
        self.assertEqual(self.uc.reg_read(UC_ARM_REG_SP),0xC03FF000)
        self.assertLess(len(instructions),4000)


if __name__=='__main__':
    unittest.main()
