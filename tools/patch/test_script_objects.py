"""The object tree of API 10 (tools/patch/script_objects.s): get, set, clamp, wrong leaves and the repair at start."""
import pathlib
import struct
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import UNICORN_AVAILABLE
from tools.patch import test_script_hooks as hooks_tests

INTENSITY, REPAIRS, NO_LEAF = 0, 1, 61     # data/script/objects.mjs (2 and 3 are the test mode and keepAwake, 4 to 28 the pages of the menu BLECH, 29 to 47 the Global settings)
ERR_OK, ERR_API_ARG = 0, 15
PATTERN_CONFIRM, TAP_MOTION, NOTE_ASSIST, LAST_PATTERN, STEREO_PAD, INIT_PATTERN, MENU_WRITE = 22, 23, 24, 25, 26, 27, 28

@unittest.skipUnless(UNICORN_AVAILABLE,'Unicorn is required for native object tests')
class NativeObjectTests(unittest.TestCase):
    def machine(self):
        """A machine whose menu_look_apply only counts its calls (it drives the LEDs and the backlight of the firmware)."""
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR
        from tools.patch.script_hooks import MENU_STATE
        m,built = hooks_tests.HookTests().machine()
        s = built.symbols
        self.at = (MENU_STATE + s['MX_INTENS']) & 0xffffffff
        self.applied = []
        def apply(uc,address,size,_):
            self.applied.append(uc.mem_read(self.at,1)[0])
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        m.uc.hook_add(UC_HOOK_CODE,apply,begin=s['menu_look_apply'],end=s['menu_look_apply'])
        if not any(a <= self.at <= b for a,b,_ in m.uc.mem_regions()): m.uc.mem_map(self.at & ~0xFFF,0x1000)   # the menu's state
        m.uc.mem_write(self.at,bytes([15]))
        return m,s

    def repairs(self,m,s): return m.read(s['objects_repairs'])

    def test_get_reads_the_byte_the_menu_keeps(self):
        m,s = self.machine()
        m.uc.mem_write(self.at,bytes([9]))
        self.assertEqual(m.call('script_object_get_glue',INTENSITY,-1 & 0xffffffff),(9,ERR_OK))

    def test_set_writes_applies_and_leaves_the_count_alone_inside_the_range(self):
        m,s = self.machine()
        self.assertEqual(m.call('script_object_set_glue',INTENSITY,-1 & 0xffffffff,0)[1],ERR_OK)
        self.assertEqual(m.uc.mem_read(self.at,1)[0],0)
        self.assertEqual(self.applied,[0])
        self.assertEqual(self.repairs(m,s),0)

    def test_set_outside_the_range_clamps_and_counts(self):
        m,s = self.machine()
        for value,want in ((300,15),(-5 & 0xffffffff,0),(16,15)):
            self.assertEqual(m.call('script_object_set_glue',INTENSITY,-1 & 0xffffffff,value)[1],ERR_OK)
            self.assertEqual(m.uc.mem_read(self.at,1)[0],want,value)
        self.assertEqual(self.repairs(m,s),3)
        self.assertEqual(m.call('script_object_get_glue',REPAIRS,-1 & 0xffffffff),(3,ERR_OK))

    def test_a_leaf_that_does_not_exist_or_is_read_only_is_refused(self):
        m,s = self.machine()
        self.assertEqual(m.call('script_object_get_glue',NO_LEAF,0)[1],ERR_API_ARG)
        self.assertEqual(m.call('script_object_set_glue',NO_LEAF,0,1)[1],ERR_API_ARG)
        self.assertEqual(m.call('script_object_set_glue',REPAIRS,0,0)[1],ERR_API_ARG)
        self.assertEqual(m.call('script_object_get_glue',255,0)[1],ERR_API_ARG)
        self.assertEqual(self.applied,[])

    def test_the_repair_at_start_clamps_a_stored_value_outside_its_range_and_counts_it(self):
        m,s = self.machine()
        m.uc.mem_write(self.at,bytes([200]))
        m.call('objects_repair')
        self.assertEqual(m.uc.mem_read(self.at,1)[0],15)
        self.assertEqual(self.applied,[15])
        self.assertEqual(self.repairs(m,s),1)
        m.call('objects_repair')
        self.assertEqual(self.repairs(m,s),1,'a valid value is left alone')
        self.assertEqual(self.applied,[15])

    def test_the_menu_repairs_once_it_has_read_its_settings(self):
        src = (ROOT/'tools'/'patch'/'script_menu.s').read_text()
        body = src.split('menu_arm_load:',1)[1].split('.pool',1)[0]
        self.assertLess(body.index('bl menu_settings_load'),body.index('bl objects_repair'))

    def test_the_table_has_a_row_for_every_leaf(self):
        from tools.patch.script_hooks import object_rows
        from tools.patch.test_script_vm import contract_data
        include = contract_data()['include']
        count = int(include.split('.equ OBJ_COUNT, ',1)[1].split()[0],0)
        self.assertEqual(object_rows(include).count('_OFFSET'),count)
        self.assertEqual(object_rows(include).count('_MIRROR'),count)
        m,s = self.machine()
        row = m.uc.mem_read(s['objects_table'],28)
        self.assertEqual(struct.unpack_from('<4i',row),(-0x20,0,15,15))
        self.assertEqual(tuple(row[16:20]),(0,0,1,5))
        self.assertEqual(struct.unpack_from('<2I',row,20),(0,0))

    def test_a_setting_word_a_patch_never_wrote_reads_as_the_factory_value(self):
        m,s = self.machine()
        for leaf,at in ((LAST_PATTERN,0xC014FEFC),(STEREO_PAD,0xC014FFFC)):
            if not any(a <= at <= b for a,b,_ in m.uc.mem_regions()): m.uc.mem_map(at & ~0xFFF,0x1000)
            m.uc.mem_write(at,struct.pack('<I',0xFFFFFFFF))
            self.assertEqual(m.call('script_object_get_glue',leaf,-1 & 0xffffffff),(1,ERR_OK),leaf)
            self.assertEqual(m.call('script_object_set_glue',leaf,-1 & 0xffffffff,0)[1],ERR_OK)
            self.assertEqual(struct.unpack('<I',m.uc.mem_read(at,4))[0],0)
            self.assertEqual(m.call('script_object_get_glue',leaf,-1 & 0xffffffff),(0,ERR_OK),leaf)

    def test_a_feature_writes_the_page_word_and_the_word_its_patch_reads(self):
        from tools.patch.script_hooks import MENU_STATE
        m,s = self.machine()
        for leaf,page,patch,value in ((PATTERN_CONFIRM,0x158,0xC0180F10,0),(TAP_MOTION,0x15C,0xC0188F00,2),(NOTE_ASSIST,0xFC,0xC0189F00,0)):
            if not any(a <= patch <= b for a,b,_ in m.uc.mem_regions()): m.uc.mem_map(patch & ~0xFFF,0x1000)
            page_at = (MENU_STATE + page) & 0xffffffff
            if not any(a <= page_at <= b for a,b,_ in m.uc.mem_regions()): m.uc.mem_map(page_at & ~0xFFF,0x1000)
            self.assertEqual(m.call('script_object_set_glue',leaf,-1 & 0xffffffff,value)[1],ERR_OK)
            self.assertEqual(struct.unpack('<I',m.uc.mem_read(page_at,4))[0],value,leaf)
            self.assertEqual(struct.unpack('<I',m.uc.mem_read(patch,4))[0],value,leaf)
            self.assertEqual(m.call('script_object_get_glue',leaf,-1 & 0xffffffff),(value,ERR_OK),leaf)

    def test_a_global_leaf_has_a_word_of_its_own_until_the_firmware_has_the_global_settings(self):
        m,s = self.machine()
        gp = 0xC0691324
        if not any(a <= gp <= b for a,b,_ in m.uc.mem_regions()): m.uc.mem_map(gp & ~0xFFF,0x1000)
        m.uc.mem_write(gp,struct.pack('<I',0))
        self.assertEqual(m.call('script_object_set_glue',INIT_PATTERN,-1 & 0xffffffff,7)[1],ERR_OK)
        self.assertEqual(m.call('script_object_get_glue',INIT_PATTERN,-1 & 0xffffffff),(7,ERR_OK))
        block = 0xC0692000
        if not any(a <= block <= b for a,b,_ in m.uc.mem_regions()): m.uc.mem_map(block & ~0xFFF,0x1000)
        m.uc.mem_write(gp,struct.pack('<I',block))
        m.uc.mem_write(block+247,bytes([42]))
        self.assertEqual(m.call('script_object_get_glue',INIT_PATTERN,-1 & 0xffffffff),(42,ERR_OK))
        self.assertEqual(m.call('script_object_set_glue',INIT_PATTERN,-1 & 0xffffffff,300)[1],ERR_OK)
        self.assertEqual(m.uc.mem_read(block+247,1)[0],250)

    def test_the_write_request_waits_for_the_main_screen_and_one_pause(self):
        m,s = self.machine()
        self.assertEqual(m.call('script_object_set_glue',MENU_WRITE,-1 & 0xffffffff,1)[1],ERR_OK)
        self.assertEqual(m.uc.mem_read(s['objects_write'],1)[0],1)

    GLOBALS_PTR, OBJECT = 0xC0691324, 0xC0700000

    def global_machine(self):
        """A machine with a Global object (the block 4 bytes in) and its metronome setter replaced by a stub that records its calls."""
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2
        from tools.patch.script_hooks import GLOBAL_SETTERS
        m,s = self.machine()
        setter = GLOBAL_SETTERS[16][0]
        for at in (self.GLOBALS_PTR,self.OBJECT,setter):
            if not any(a <= at <= b for a,b,_ in m.uc.mem_regions()): m.uc.mem_map(at & ~0xFFF,0x1000)
        m.uc.mem_write(self.GLOBALS_PTR,struct.pack('<I',self.OBJECT))
        self.calls = []
        def stub(uc,address,size,_):
            self.calls.append((uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1),uc.reg_read(UC_ARM_REG_R2)))
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        m.uc.write = None
        m.uc.mem_write(setter,bytes(4))
        m.uc.hook_add(UC_HOOK_CODE,stub,begin=setter,end=setter)
        return m,s

    def leaf(self,offset):
        """The id of the Global leaf for the dump offset `offset`."""
        from tools.patch.test_script_vm import contract_data
        include = contract_data()['include']
        count = int(include.split('.equ OBJ_COUNT, ',1)[1].split()[0],0)
        return next(i for i in range(count) if include.split(f'.equ OBJ_{i}_BASE, ',1)[1].split()[0] == '3'
                    and int(include.split(f'.equ OBJ_{i}_OFFSET, ',1)[1].split()[0],0) == offset + 4)

    def test_a_global_leaf_reads_the_block_behind_the_pointer(self):
        m,s = self.global_machine()
        m.uc.mem_write(self.OBJECT+4+16,bytes([3]))
        self.assertEqual(m.call('script_object_get_glue',self.leaf(16),-1 & 0xffffffff),(3,ERR_OK))

    def test_a_global_leaf_is_set_through_the_firmware_setter_with_the_object_the_value_and_1(self):
        m,s = self.global_machine()
        self.assertEqual(m.call('script_object_set_glue',self.leaf(16),-1 & 0xffffffff,2)[1],ERR_OK)
        self.assertEqual(self.calls,[(self.OBJECT,2,1)])
        self.assertEqual(m.uc.mem_read(self.OBJECT+4+16,1)[0],0,'the setter writes the byte, not our code')
        for value,want in ((9,4),(-3 & 0xffffffff,0)):
            self.calls.clear()
            m.call('script_object_set_glue',self.leaf(16),-1 & 0xffffffff,value)
            self.assertEqual(self.calls,[(self.OBJECT,want,1)])
        self.assertEqual(self.repairs(m,s),2)

    def test_a_global_leaf_is_refused_before_the_firmware_has_made_the_object(self):
        m,s = self.global_machine()
        m.uc.mem_write(self.GLOBALS_PTR,bytes(4))
        self.assertEqual(m.call('script_object_set_glue',self.leaf(16),-1 & 0xffffffff,1)[1],ERR_API_ARG)
        self.assertEqual(self.calls,[])

    def test_the_repair_at_start_writes_a_global_byte_alone_without_calling_the_setter(self):
        m,s = self.global_machine()
        m.uc.mem_write(self.OBJECT+4+16,bytes([200]))
        m.uc.mem_write(self.OBJECT+4+30,bytes([0]))
        m.call('objects_repair')
        self.assertEqual(m.uc.mem_read(self.OBJECT+4+16,1)[0],4)
        self.assertEqual(m.uc.mem_read(self.OBJECT+4+30,1)[0],18,'LCD CONTRAST starts at 18, not 0')
        self.assertEqual(self.calls,[])
        self.assertEqual(self.repairs(m,s),2,'METRONOME and LCD CONTRAST')

    def test_the_setters_are_those_the_map_lists_for_each_field(self):
        import json, subprocess
        from tools.patch.script_hooks import GLOBAL_SETTERS
        code = ("import m from './data/map/global.mjs';"
                "process.stdout.write(JSON.stringify(m.fields.filter(f => f.live).map(f => [f.where.offset, f.live.setter.hacktribe, f.live.setter.red, f.live.setter.blue])))")
        rows = json.loads(subprocess.run(['node','--input-type=module','-e',code],cwd=ROOT,capture_output=True,text=True,check=True).stdout)
        self.assertEqual({offset:(int(h,16),int(b,16)) for offset,h,r,b in rows},GLOBAL_SETTERS)
        self.assertTrue(all(h == r for _,h,r,_ in rows))

    def test_the_rows_of_a_leaf_with_a_setter_carry_the_setter_of_the_build(self):
        from tools.patch.script_hooks import object_rows, GLOBAL_SETTERS
        from tools.patch.test_script_vm import contract_data
        include = contract_data()['include']
        self.assertIn(f'{GLOBAL_SETTERS[16][0]:#x}',object_rows(include,'hacktribe'))
        self.assertIn(f'{GLOBAL_SETTERS[16][1]:#x}',object_rows(include,'synth'))
        self.assertNotIn(f'{GLOBAL_SETTERS[16][0]:#x}',object_rows(include,'synth'))

if __name__ == '__main__':
    unittest.main()
