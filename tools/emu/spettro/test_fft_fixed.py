"""Execute the isolated native FFT; compare against NumPy's independent FFT.
No device access. Emulator execution time does not predict hardware timing.
"""
import struct
import unittest
from emulator import assemble, ORIGIN, SOURCE
from spectrum_reference import np
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R4, UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_PC

DATA, TWIDDLE, STACK, STOP = 0xC1200100, 0xC1210100, 0xC1221000, 0xC1230000


def execute_fft(samples):
    samples = np.asarray(samples, dtype=np.int32)
    if samples.shape != (4096,) or np.any(samples < -4194304) or np.any(samples > 4194303):
        raise ValueError('Expected 4096 real signed16 samples in Q7')
    code = assemble((SOURCE/'fft_fixed.s').read_text(), origin=ORIGIN)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(ORIGIN, 0x10000)
    uc.mem_map(0xC1200000, 0x40000)
    uc.mem_write(ORIGIN, code.bytes)
    data = np.column_stack((samples, np.zeros(4096, dtype=np.int32))).astype('<i4').tobytes()
    angle = -2*np.pi*np.arange(2048)/4096
    twiddle = np.rint(32768*np.column_stack((np.cos(angle),np.sin(angle)))).astype('<i4').tobytes()
    uc.mem_write(DATA-16, b'A'*16+data+b'Z'*16)
    uc.mem_write(TWIDDLE-16, b'B'*16+twiddle+b'Y'*16)
    uc.reg_write(UC_ARM_REG_R0, DATA)
    uc.reg_write(UC_ARM_REG_R1, TWIDDLE)
    uc.reg_write(UC_ARM_REG_SP, STACK)
    uc.reg_write(UC_ARM_REG_LR, STOP)
    for i in range(8):
        uc.reg_write(UC_ARM_REG_R4+i,0x56780000+i)
    uc.emu_start(code.symbols['fft4096'], STOP, count=2_000_000)
    if uc.reg_read(UC_ARM_REG_PC)!=STOP:
        raise AssertionError('FFT did not finish inside instruction bound')
    if uc.reg_read(UC_ARM_REG_SP)!=STACK:
        raise AssertionError('FFT changed stack pointer')
    for i in range(8):
        if uc.reg_read(UC_ARM_REG_R4+i)!=0x56780000+i:
            raise AssertionError('FFT clobbered callee-saved register')
    if bytes(uc.mem_read(DATA-16,16))!=b'A'*16 or bytes(uc.mem_read(DATA+len(data),16))!=b'Z'*16:
        raise AssertionError('FFT overran data')
    if bytes(uc.mem_read(TWIDDLE-16,len(twiddle)+32))!=b'B'*16+twiddle+b'Y'*16:
        raise AssertionError('FFT modified coefficients or their guards')
    out=np.frombuffer(bytes(uc.mem_read(DATA,len(data))),dtype='<i4').reshape(-1,2)
    return out[:,0]+1j*out[:,1]


class NativeFFTTests(unittest.TestCase):
    def compare(self, samples, limit=16):
        actual=execute_fft(samples)
        expected=np.fft.fft(samples)/4096
        # Absolute full-scale units after /4096, not a relative noise-floor guarantee.
        self.assertLess(np.max(np.abs(actual-expected)),limit)
        return actual

    def test_silence_and_full_scale_dc_do_not_overflow(self):
        for value in (0,32767,-32768):
            actual=self.compare(np.full(4096,value,dtype=np.int32))
            self.assertEqual(actual[0],value)
            self.assertEqual(np.max(np.abs(actual[1:])),0)

    def test_low_and_high_tones_match_frequency_and_level(self):
        t=np.arange(4096)
        samples=np.rint(12000*np.sin(2*np.pi*5*t/4096)+8000*np.cos(2*np.pi*800*t/4096)).astype(np.int32)
        actual=self.compare(samples)
        self.assertEqual(np.argmax(np.abs(actual[:2049])),5)
        self.assertLess(abs(abs(actual[5])-6000),16)
        self.assertLess(abs(abs(actual[800])-4000),16)

    def test_windowed_random_and_rail_values(self):
        rng=np.random.default_rng(786)
        for samples in (rng.integers(-32768,32768,4096),
                        np.rint(rng.integers(-32768,32768,4096)*np.hanning(4096)),
                        np.where(np.arange(4096)%2,32767,-32768)):
            self.compare(np.asarray(samples,dtype=np.int32))

    def test_q7_retains_fractional_precision_without_product_overflow(self):
        t=np.arange(4096)
        signal=np.rint(30000*128*np.sin(2*np.pi*5*t/4096)).astype(np.int32)
        self.compare(signal,limit=32)  # <0.25 input PCM units with Q7
        self.compare(np.where(t%2,32767*128,-32768*128).astype(np.int32),limit=32)


if __name__=='__main__':
    unittest.main()
