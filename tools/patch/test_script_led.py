"""Native LED requests and atomic UART FIFO transport, without firmware bytes."""
import pathlib
import struct
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import BareMachine, contract_data, blob, UNICORN_AVAILABLE
from tools.patch import test_script_hooks as hooks_tests
if UNICORN_AVAILABLE:
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.arm_const import *

@unittest.skipUnless(UNICORN_AVAILABLE,'Unicorn is required for native LED tests')
class NativeLedTests(unittest.TestCase):
    def machine(self):
        m,built=hooks_tests.HookTests().machine()
        for at in [0xC0025000,0xC06A0000,0xC06B0000,0x01C42000]:m.uc.mem_map(at,0x1000 if at!=0xC06A0000 else 0x10000)
        m.uc.mem_write(0xC002548C,struct.pack('<I',0xE12FFF1E))
        m.write(0xC033E6FC,0xC06B0000)
        m.write(0xC033E644,0x01C42000)
        m.write(0xC06A24C0,1)
        q=0xC033E648
        m.write(q+4,0xC06AE578);m.write(q+8,5)
        for off,value in [(14,1),(16,0),(18,0),(20,0),(22,1024),(24,0x13ff)]:self.half(m,q+off,value)
        m.write(q+32,0xC002548C)
        table=built.symbols['script_api_table']+built.symbols['API_KORG_LED']*built.symbols['SCRIPT_API_ENTRY_SIZE']
        m.write(table+12,built.symbols['script_led_glue'])
        m.uc.reg_write(UC_ARM_REG_CPSR,0x60000013)
        return m,built

    def half(self,m,at,value):m.uc.mem_write(at,struct.pack('<H',value))
    def count(self,m):return struct.unpack('<H',m.uc.mem_read(0xC033E65C,2))[0]
    def request(self,m,index,value):return m.call('script_led_request',m.runtime,index,value)
    def flush(self,m):return m.call('script_led_flush',m.runtime)[0]

    def test_generated_api_one_enqueues_ready_packet(self):
        m,built=self.machine()
        error,entry=m.load(blob([0,1,4,1,77,33,1,2,9,0],stack=2,handlers=[(2,0,1)]))
        self.assertEqual(error,0);self.assertEqual(m.run(entry,0),0)
        m.call('script_frame_run',m.runtime)
        self.assertEqual(self.count(m),5)
        self.assertEqual(bytes(m.uc.mem_read(0xC06AE578,5)),bytes([0,4,77,0,0]))

    def test_first_zero_latest_request_and_frame_dedup(self):
        m,_=self.machine()
        self.assertEqual(self.request(m,0,0),(0,0))
        self.assertEqual(self.flush(m),1)
        self.request(m,0,0);self.assertEqual(self.flush(m),0)
        m.call('script_led_begin_frame',m.runtime)
        self.request(m,0,255);self.request(m,0,3);self.request(m,0,0)
        self.assertEqual(self.flush(m),1)
        self.assertEqual(bytes(m.uc.mem_read(0xC06AE578,10)),bytes(10))
        self.request(m,0,1);self.request(m,0,0);self.assertEqual(self.flush(m),0)

    def test_frame_cap_fairness_and_pending(self):
        m,_=self.machine()
        for i in range(88):self.request(m,i,i+1)
        self.assertEqual(self.flush(m),16)
        self.assertEqual(self.count(m),80)
        self.assertEqual(self.flush(m),0)
        for _ in range(5):
            m.call('script_led_begin_frame',m.runtime);self.flush(m)
        packets=bytes(m.uc.mem_read(0xC06AE578,440))
        self.assertEqual(packets,b''.join(bytes([0,i,i+1,0,0]) for i in range(88)))
        self.assertEqual(self.flush(m),0)

    def test_atomic_reserve_wrap_semaphore_and_irq_guard(self):
        for free,want in [(260,0),(261,1)]:
            m,_=self.machine();self.half(m,0xC033E65C,1024-free)
            self.half(m,0xC033E658,1023)
            self.half(m,0xC033E65A,(1023-(1024-free))&1023)
            self.assertEqual(m.call('script_led_try_send',87,255)[0],want)
            self.assertEqual(self.count(m),1024-free+want*5)
            if want:
                self.assertEqual(bytes(m.uc.mem_read(0xC06AE578+1023,1)),b'\0')
                self.assertEqual(bytes(m.uc.mem_read(0xC06AE578,4)),bytes([87,255,0,0]))
            self.assertEqual(m.read(0xC06A24C0),1)
            self.assertEqual(m.uc.reg_read(UC_ARM_REG_CPSR),0x60000013)
        for cpsr,sem in [(0x60000013,0),(0x60000093,1),(0x60000013,2)]:
            m,_=self.machine();m.write(0xC06A24C0,sem);m.uc.reg_write(UC_ARM_REG_CPSR,cpsr)
            self.assertEqual(m.call('script_led_try_send',1,2)[0],0)
            self.assertEqual(self.count(m),0);self.assertEqual(m.read(0xC06A24C0),sem)
            self.assertEqual(m.uc.reg_read(UC_ARM_REG_CPSR),cpsr)

    def test_invalid_hardware_rejected_and_pending_retained(self):
        defects=[(0xC033E6FC,0,4),(0xC033E6FC,0xffffffff,4),(0xC06B0004,1,1),
            (0xC033E64C,0,4),(0xC033E650,6,4),(0xC033E656,2,2),
            (0xC033E658,1024,2),(0xC033E65A,1024,2),(0xC033E65C,1025,2),
            (0xC033E65E,512,2),(0xC033E660,1024,2),(0xC033E668,0,4),
            (0xC033E644,0,4),(0xC033E644,0xC06B0080,4)]
        for at,value,width in defects:
            with self.subTest(at=hex(at),value=value):
                m,_=self.machine();m.uc.mem_write(at,value.to_bytes(width,'little'))
                self.request(m,7,44);self.assertEqual(self.flush(m),0)
                pending=m.runtime+m.symbols['RT_LED']+m.symbols['SCRIPT_LED_PENDING']
                self.assertEqual(bytes(m.uc.mem_read(pending+7,1)),b'\1')

    def test_bounds_callee_registers_and_short_irq_window(self):
        m,_=self.machine()
        for index,value in [(-1,0),(88,0),(0,-1),(0,256)]:
            self.assertEqual(self.request(m,index&0xffffffff,value&0xffffffff)[1],contract_data()['error']['API_ARG'])
        regs=[0x12340000+i for i in range(8)]
        for i,v in enumerate(regs):m.uc.reg_write(UC_ARM_REG_R4+i,v)
        trace=[]
        def inspect(uc,at,size,_):
            if uc.reg_read(UC_ARM_REG_CPSR)&0x80:trace.append(at)
        m.uc.hook_add(UC_HOOK_CODE,inspect)
        self.assertEqual(m.call('script_led_try_send',1,2)[0],1)
        self.assertEqual([m.uc.reg_read(UC_ARM_REG_R4+i) for i in range(8)],regs)
        self.assertLessEqual(len(trace),150)
        self.assertGreater(len(trace),25)
        self.assertEqual(m.uc.reg_read(UC_ARM_REG_SP),m.stack+0xF0000)

    def test_fifo_consistency_and_kick_only_on_empty(self):
        m,_=self.machine()
        self.half(m,0xC033E65C,1)
        self.assertEqual(m.call('script_led_try_send',1,2)[0],0)
        self.half(m,0xC033E65C,0)
        kicks=[];writes=[]
        m.uc.hook_add(UC_HOOK_CODE,lambda uc,at,size,_:kicks.append(at),
            begin=0xC002548C,end=0xC002548C)
        def write(uc,access,at,size,value,_):
            if 0xC06AE578<=at<0xC06AE978 or 0xC033E658<=at<0xC033E65E:
                writes.append((at,uc.reg_read(UC_ARM_REG_CPSR)&0x80))
        m.uc.hook_add(UC_HOOK_MEM_WRITE,write)
        self.assertEqual(m.call('script_led_try_send',1,2)[0],1)
        self.assertEqual(m.call('script_led_try_send',3,4)[0],1)
        self.assertEqual(kicks,[0xC002548C])
        self.assertEqual(len(writes),18)
        self.assertTrue(all(mask==0x80 for _,mask in writes))

    def test_time_fault_retains_led_request_until_following_frame(self):
        m,_=self.machine()
        error,entry=m.load(blob([0,1,4,1,77,33,1,2,9,28,9,0],stack=2,handlers=[(2,0,1)]))
        self.assertEqual(error,0);self.assertEqual(m.run(entry,0),0)
        def advance(uc,at,size,_):m.write(m.timer,m.read(m.timer)+5000)
        hook=m.uc.hook_add(UC_HOOK_CODE,advance,begin=m.symbols['run_next'],end=m.symbols['run_next'])
        m.call('script_frame_run',m.runtime)
        self.assertEqual(m.read(entry+16),contract_data()['error']['TIME'])
        self.assertEqual(self.count(m),0)
        m.uc.hook_del(hook)
        m.call('script_frame_run',m.runtime)
        self.assertEqual(self.count(m),5)
        self.assertEqual(bytes(m.uc.mem_read(0xC06AE578,5)),bytes([0,4,77,0,0]))

    def test_shared_deadline_checked_before_each_packet_wrap_safe(self):
        for start,ticks,want in [(0,750000,1),(0,750001,0),(0xfffffff0,750001,0)]:
            m,_=self.machine();self.request(m,1,2)
            m.write(m.runtime+116,1);m.write(m.runtime+112,start);m.write(m.timer,start+ticks)
            self.assertEqual(self.flush(m),want)
        m,_=self.machine()
        for i in range(10):self.request(m,i,2)
        m.write(m.runtime+116,1)
        def advance(uc,at,size,_):m.write(m.timer,m.read(m.timer)+400000)
        m.uc.hook_add(UC_HOOK_CODE,advance,begin=m.symbols['script_led_try_send'],end=m.symbols['script_led_try_send'])
        self.assertEqual(self.flush(m),2)
        self.assertEqual(self.count(m),10)
        m.write(m.runtime+112,m.read(m.timer));self.assertEqual(self.flush(m),2)

if __name__=='__main__':unittest.main()
