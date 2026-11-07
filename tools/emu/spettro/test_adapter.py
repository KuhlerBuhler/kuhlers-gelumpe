"""Real ARM adapter with modelled native CommandTask and allocator boundaries."""
import unittest
from emulator import *
from tools.patch.spettro import source, CONTEXT_SIZE
SIZE = CONTEXT_SIZE
from unicorn.arm_const import UC_ARM_REG_R4

COMMAND, ALLOC = 0xC002D844, 0xC0028DCC

class AdapterMachine(ScopeMachine):
    def __init__(self):
        super().__init__()
        self.code=assemble(source(),origin=ORIGIN)
        for at,data in self.code.sections:self.uc.mem_write(at,data)
        self.control=self.code.symbols['scope_control']
        self.allocations=0
        self.oom=False
        self.commands=0
        self.uc.hook_add(UC_HOOK_CODE,self._native)

    def _native(self,uc,at,size,data):
        if at==ALLOC:
            assert uc.reg_read(UC_ARM_REG_R0)==SIZE
            self.allocations+=1
            uc.reg_write(UC_ARM_REG_R0,0 if self.oom else CTX)
        elif at==COMMAND:
            self.commands+=1
            for i in (0,1,2,3,12):uc.reg_write(UC_ARM_REG_R0+i,0x800+i)
            uc.reg_write(UC_ARM_REG_CPSR,0xA0000013)
        else:return
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))

    def request(self,enable=1,part=0,stereo=0,channel=0,shift=11,freeze=0):
        for i,x in enumerate((enable,part,stereo,channel,shift,freeze)):self.word(self.control+4*i,x)

    def run_hook(self):return self.call('scope_command_hook')

class AdapterTests(unittest.TestCase):
    def test_disabled_does_not_allocate_or_access_dsp_and_original_call_runs(self):
        m=AdapterMachine();m.run_hook()
        self.assertEqual((m.allocations,m.commands,len(m.calls)),(0,1,0))

    def test_lazy_context_is_zeroed_and_retained_on_close_and_reopen(self):
        m=AdapterMachine();m.uc.mem_write(CTX,bytes([0xBA])*SIZE)
        m.request(part=5);m.run_hook()
        self.assertEqual(m.word(m.control+24),CTX)
        self.assertEqual(m.word(CTX+56),0)
        self.assertIn(('begin',6),m.calls)
        m.tick(1040);m.request(0);m.run_hook()
        self.assertIn(('end',),m.calls)
        m.tick(1080);m.request(part=1);m.run_hook()
        self.assertEqual(m.allocations,1)
        self.assertIn(('begin',2),m.calls)

    def test_out_of_memory_is_latched_until_disabled_then_retry(self):
        m=AdapterMachine();m.oom=True;m.request();m.run_hook();m.run_hook()
        self.assertEqual(m.allocations,1)
        self.assertEqual(m.word(m.control+28),7)
        self.assertEqual(m.calls,[])
        m.request(0);m.run_hook();self.assertEqual(m.word(m.control+24),0)
        m.oom=False;m.request();m.run_hook();self.assertEqual(m.allocations,2)

    def test_native_return_registers_flags_and_stack_survive_scope_service(self):
        m=AdapterMachine();m.request()
        for i in range(4,12):m.uc.reg_write(UC_ARM_REG_R0+i,0x700+i)
        m.run_hook()
        for i in (0,1,2,3,12):self.assertEqual(m.uc.reg_read(UC_ARM_REG_R0+i),0x800+i)
        for i in range(4,12):self.assertEqual(m.uc.reg_read(UC_ARM_REG_R0+i),0x700+i)
        self.assertEqual(m.uc.reg_read(UC_ARM_REG_CPSR)&0xF00000FF,0xA0000013)

    def test_expired_ui_lease_closes_owned_capture(self):
        m=AdapterMachine();m.request();m.run_hook()
        self.assertIn(('begin',1),m.calls)
        m.word(m.control+32,1000);m.word(m.control+36,1)
        m.tick(1200);m.run_hook()
        self.assertEqual(m.word(m.control),0)
        self.assertIn(('end',),m.calls)

    def test_ui_without_context_or_after_oom_does_not_write_destination(self):
        for pointer in (0,0xFFFFFFFF):
            m=AdapterMachine();m.word(m.control+24,pointer)
            m.uc.mem_write(FB,b'\xA5'*1024)
            self.assertEqual(m.call('scope_adapter_copy',FB),OFF)
            self.assertEqual(bytes(m.uc.mem_read(FB,1024)),b'\xA5'*1024)

if __name__=='__main__':unittest.main()
