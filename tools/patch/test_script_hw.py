"""Native clock and read-only views of the firmware's state, without firmware bytes."""
import json
import pathlib
import subprocess
import struct
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import contract_data, UNICORN_AVAILABLE
from tools.patch import test_script_hooks as hooks_tests

CLOCK_INIT, CLOCK_LAST, CLOCK_REM, CLOCK_MS = 208, 212, 216, 220
OS_TICKS = 0xC06A292C
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

    def test_whole_seconds_timer3_did_not_see_come_from_the_os_tick_count(self):
        m,_ = self.machine()
        self.timer(m,5); m.write(OS_TICKS,1000)
        start = m.call('script_clock_update',m.runtime)[0]
        # 2.4 s later: Timer3 wrapped twice and shows 400 ms, the tick count the whole of it
        self.timer(m,5 + 400 * TICKS_PER_MS); m.write(OS_TICKS,3400)
        self.assertEqual(m.call('script_clock_update',m.runtime)[0] - start,2400)
        # a tick count that lags a little (it stands still for a moment while the device starts) changes nothing
        self.timer(m,5 + 800 * TICKS_PER_MS); m.write(OS_TICKS,3700)
        self.assertEqual(m.call('script_clock_update',m.runtime)[0] - start,2800)
        self.timer(m,5 + 900 * TICKS_PER_MS); m.write(OS_TICKS,4200)
        self.assertEqual(m.call('script_clock_update',m.runtime)[0] - start,2900,'400 ms more ticks than Timer3 shows is no whole second')

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

    def test_pattern_values_read_every_named_field_of_the_pattern_in_ram_and_of_the_bank(self):
        m,_ = self.machine()
        fields = json.loads(subprocess.check_output(['node','--input-type=module','-e',
            "import * as c from './data/script/contract.mjs'; console.log(JSON.stringify({pattern:c.PATTERN_FIELDS,part:c.PART_FIELDS}))"],cwd=ROOT))
        block, bank = 0xC06B2798 + 4, 0xC08B2940
        m.uc.mem_map(bank & ~0xFFF,((bank + 250 * 0x4000 + 0xFFF) & ~0xFFF) - (bank & ~0xFFF))
        error = contract_data()['error']['API_ARG']
        signed = lambda v: struct.unpack('<i',struct.pack('<I',v))[0]
        value = lambda pattern,part,field: m.call('script_read_pattern_value_glue',pattern & 0xffffffff,part & 0xffffffff,field)
        def expect(kind,raw,raw2):
            return {'u8':raw,'s8':raw - 256 if raw > 127 else raw,'u16':raw | raw2 << 8,'bars':(raw & 3) + 1,
                    'chain':raw - 1 if 1 <= raw <= 250 else -1,'atLeast1':max(raw,1)}[kind]
        for pattern,base in [(-1,block),(0,bank),(7,bank + 7 * 0x4000),(249,bank + 249 * 0x4000)]:
            for part,group in [(-1,fields['pattern']),(0,fields['part']),(15,fields['part'])]:
                at = base + (0 if part < 0 else 0x800 + part * 0x330)
                for i,f in enumerate(group):
                    for raw,raw2 in [(0,0),(1,7),(200,1),(255,255),(251,0)]:
                        with self.subTest(pattern=pattern,part=part,field=f['name'],raw=raw):
                            m.uc.mem_write(at + f['offset'],bytes([raw,raw2]) if f['kind'] == 'u16' else bytes([raw]))
                            got,err = value(pattern,part,i)
                            self.assertEqual(err,0)
                            self.assertEqual(signed(got),expect(f['kind'],raw,raw2))
        self.assertEqual(value(-1,-1,len(fields['pattern']))[1],error)
        self.assertEqual(value(-1,0,len(fields['part']))[1],error)

    def test_chain_mode_is_the_global_switch(self):
        m,_ = self.machine()
        for byte,want in [(0,0),(1,1),(7,1)]:
            m.uc.mem_write(0xC06A2A94 + 31,bytes([byte]))
            self.assertEqual(m.call('script_read_chain_mode_glue'),(want,0))

    def test_remap_key_records_the_calling_plugin_and_refuses_exit(self):
        m,built = self.machine()
        remap = built.layout['card'] + built.symbols['RP_AT']
        entry, blob = m.input + 0x6000, m.input + 0x6100
        m.write(entry + 4,blob); m.write(blob + 12,0xCAFE0001)
        m.write(m.runtime + built.symbols['RT_ENTRY'],entry)
        error = contract_data()['error']['API_ARG']
        self.assertEqual(m.call('script_remap_key_glue',17,16),(0,0))
        self.assertEqual((m.read(remap),m.read(remap + 4),m.read(remap + 8)),(entry,0xCAFE0001,17 | 16 << 8))
        self.assertEqual(m.call('script_remap_key_glue',5,5),(0,0))
        self.assertEqual(m.read(remap),0,'the same key twice ends the remap')
        self.assertEqual(m.call('script_remap_key_glue',13,16)[1],error)
        self.assertEqual(m.call('script_remap_key_glue',16,13)[1],error)

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

    def test_seq_writes_steps_of_the_pattern_in_ram_and_the_pads_hear_of_it_once_a_frame(self):
        m,built = self.machine()
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR, UC_ARM_REG_PC
        m.uc.mem_map(0xC0070000,0x1000)
        m.uc.mem_write(0xC0070688,struct.pack('<I',0xE12FFF1E))
        told = []
        def notify(uc,address,size,_):
            told.append((uc.reg_read(UC_ARM_REG_R0),struct.unpack('<II',bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R1),8)))))
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        m.uc.hook_add(UC_HOOK_CODE,notify,begin=0xC0070688,end=0xC0070688)
        error = contract_data()['error']['API_ARG']
        step = lambda part,index: 0xC06B2798 + 4 + 0x800 + 0x330 * part + 0x30 + 12 * index
        record = lambda part,index: bytes(m.uc.mem_read(step(part,index),12))
        flag = built.layout['card'] + built.symbols['SQ_AT']
        m.write(flag,0xFFFFFFFF)
        m.call('script_seq_flush')
        self.assertEqual(told,[],'the card area is FF at power-on: no message without a write')
        m.uc.mem_write(step(3,17),bytes([0,77,9,0,5,6,7,8,1,2,3,4]))
        self.assertEqual(m.call('script_seq_set_step_glue',3,17,60,100),(0,0))
        self.assertEqual(record(3,17),bytes([1,77,100,1,61,0,0,0,1,2,3,4]),'on, velocity, trigger and the note; the gate and bytes 8 to 11 stay')
        self.assertEqual(m.call('script_seq_set_gate_glue',3,17,127),(0,0))
        self.assertEqual(record(3,17)[1],127)
        self.assertEqual(m.call('script_seq_set_step_glue',3,17,0xFFFFFFFF,100),(0,0))
        self.assertEqual(record(3,17),bytes([0,127,100,1,61,0,0,0,1,2,3,4]),'note -1 turns only the step off')
        m.call('script_seq_set_step_glue',3,17,0,90)
        self.assertEqual(m.call('script_seq_set_step_glue',3,17,64,0),(0,0))
        self.assertEqual(record(3,17)[:5],bytes([0,127,90,1,1]),'velocity 0 turns it off as well')
        self.assertEqual(m.call('script_seq_set_step_glue',15,63,127,1),(0,0))
        self.assertEqual(record(15,63)[:5],bytes([1,0,1,1,128]))
        for part in (2,4):
            for index in range(64): m.uc.mem_write(step(part,index),bytes([1,50,60,1,61,0,0,0]))
        m.write(0xC06B2108 + 0x344,2)
        m.call('script_seq_clear_part_glue',2)
        self.assertTrue(all(record(2,index)[:8] == bytes([0,50,60,1,61,0,0,0]) for index in range(64)),'clearPart turns every step off and leaves the rest')
        self.assertTrue(all(record(4,index)[0] == 1 for index in range(64)),'the next part stays')
        self.assertEqual(m.call('script_seq_set_step_glue',16,0,60,100),(0,error))
        self.assertEqual(m.call('script_seq_set_gate_glue',0,64,10),(0,error))
        self.assertEqual(m.call('script_seq_clear_part_glue',16),(0,error))
        m.write(m.input+0x202C,5)
        m.call('script_seq_flush')
        self.assertEqual(told,[],'another screen: the message waits')
        m.write(m.input+0x202C,1)
        m.call('script_seq_flush')
        m.call('script_seq_flush')
        self.assertEqual(told,[(0xC06B2108 + 4,(0x0B | 2 << 8,0))],'one message: the section that is shown, to the model\'s observers')

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
