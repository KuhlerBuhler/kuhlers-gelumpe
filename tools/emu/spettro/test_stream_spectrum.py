"""Actual ARM reader -> offline FFT, with generated known audio.

This verifies sample continuity and spectral interpretation across ring wraps.
The FFT runs on the PC; it measures neither ARM FFT speed nor physical hardware.
"""
import struct
import unittest
from test_stream_capture import StreamMachine
from emulator import CTX, RING
from measurement_reference import CAPACITY
from spectrum_reference import np, spectrum


class StreamSpectrumTests(unittest.TestCase):
    def acquire(self, left_bin=5, right_bin=80, amplitude=16000):
        m = StreamMachine()
        position, tick = 1200, 0
        chunks = []
        start = position - 256
        for interval in (0, 40, 43, 38, 47):
            position += interval * 48
            tick += interval
            m.tick(tick)
            m.state[2] = RING + position % CAPACITY * 4
            for frame in range(max(0, position-CAPACITY), position):
                low = round(amplitude*np.sin(2*np.pi*left_bin*frame/4096))
                high = round(amplitude*np.sin(2*np.pi*right_bin*frame/4096))
                at = frame % CAPACITY * 4
                m.ring[at:at+4] = struct.pack('<hh', low, high)
            status = m.call('stream_poll', CTX)
            self.assertEqual(status, 1 if not interval else 0)
            size = m.word(CTX+12)
            chunks.append(bytes(m.uc.mem_read(CTX+128, size)))
        raw = b''.join(chunks)
        samples = np.frombuffer(raw, dtype='<i2').reshape(-1, 2)
        expected = np.array([
            [round(amplitude*np.sin(2*np.pi*b*frame/4096))
             for b in (left_bin, right_bin)]
            for frame in range(start, position-256)
        ], dtype=np.int16)
        np.testing.assert_array_equal(samples, expected)
        return samples[-4096:]

    def test_bass_and_high_stereo_peaks_after_ring_wrap(self):
        pcm = self.acquire()
        for component, expected_bin in ((0, 5), (1, 80)):
            f, p = spectrum(pcm[:, component])
            self.assertEqual(f[np.argmax(p)], expected_bin*48000/4096)
            level = 10*np.log10(p[expected_bin])
            self.assertAlmostEqual(level, 20*np.log10(16000/32768), places=3)

    def test_lower_input_level_remains_lower_without_auto_normalization(self):
        loud = self.acquire(amplitude=16000)
        quiet = self.acquire(amplitude=4000)
        _, a = spectrum(loud)
        _, b = spectrum(quiet)
        for peak in (5, 80):
            self.assertAlmostEqual(10*np.log10(b[peak]/a[peak]),
                                   20*np.log10(.25), places=2)


if __name__ == '__main__':
    unittest.main()
