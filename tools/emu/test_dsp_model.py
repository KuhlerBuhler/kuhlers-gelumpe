# SPDX-License-Identifier: GPL-2.0-only
"""The DSP model's decoding of host-port transfers (dsp_model.py), with a stand-in machine: no firmware, no Unicorn."""

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsp_model import FIFO, PEAK, DspModel, MAILBOX, slot  # noqa: E402
from machine import DSP_CTRL, DSP_DATA, DSP_SYNC  # noqa: E402


class Port:
    """What the CPU does on the host port: 7 control words, then the data words."""

    def __init__(self, build="sampler"):
        self.machine = SimpleNamespace(profile=SimpleNamespace(build=build), time_ns=0, written=[])
        self.machine.write = lambda a, v: self.machine.written.append((a, v)) or True
        self.dsp = DspModel.attach(self.machine)

    def send(self, words, address=MAILBOX, cmd=0xAB, block=16):
        words = list(words) + [0xBEEF] * (block - len(words))
        for w in (cmd, address & 0xFFFF, address >> 16, len(words), 2, 0, 0):
            self.machine.write(DSP_CTRL, w)
        for w in words:
            self.machine.write(DSP_DATA, w)


class DspModelTest(unittest.TestCase):
    def test_a_parameter_message_sets_its_value(self):
        port = Port()
        port.send([0x106, 0, 0, 0x2E5, 0x114A])
        self.assertEqual(port.dsp.params, {0x2E5: 0x114A})

    def test_part_switch_on_and_off(self):
        port = Port()
        self.assertIsNone(port.dsp.part_on(3))
        port.send([0x106, 0, 0, 0x2C2 + 0x6D * 3, 1])
        mark = port.dsp.mark()
        self.assertTrue(port.dsp.part_on(3))
        port.send([0x106, 0, 0, 0x2C2 + 0x6D * 3, 0])
        self.assertFalse(port.dsp.part_on(3))
        self.assertEqual(port.dsp.parts_switched_off(mark), [3])
        self.assertEqual(port.dsp.parts_switched_off(port.dsp.mark()), [])

    def test_a_stereo_pair_in_one_message(self):
        port = Port()
        port.send([0x106, 0, 1, 0x2C2 + 0x6D * 4, 0, 0x2C2 + 0x6D * 5, 0])
        self.assertEqual(port.dsp.parts_switched_off(), [4, 5])

    def test_the_synth_has_its_own_part_switch(self):
        port = Port("synth")
        port.send([0x106, 0, 0, 0x2A8 + 0x6D, 0])
        self.assertFalse(port.dsp.part_on(1))
        port.send([0x106, 0, 0, 0x2C2, 0])
        self.assertIsNone(port.dsp.part_on(0))

    def test_reads_and_note_commands_set_no_parameter(self):
        port = Port()
        port.send([0x106, 0x35, 0x2CA, 0x461C])
        port.send([0x106, 0, 0, 0x2C2, 0], cmd=0xA9)
        self.assertEqual(port.dsp.params, {})
        self.assertEqual(port.dsp.messages, 1)
        self.assertEqual(port.dsp.commands[0x35], 1)

    def test_parameters_land_at_their_dsp_address(self):
        port = Port()
        port.send([0x106, 0, 0, 0x2C2, 1])
        port.send([0x106, 1, 0, 0x4C3B, 0x1234, 0x5678])
        port.send([0x106, 2, 1, 0x325, 0x7FFF, 0x10])
        port.send([0x106, 0x31, 1, 0x4C3D, 0, 5, 0, 6])
        self.assertEqual(slot(0x2C2), 0xFF800B08)
        self.assertEqual(slot(0x4C3D), PEAK)
        self.assertEqual(port.dsp.word(0xFF800B08), 1 << 16)
        self.assertEqual(port.dsp.word(slot(0x4C3B)), 0x12345678)
        self.assertEqual(port.dsp.word(slot(0x326)), 0x10 << 16)
        self.assertEqual(port.dsp.word(PEAK + 4), 6)

    def test_a_write_elsewhere_is_kept_as_written(self):
        port = Port()
        port.send([0xAAAA, 0xBBBB], address=0xFF904000, block=2)
        self.assertEqual(port.dsp.word(0xFF904000), 0xBBBBAAAA)
        self.assertEqual(port.dsp.messages, 0)

    def test_the_fifo_carries_the_tempo(self):
        port = Port()
        words = [0xF0203CBE, 0xF0603CBE, 0xFF800000, 0x00203CBE]
        port.send([h for w in words for h in (w & 0xFFFF, w >> 16)], address=FIFO[0], block=64)
        self.assertEqual(port.dsp.tempo, {0: 15550, 1: 15550})
        self.assertEqual([e[1:] for e in port.dsp.fifo], [(0, 0x20, 15550), (1, 0x20, 15550)])

    def test_the_output_peak_is_the_larger_of_level_and_written(self):
        port = Port()
        self.assertEqual(port.dsp.peak(), (0, 0))
        port.dsp.output(0.5, 1.5)
        self.assertEqual(port.dsp.peak(), (0x40000000, 0x7FFFFFFF))
        port.send([0x106, 0x31, 1, 0x4C3D, 0x7000, 0, 0, 0])
        self.assertEqual(port.dsp.peak(), (0x70000000, 0x7FFFFFFF))
        self.assertTrue(port.dsp.answers(PEAK + 6) and not port.dsp.answers(PEAK + 8))

    def test_the_sync_word_and_the_machine_still_get_every_write(self):
        port = Port()
        port.machine.write(DSP_CTRL, DSP_SYNC)
        port.send([0x106, 0, 0, 0x2C2, 1])
        self.assertTrue(port.dsp.part_on(0))
        self.assertEqual(len(port.machine.written), 1 + 7 + 16)

    def test_attach_keeps_one_model(self):
        port = Port()
        self.assertIs(DspModel.attach(port.machine), port.dsp)


if __name__ == "__main__":
    unittest.main()
