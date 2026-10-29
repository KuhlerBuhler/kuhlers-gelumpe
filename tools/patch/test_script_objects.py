"""The object tree of API 10 (tools/patch/script_objects.s): get, set, clamp, wrong leaves and the repair at start."""
import pathlib
import struct
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import UNICORN_AVAILABLE
from tools.patch import test_script_hooks as hooks_tests

INTENSITY, REPAIRS, NO_LEAF = 0, 1, 4      # data/script/objects.mjs (2 and 3 are the test mode and keepAwake)
ERR_OK, ERR_API_ARG = 0, 15

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
        self.assertEqual(object_rows(include).count('.word'),count)
        m,s = self.machine()
        row = m.uc.mem_read(s['objects_table'],20)
        self.assertEqual(struct.unpack_from('<4i',row),(-0x20,0,15,15))
        self.assertEqual(tuple(row[16:20]),(0,0,1,5))

if __name__ == '__main__':
    unittest.main()
