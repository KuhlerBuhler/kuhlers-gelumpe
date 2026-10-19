"""Native clock and read-only views of the firmware's state, without firmware bytes."""
import pathlib
import struct
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import contract_data, UNICORN_AVAILABLE
from tools.patch import test_script_hooks as hooks_tests

CLOCK_INIT, CLOCK_LAST, CLOCK_REM, CLOCK_MS = 208, 212, 216, 220
TICKS_PER_MS = 150000
PERIOD = 150_000_000

@unittest.skipUnless(UNICORN_AVAILABLE,'Unicorn is required for native hardware tests')
class NativeHardwareTests(unittest.TestCase):
    def machine(self):
        m,built = hooks_tests.HookTests().machine()
        return m,built

    def timer(self,m,value): m.uc.mem_write(m.timer,struct.pack('<I',value & 0xffffffff))

    def test_the_clock_counts_milliseconds_from_timer_ticks_and_keeps_the_remainder(self):
        m,_ = self.machine()
        self.timer(m,1000)
        self.assertEqual(m.call('script_clock_millis_glue'),(0,0))
        self.timer(m,1000 + 37 * TICKS_PER_MS + 10)
        self.assertEqual(m.call('script_clock_millis_glue'),(37,0))
        self.assertEqual(m.read(m.runtime+CLOCK_REM),10)
        self.timer(m,1000 + 37 * TICKS_PER_MS + 10 + TICKS_PER_MS - 11)
        self.assertEqual(m.call('script_clock_millis_glue')[0],37)
        self.timer(m,1000 + 38 * TICKS_PER_MS + 10 - 10 + 10)
        self.assertEqual(m.call('script_clock_millis_glue')[0],38)

    def test_the_clock_survives_the_wrap_of_the_timer_at_its_one_second_period(self):
        m,_ = self.machine()
        start = PERIOD - 1000
        self.timer(m,start)
        m.call('script_clock_millis_glue')
        for step in range(1,12):
            self.timer(m,(start + step * 6_000_000) % PERIOD)
            ms = m.call('script_clock_millis_glue')[0]
            self.assertEqual(ms,(step * 6_000_000) // TICKS_PER_MS)

    def test_a_long_gap_is_counted_in_full(self):
        m,_ = self.machine()
        self.timer(m,5)
        m.call('script_clock_update',m.runtime)
        self.timer(m,5 + 400 * TICKS_PER_MS)
        self.assertEqual(m.call('script_clock_update',m.runtime)[0],400)

    def test_reads_return_the_firmware_state_words(self):
        m,_ = self.machine()
        m.write(0xC06BC318,4); m.write(0xC0691518,1234); m.write(0xC06B2420,77); m.write(0xC06B2428,16)
        for part in range(16):
            m.write(0xC06904B0 + 0x48 * part,part + 40)
            m.uc.mem_write(0xC06B2F9D + 0x330 * part,bytes([part % 3]))
        self.assertEqual(m.call('script_read_transport_glue')[0],4)
        self.assertEqual(m.call('script_read_tempo_glue')[0],1234)
        self.assertEqual(m.call('script_read_pattern_glue')[0],77)
        self.assertEqual(m.call('script_read_part_glue')[0],16)
        for part in range(16):
            self.assertEqual(m.call('script_read_step_glue',part),(part + 40,0))
            self.assertEqual(m.call('script_read_mute_glue',part),(1 if part % 3 else 0,0))
        error = contract_data()['error']['API_ARG']
        self.assertEqual(m.call('script_read_step_glue',16),(0,error))
        self.assertEqual(m.call('script_read_mute_glue',99),(0,error))

    def test_the_input_filter_keeps_the_last_value_of_each_knob(self):
        m,_ = self.machine()
        h = hooks_tests.HookTests()
        m.write(m.runtime+148,0xffffffff)
        h.input(m,[2,3,1,244,0])
        h.input(m,[2,3,0,9,0])
        h.input(m,[2,19,3,255,0])
        h.input(m,[2,20,0,5,0])
        self.assertEqual(m.call('script_read_knob_glue',3),(9,0))
        self.assertEqual(m.call('script_read_knob_glue',19),(1023,0))
        self.assertEqual(m.call('script_read_knob_glue',0),(0,0))
        self.assertEqual(m.call('script_read_knob_glue',20),(0,contract_data()['error']['API_ARG']))

    def stubs(self,m):
        """`bx lr` at each firmware function the actions call, recording the registers it was called with."""
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR, UC_ARM_REG_PC
        m.uc.mem_map(0xC0040000,0x43000)
        names = {0xC0042BB8:'key',0xC0081F50:'pattern',0xC0081BB4:'part',0xC004A80C:'tempo',0xC0060C74:'mute'}
        calls = []
        for address in names: m.uc.mem_write(address,struct.pack('<I',0xE12FFF1E))
        def record(uc,address,size,_):
            calls.append((names[address],uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1),uc.reg_read(UC_ARM_REG_R2)))
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        for address in names: m.uc.hook_add(UC_HOOK_CODE,record,begin=address,end=address)
        return calls

    def test_actions_call_the_firmware_with_the_documented_arguments(self):
        m,_ = self.machine()
        calls = self.stubs(m)
        error = contract_data()['error']['API_ARG']
        self.assertEqual(m.call('script_play_glue'),(0,0))
        self.assertEqual(m.call('script_stop_glue'),(0,0))
        self.assertEqual(calls,[('key',2,1,calls[0][3]),('key',2,0,calls[1][3]),('key',1,1,calls[2][3]),('key',1,0,calls[3][3])])
        calls.clear()
        self.assertEqual(m.call('script_pattern_glue',249),(0,0))
        self.assertEqual(calls,[('pattern',0xC06B2108,249,1)])
        self.assertEqual(m.call('script_pattern_glue',250),(0,error))
        calls.clear()
        self.assertEqual(m.call('script_tempo_glue',1500),(0,0))
        self.assertEqual(calls,[('tempo',0xC06B2798,1500,1)])
        for bad in (99,3001,0): self.assertEqual(m.call('script_tempo_glue',bad),(0,error))
        self.assertEqual(m.call('script_tempo_glue',100)[1],0)
        self.assertEqual(m.call('script_tempo_glue',3000)[1],0)
        calls.clear()
        self.assertEqual(m.call('script_part_glue',15),(0,0))
        self.assertEqual(calls,[('part',0xC06B2108,15,calls[0][3])])
        self.assertEqual(m.call('script_part_glue',16),(0,error))

    def test_mute_presses_the_pad_only_when_the_part_is_not_in_the_wanted_state(self):
        m,_ = self.machine()
        calls = self.stubs(m)
        m.uc.mem_write(0xC06B2F9D + 0x330 * 5,bytes([1]))
        m.uc.mem_write(0xC06B2F9D + 0x330 * 6,bytes([0]))
        self.assertEqual(m.call('script_mute_glue',5,1),(0,0))
        self.assertEqual(calls,[])
        self.assertEqual(m.call('script_mute_glue',5,0),(0,0))
        self.assertEqual([(c[0],c[1],c[2],c[3]) for c in calls],[('mute',0xC06CA760,5,1),('mute',0xC06CA760,5,0)])
        calls.clear()
        m.call('script_mute_glue',6,1)
        self.assertEqual(len(calls),2)
        calls.clear()
        m.call('script_mute_glue',6,0)
        self.assertEqual(calls,[])
        error = contract_data()['error']['API_ARG']
        self.assertEqual(m.call('script_mute_glue',16,0),(0,error))
        self.assertEqual(m.call('script_mute_glue',0,2),(0,error))

    def test_backlight_sets_each_colour_pin_through_the_gpio_function(self):
        m,_ = self.machine()
        m.uc.mem_map(0xC0016000,0x1000); m.uc.mem_map(0xC0087000,0x1000)
        calls = self.hardware_stubs_pages(m)
        self.assertEqual(m.call('script_backlight_glue',1,0,1),(0,0))
        self.assertEqual(calls,[('gpio',0x01E26000,1,3,0x08),('gpio',0x01E26000,0,3,0x10),('gpio',0x01E26000,1,3,0x20)])

    def hardware_stubs_pages(self,m):
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR, UC_ARM_REG_PC
        calls = []
        names = {0xC0016BB4:'gpio',0xC00875F4:'refresh'}
        for address in names: m.uc.mem_write(address,struct.pack('<I',0xE12FFF1E))
        def record(uc,address,size,_):
            calls.append((names[address],uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1),uc.reg_read(UC_ARM_REG_R2),uc.reg_read(UC_ARM_REG_R3)))
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        for address in names: m.uc.hook_add(UC_HOOK_CODE,record,begin=address,end=address)
        return calls

    def test_led_hold_sets_the_firmware_flag_and_gives_every_led_back_when_released(self):
        m,_ = self.machine()
        m.uc.mem_map(0xC0016000,0x1000); m.uc.mem_map(0xC0087000,0x1000); m.uc.mem_map(0xC0700000,0x2000)
        calls = self.hardware_stubs_pages(m)
        manager = 0xC0700000
        m.write(0xC0345A1C,manager)
        self.assertEqual(m.call('script_led_hold_glue',1),(0,0))
        self.assertEqual(bytes(m.uc.mem_read(manager + 0xB98,1)),b'\x01')
        self.assertEqual(calls,[])
        self.assertEqual(m.read(m.runtime+252),1)
        self.assertEqual(m.call('script_led_hold_glue',1),(0,0))
        self.assertEqual(m.call('script_led_hold_glue',0),(0,0))
        self.assertEqual(bytes(m.uc.mem_read(manager + 0xB98,1)),b'\x00')
        self.assertEqual(calls,[('refresh',manager,i,1,calls[i][4]) for i in range(0x58)])
        self.assertEqual(m.read(m.runtime+252),0)

    def test_led_hold_does_nothing_without_a_led_manager_and_the_guard_releases_when_no_script_is_armed(self):
        m,_ = self.machine()
        m.uc.mem_map(0xC0016000,0x1000); m.uc.mem_map(0xC0087000,0x1000); m.uc.mem_map(0xC0700000,0x2000)
        calls = self.hardware_stubs_pages(m)
        for bad in (0,0xffffffff):
            m.write(0xC0345A1C,bad)
            self.assertEqual(m.call('script_led_hold_glue',1),(0,0))
            self.assertEqual(m.read(m.runtime+252),0)
        manager = 0xC0700000
        m.write(0xC0345A1C,manager)
        m.call('script_led_hold_glue',1)
        m.call('script_led_hold_guard',m.runtime)
        self.assertEqual(m.read(m.runtime+252),0,'no script at all: the LEDs go back')
        self.assertEqual(len(calls),0x58)
        from tools.patch.test_script_vm import blob
        error,entry = m.load(blob([0],stack=0))
        self.assertEqual(error,0)
        m.run(entry,0)
        calls.clear()
        m.call('script_led_hold_glue',1)
        m.call('script_led_hold_guard',m.runtime)
        self.assertEqual(m.read(m.runtime+252),1,'an armed script keeps the hold')
        m.write(entry+12,3)
        m.call('script_led_hold_guard',m.runtime)
        self.assertEqual(m.read(m.runtime+252),0,'a script that faulted lets the LEDs go')

    def test_the_built_in_app_alone_does_not_keep_the_led_hold(self):
        m,built = self.machine()
        m.uc.mem_map(0xC0016000,0x1000); m.uc.mem_map(0xC0087000,0x1000); m.uc.mem_map(0xC0700000,0x2000)
        self.hardware_stubs_pages(m)
        m.write(0xC0345A1C,0xC0700000)
        from tools.patch.script_hooks import BLECHY_BLOCK
        block = built.sections[-1][1]
        error,him = m.call('script_load_block_ex',m.runtime,BLECHY_BLOCK,len(block),1)
        self.assertEqual(error,0)
        m.write(him+12,2)
        m.call('script_led_hold_glue',1)
        m.call('script_led_hold_guard',m.runtime)
        self.assertEqual(m.read(m.runtime+252),0,'he is armed for good, a plugin that holds the LEDs needs one of its own')
        from tools.patch.test_script_vm import blob
        error,entry = m.load(blob([0],stack=0))
        self.assertEqual(error,0)
        m.run(entry,0)
        m.call('script_led_hold_glue',1)
        m.call('script_led_hold_guard',m.runtime)
        self.assertEqual(m.read(m.runtime+252),1,'an armed plugin of the card keeps the hold')

if __name__ == '__main__':
    unittest.main()
