"""Integrated ARM acquisition/FFT/bitmap with synthetic DSP, no device access."""
import struct
import unittest
from tools.patch.spettro import source, CONTEXT_SIZE
from spectrum_reference import np
from emulator import ScopeMachine, assemble, ORIGIN, CTX, STACK, STOP, RING, RING_BYTES
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_CPSR


class SpectrumMachine(ScopeMachine):
    def __init__(self):
        super().__init__()
        self.code=assemble(source(),origin=ORIGIN)
        self.uc.mem_write(ORIGIN,self.code.bytes)
        self.uc.mem_write(CTX-16,b'A'*16+bytes(CONTEXT_SIZE)+b'Z'*16)
    def call(self,symbol,*args):
        self.uc.reg_write(UC_ARM_REG_CPSR,0x13)
        for i,v in enumerate(args):self.uc.reg_write(UC_ARM_REG_R0+i,v&0xFFFFFFFF)
        self.uc.reg_write(UC_ARM_REG_SP,STACK)
        self.uc.reg_write(UC_ARM_REG_LR,STOP)
        self.uc.emu_start(self.code.symbols[symbol],STOP,count=4_000_000)
        assert self.uc.reg_read(UC_ARM_REG_PC)==STOP, symbol
        assert self.uc.reg_read(UC_ARM_REG_SP)==STACK
        return self.uc.reg_read(UC_ARM_REG_R0)
    def advance(self,position,tick,opposite=False):
        self.tick(tick)
        self.state[2]=RING+(position%4800)*4
        for frame in range(max(0,position-4800),position):
            v=round(16000*np.sin(2*np.pi*80*frame/4096))
            at=frame%4800*4
            self.ring[at:at+4]=struct.pack('<hh',v,-v if opposite else v)
        return self.service()
    def filled(self,stereo=False):
        self.request(stereo=int(stereo),channel=2 if stereo else 0)
        self.tick(1000);self.service()
        for i in range(1,4):self.advance(i*2400,1000+i*50,stereo)
        return np.frombuffer(bytes(self.uc.mem_read(CTX+94208,2049*4)),dtype='<u4').copy()
    def frame(self):
        ptr=self.word(CTX+56)
        return bytes(self.uc.mem_read(ptr,1024)) if ptr else None


class SpectrumWorkerTests(unittest.TestCase):
    def test_complete_pipeline_mono_freeze_gap_and_close(self):
        m=SpectrumMachine();powers=m.filled()
        self.assertEqual(m.word(CTX+28),0)
        self.assertEqual(np.argmax(powers),80)
        self.assertAlmostEqual(10*np.log10(powers[80]/2**30),20*np.log10(16000/32768),delta=.05)
        frame=m.frame();self.assertTrue(any(frame))
        m.word(CTX+60,1)
        m.advance(9600,1200)
        self.assertEqual(m.frame(),frame)
        m.word(CTX+108,1)  # zoom uses held powers, with matching new frequency axis
        m.advance(12000,1250)
        self.assertNotEqual(m.frame(),frame)
        m.advance(16800,1350)  # >80 ms gap must invalidate held old frame
        self.assertEqual(m.word(CTX+56),0)
        self.assertEqual(m.word(CTX+124),0)
        m.request(enabled=0);m.tick(1370);m.service()
        self.assertEqual(m.state[0],0)
        self.assertEqual(m.word(CTX+4),0)
        self.assertEqual(bytes(m.uc.mem_read(CTX-16,16)),b'A'*16)
        self.assertEqual(bytes(m.uc.mem_read(CTX+CONTEXT_SIZE,16)),b'Z'*16)

    def test_stereo_opposition_and_pad_change_clears_measurement(self):
        m=SpectrumMachine();powers=m.filled(stereo=True)
        self.assertEqual(np.argmax(powers),80)
        self.assertAlmostEqual(10*np.log10(powers[80]/2**30),20*np.log10(16000/32768),delta=.05)
        m.request(part=2,stereo=0,channel=0);m.tick(1170);m.service()
        self.assertEqual(m.word(CTX+56),0)
        self.assertEqual(m.word(CTX+124),0)
        self.assertIn(('begin',3),m.calls)

    def test_recording_takeover_does_not_end_other_capture(self):
        m=SpectrumMachine();m.request();m.tick(1000);m.service()
        m.state[10]=1;m.tick(1020);m.service()
        self.assertEqual(m.word(CTX+4),0)
        m.request(enabled=0);m.tick(1040);m.service()
        self.assertFalse(any(c[0]=='end' for c in m.calls))

    def test_render_constant_power_scale_and_graph_bounds(self):
        m=SpectrumMachine()
        p=CTX+94208;fb=CTX+4224
        m.uc.mem_write(p,struct.pack('<2049I',*([2**30]*2049)))
        m.call('spectrum_render',p,fb,11,0)
        frame=bytes(m.uc.mem_read(fb,1024))
        for x in range(128):
            ys=[y for y in range(64) if frame[y//8*128+x]&(1<<(y%8))]
            self.assertEqual(ys,[10])
        m.uc.mem_write(p,struct.pack('<2049I',*([2**18]*2049)))
        m.call('spectrum_render',p,fb,11,1)
        frame=bytes(m.uc.mem_read(fb,1024))
        for x in range(128):
            ys=[y for y in range(64) if frame[y//8*128+x]&(1<<(y%8))]
            self.assertEqual(ys,[33])

    def test_low_frequency_column_interpolates_instead_of_repeating_ceiling_bin(self):
        m=SpectrumMachine();p=CTX+94208;fb=CTX+4224
        powers=[0]*2049;powers[2]=2**30
        m.uc.mem_write(p,struct.pack('<2049I',*powers))
        m.call('spectrum_render',p,fb,11,0)
        frame=bytes(m.uc.mem_read(fb,1024))
        first=[y for y in range(64) if frame[y//8*128]&(1<<(y%8))]
        self.assertGreater(min(first),10)  # 20 Hz lies between bins, below bin-2 peak


if __name__=='__main__':unittest.main()
