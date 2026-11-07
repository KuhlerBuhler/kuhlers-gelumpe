"""Native preprocessing + FFT + power against independent analytic signals."""
from pathlib import Path
import unittest
from emulator import SOURCE, ORIGIN, assemble
from test_fft_benchmark import BenchMachine, HEAP
from spectrum_reference import np
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3

INPUT,POWER=0xC1240100,0xC1250100


class FrontendMachine(BenchMachine):
    def __init__(self):
        super().__init__()
        old=self.code.bytes
        source='\n'.join(((Path(__file__).parent/n) if n == 'fft_benchmark.s' else (SOURCE/n)).read_text()
                         for n in ('fft_benchmark.s','fft_fixed.s','fft_frontend.s'))
        self.code=assemble(source,origin=ORIGIN)
        assert self.code.bytes[:len(old)]==old
        self.uc.mem_write(ORIGIN,self.code.bytes)
        self.uc.mem_map(0xC1240000,0x20000)
        self.call('fft_bench')  # initializes coefficients in allocated storage
    def prepare(self,pcm,component=0):
        self.uc.mem_write(INPUT-16,b'A'*16+np.asarray(pcm,dtype='<i2').tobytes()+b'Z'*16)
        for reg,value in ((UC_ARM_REG_R0,INPUT),(UC_ARM_REG_R1,HEAP+64),
                          (UC_ARM_REG_R2,HEAP+32832),(UC_ARM_REG_R3,component*2)):
            self.uc.reg_write(reg,value)
        self.call('fft_prepare')
        raw=bytes(self.uc.mem_read(HEAP+64,32768))
        self.assert_input_guards()
        return np.frombuffer(raw,dtype='<i4').reshape(-1,2).copy()
    def assert_input_guards(self):
        assert bytes(self.uc.mem_read(INPUT-16,16))==b'A'*16
        assert bytes(self.uc.mem_read(INPUT+16384,16))==b'Z'*16
    def power(self,pcm,component=0,mode=0):
        self.prepare(pcm,component)
        self.uc.reg_write(UC_ARM_REG_R0,HEAP+64)
        self.uc.reg_write(UC_ARM_REG_R1,HEAP+32832)
        self.call('fft4096')
        self.uc.reg_write(UC_ARM_REG_R0,HEAP+64)
        self.uc.reg_write(UC_ARM_REG_R1,POWER)
        self.uc.reg_write(UC_ARM_REG_R2,mode)
        self.call('fft_power')
        return np.frombuffer(bytes(self.uc.mem_read(POWER,2049*4)),dtype='<u4').copy()


class FFTFrontendTests(unittest.TestCase):
    def test_window_mean_and_extreme_inputs(self):
        m=FrontendMachine()
        rng=np.random.default_rng(40)
        left=rng.integers(-32768,32768,4096)
        right=np.full(4096,-32768)
        pcm=np.column_stack((left,right))
        for component,signal in enumerate((left,right)):
            actual=m.prepare(pcm,component)
            window=(1-np.cos(2*np.pi*np.arange(4096)/4096))/2
            expected=(signal-(int(signal.sum())>>12))*window*64
            self.assertLess(np.max(np.abs(actual[:,0]-expected)),128)
            self.assertTrue(np.all(actual[:,1]==0))
            self.assertLessEqual(np.max(np.abs(actual[:,0])),4194304)

    def test_native_peak_and_half_scale_level_with_dc_offset(self):
        m=FrontendMachine();t=np.arange(4096)
        signal=np.rint(16384*np.sin(2*np.pi*80*t/4096)+10000)
        pcm=np.column_stack((signal,signal)).astype(np.int16)
        power=m.power(pcm)
        self.assertEqual(np.argmax(power),80)
        self.assertAlmostEqual(10*np.log10(power[80]/2**30),20*np.log10(.5),delta=.05)

    def test_stereo_opposite_phase_does_not_cancel(self):
        m=FrontendMachine();t=np.arange(4096)
        signal=np.rint(24000*np.sin(2*np.pi*5*t/4096)).astype(np.int16)
        pcm=np.column_stack((signal,-signal))
        mono=m.power(pcm)
        m.power(pcm,0,1)
        combined=m.power(pcm,1,2)
        self.assertEqual(np.argmax(combined),5)
        self.assertLess(abs(10*np.log10(combined[5]/mono[5])),.05)

    def test_constant_input_produces_zero_spectrum(self):
        m=FrontendMachine()
        pcm=np.full((4096,2),15000,dtype=np.int16)
        self.assertTrue(np.all(m.power(pcm)==0))

    def test_quiet_tone_retains_level_without_false_large_peaks(self):
        m=FrontendMachine();t=np.arange(4096)
        signal=np.rint(64*np.sin(2*np.pi*80*t/4096)).astype(np.int16)
        p=m.power(np.column_stack((signal,signal)))
        self.assertEqual(np.argmax(p),80)
        self.assertAlmostEqual(10*np.log10(p[80]/2**30),20*np.log10(64/32768),delta=.15)
        other=np.concatenate((p[2:79],p[82:]))
        self.assertLess(np.max(other),p[80]/1000)


if __name__=='__main__':unittest.main()
