"""Build-specific check dispatch, with synthetic images only."""
import struct
import unittest
from unittest.mock import patch

import sysex_cases
import synthaddr


class SynthChecks(unittest.TestCase):
    def test_sysex_hooks_are_detected_at_the_address_of_each_build(self):
        for synth in (False, True, False):
            payload = bytearray(b'\xff' * 0x200000)
            for site in (sysex_cases.spec.CLASSIFY_HOOK, sysex_cases.spec.PROCESS_HOOK):
                at = synthaddr.tr(site) if synth else site
                target = sysex_cases.spec.CODE_AT
                branch = 0xEA000000 | (((target - at - 8) >> 2) & 0xFFFFFF)
                struct.pack_into('<I', payload, at - sysex_cases.IMAGE, branch)
            with patch.object(sysex_cases.synthaddr, 'is_synth', return_value=synth):
                self.assertTrue(sysex_cases.has_hooks(payload))
                payload[at - sysex_cases.IMAGE:at - sysex_cases.IMAGE + 4] = b'\xff' * 4
                self.assertFalse(sysex_cases.has_hooks(payload))

    def test_synth_dispatch_runs_read_only_cases(self):
        with patch.object(sysex_cases.synthaddr, 'is_synth', return_value=True), \
             patch.object(sysex_cases, 'synth_cases', return_value=['read-only']) as cases:
            self.assertEqual(sysex_cases.group_entries(b'image', b'flash', 0), ['read-only'])
            cases.assert_called_once_with(b'image', b'flash')
            self.assertEqual(sysex_cases.group_entries(b'image', b'flash', 1), [])


class Loading(unittest.TestCase):
    def test_loading_screen_is_specific_to_each_firmware(self):
        from types import SimpleNamespace
        from machine import Machine
        for build, loading in [('stock', 46), ('synth', 38)]:
            dev = SimpleNamespace(profile=SimpleNamespace(build=build), screen=lambda: loading)
            self.assertTrue(Machine.loading(dev))
            dev.screen = lambda: 0
            self.assertTrue(Machine.loading(dev))
            for screen in (1, 7, 10):
                dev.screen = lambda screen=screen: screen
                self.assertFalse(Machine.loading(dev))
        dev = SimpleNamespace(profile=SimpleNamespace(build='hacktribe'), screen=lambda: 38)
        self.assertFalse(Machine.loading(dev))

    def test_periodic_boot_observation_remembers_loading_across_the_screen_gap(self):
        from types import SimpleNamespace
        from machine import Machine
        dev = SimpleNamespace(profile=SimpleNamespace(build='synth'), screen=lambda: 38,
                              booted=False, time_ns=300_000_000)
        Machine._look_booted(dev)
        dev.screen = lambda: 0
        self.assertTrue(Machine.loading(dev))
        dev.screen = lambda: 1
        Machine._look_booted(dev)
        self.assertTrue(dev.booted)


class DspStream(unittest.TestCase):
    def test_synth_integrity_covers_the_program_prefix_missing_from_the_sampler_range(self):
        import check
        base = bytes(0x200100)
        modified = bytearray(base)
        modified[0xDFC80] = 1
        with patch.object(check, 'is_synth', return_value=True):
            self.assertFalse(check.same_dsp_program(base, modified))
            modified[0xDFC80] = 0
            modified[0x1218F4] = 1
            self.assertTrue(check.same_dsp_program(base, modified))
        with patch.object(check, 'is_synth', return_value=False):
            self.assertFalse(check.same_dsp_program(base, modified))


class DiceFlash(unittest.TestCase):
    def test_dice_tracks_write_commands_since_boot_even_if_the_image_stays_the_same(self):
        from collections import Counter
        from types import SimpleNamespace
        from dice_cases import DBox
        box = object.__new__(DBox)
        box.m = SimpleNamespace(flash=SimpleNamespace(commands=Counter({0x20: 1, 0x02: 16}), dirty=True))
        before = box.flash_writes()
        box.m.flash.commands[0x03] += 1
        self.assertEqual(box.flash_writes(), before)
        box.m.flash.commands[0x02] += 1
        self.assertNotEqual(box.flash_writes(), before)

    def test_dice_checks_every_flash_byte_including_the_firmware(self):
        from types import SimpleNamespace
        from dice_cases import DBox
        box = object.__new__(DBox)
        box.m = SimpleNamespace(flash=SimpleNamespace(mem=bytearray(0x1000000)))
        before = box.flash_sha()
        box.m.flash.mem[0x20000] = 1
        self.assertNotEqual(box.flash_sha(), before)


class MotionMeasurements(unittest.TestCase):
    def test_motion_output_maps_the_array_base_before_adding_a_lane(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        import struct
        import tap_motion_cases as cases
        box = object.__new__(cases.TBox)
        box.dev = SimpleNamespace(synth=True, u32=lambda addr: 0)
        read = Mock(return_value=struct.pack('<I', 123))
        box.m = SimpleNamespace(uc=SimpleNamespace(mem_read=read))
        with patch.object(cases.synthaddr, 'tr', return_value=0xC0500000):
            self.assertEqual(box.out(2), 123)
            read.assert_called_once_with(0xC0500008, 4)
        with patch.object(cases.synthaddr, 'tr', side_effect=cases.synthaddr.Unmapped('missing')):
            with self.assertRaises(cases.synthaddr.Unmapped):
                box.out()

    def test_app_capture_cases_require_the_runtime_input_hook(self):
        import tap_motion_cases as cases
        with patch('menu_cases.has_menu', return_value=False):
            self.assertEqual(cases.case_app(b'not a firmware fixture', None), [])


class MidiProgramChange(unittest.TestCase):
    def test_program_change_uses_the_channel_reported_by_the_firmware(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from mfx_cases import Box
        box = object.__new__(Box)
        box.dev = object()
        box.m = SimpleNamespace(midi=Mock())
        box.run = Mock()
        with patch('sysex_cases.Link') as link:
            link.return_value.exchange.return_value = ([bytes([0xF0, 0x42, 0x50, 0, 7, 0xF7])], 1)
            box.program_change(12)
            box.m.midi.assert_called_once_with(bytes([0xC7, 12]))
            link.return_value.exchange.return_value = ([], 0)
            with self.assertRaises(ValueError):
                box.program_change(12)
