"""Actual timing-probe ARM with simulated native allocator, no device access."""
import unittest
import struct
from fft_benchmark import build, SIZE
from emulator import ORIGIN
from spectrum_reference import np
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_PC

HEAP, STACK, STOP = 0xC1200100, 0xC1221000, 0xC1230000
ALLOC, FREE, TICKS = 0xC0028DCC, 0xC0028DD4, 0xC06A292C


class BenchMachine:
    def __init__(self, oom=False):
        self.code=build()
        self.uc=Uc(UC_ARCH_ARM,UC_MODE_ARM)
        for addr,size in ((0xC0000000,0x800000),(ORIGIN,0x10000),(0xC1200000,0x40000)):
            self.uc.mem_map(addr,size)
        self.uc.mem_write(ORIGIN,self.code.bytes)
        self.uc.mem_write(HEAP-16,b'A'*16+bytes(SIZE)+b'Z'*16)
        self.events=[];self.writes=[];self.oom=oom
        self.uc.hook_add(UC_HOOK_CODE,self.native,begin=ALLOC,end=ALLOC)
        self.uc.hook_add(UC_HOOK_CODE,self.native,begin=FREE,end=FREE)
        self.uc.hook_add(UC_HOOK_MEM_WRITE,self.write)

    def native(self,uc,addr,size,data):
        arg=uc.reg_read(UC_ARM_REG_R0)
        self.events.append((addr,arg))
        if addr==ALLOC:
            assert arg==SIZE
            uc.reg_write(UC_ARM_REG_R0,0 if self.oom else HEAP)
        else:
            assert arg==HEAP
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))

    def write(self,uc,access,addr,size,value,data):
        self.writes.append((addr,size))

    def call(self,name):
        self.uc.reg_write(UC_ARM_REG_SP,STACK)
        self.uc.reg_write(UC_ARM_REG_LR,STOP)
        self.uc.emu_start(self.code.symbols[name],STOP,count=2_000_000)
        assert self.uc.reg_read(UC_ARM_REG_PC)==STOP
        assert self.uc.reg_read(UC_ARM_REG_SP)==STACK
        return self.uc.reg_read(UC_ARM_REG_R0)


class FFTBenchmarkTests(unittest.TestCase):
    def test_coefficients_impulse_memory_and_cleanup(self):
        m=BenchMachine()
        self.assertEqual(m.call('fft_bench'),HEAP)
        self.assertEqual(struct.unpack('<I',bytes(m.uc.mem_read(HEAP,4)))[0],0x46465442)
        self.assertEqual(struct.unpack('<I',bytes(m.uc.mem_read(HEAP+16,4)))[0],1)
        data=np.frombuffer(bytes(m.uc.mem_read(HEAP+64,32768)),dtype='<i4').reshape(-1,2)
        np.testing.assert_array_equal(data[:,0],np.full(4096,4))
        np.testing.assert_array_equal(data[:,1],np.zeros(4096))
        coefficients=np.frombuffer(bytes(m.uc.mem_read(HEAP+32832,16384)),dtype='<i4').reshape(-1,2)
        angle=-2*np.pi*np.arange(2048)/4096
        reference=np.rint(32768*np.column_stack((np.cos(angle),np.sin(angle))))
        self.assertLessEqual(np.max(np.abs(coefficients-reference)),1)
        self.assertEqual(m.call('fft_bench'),0)  # outstanding allocation cannot be lost
        self.assertEqual(m.call('fft_bench_free'),0)
        self.assertEqual(m.call('fft_bench_free'),0)
        self.assertEqual(m.events,[(ALLOC,SIZE),(FREE,HEAP)])
        self.assertEqual(bytes(m.uc.mem_read(HEAP-16,16)),b'A'*16)
        self.assertEqual(bytes(m.uc.mem_read(HEAP+SIZE,16)),b'Z'*16)
        ptr=m.code.symbols['fft_bench_ptr']
        for addr,size in m.writes:
            self.assertTrue(HEAP<=addr and addr+size<=HEAP+SIZE
                            or STACK-4096<=addr and addr+size<=STACK
                            or addr==ptr and size==4)

    def test_allocation_failure_returns_without_processing(self):
        m=BenchMachine(oom=True)
        self.assertEqual(m.call('fft_bench'),0)
        self.assertEqual(m.call('fft_bench_free'),0)
        self.assertEqual(m.events,[(ALLOC,SIZE)])


if __name__=='__main__':unittest.main()
