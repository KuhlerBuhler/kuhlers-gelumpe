"""Frequency and level checks independent of the prospective ARM implementation."""
import math
import unittest
from spectrum_reference import *


class SpectrumTests(unittest.TestCase):
    def tone(self,amplitude=32768,n=4096,bin_index=80):
        return amplitude*np.sin(2*np.pi*bin_index*np.arange(n)/n)

    def test_known_frequency_and_full_scale_sine(self):
        f,p=spectrum(self.tone())
        self.assertEqual(f[np.argmax(p)],937.5)
        self.assertLess(abs(10*np.log10(p[80])),.001)

    def test_half_amplitude_is_six_db_lower(self):
        f,p=spectrum(self.tone(amplitude=16384))
        self.assertAlmostEqual(10*np.log10(p[80]),-6.020599913,places=4)

    def test_opposite_stereo_phases_do_not_cancel(self):
        x=self.tone();f,p=spectrum(np.column_stack((x,-x)))
        self.assertLess(abs(10*np.log10(p[80])),.001)

    def test_silence_and_dc_have_no_fake_frequency_peak(self):
        for x in (np.zeros(4096),np.ones(4096)*10000):
            f,p=spectrum(x);centers,db=logarithmic_columns(f,p)
            self.assertTrue(np.all(db[np.isfinite(db)]==-90))

    def test_short_window_does_not_invent_low_frequency_resolution(self):
        f,p=spectrum(self.tone(n=1024));centers,db=logarithmic_columns(f,p)
        self.assertTrue(np.isnan(db[centers<46.875]).all())
        self.assertTrue(np.isfinite(db[centers>=46.875]).all())

    def test_log_axis_spans_three_decades(self):
        f,p=spectrum(self.tone());x,y=logarithmic_columns(f,p)
        self.assertAlmostEqual(x[1]/x[0],1000**(1/128))
        self.assertEqual(len(y),128)


if __name__=='__main__':unittest.main()
