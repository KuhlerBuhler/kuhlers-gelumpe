# SPDX-License-Identifier: GPL-2.0-only
"""The DSP model's decoding of host-port transfers (dsp_model.py), with a stand-in machine: no firmware, no Unicorn."""

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsp_model import DspModel, MAILBOX  # noqa: E402
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

    def test_other_commands_reads_and_addresses_set_nothing(self):
        port = Port()
        port.send([0x106, 0x31, 0, 0x2C2, 0])
        port.send([0x106, 0, 0, 0x2C2, 0], address=0xFF900098)
        port.send([0x106, 0, 0, 0x2C2, 0], cmd=0xA9)
        self.assertEqual(port.dsp.params, {})
        self.assertEqual(port.dsp.messages, 1)

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
