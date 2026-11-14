# SPDX-License-Identifier: GPL-3.0-or-later
"""Generated cycle, sleep and external FIFO state counterexamples."""
import os
import struct
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from blackfin_backend import BlackfinBackend, BlackfinPort, BackendError

WORKER = os.environ.get('BFIN_WORKER')


@unittest.skipUnless(WORKER, 'build the GNU Blackfin worker and set BFIN_WORKER')
class Clock(unittest.TestCase):
    def setUp(self):
        self.backend = BlackfinBackend(WORKER, operating=True)
        self.addCleanup(self.backend.close)
        self.backend.write(0x1000, bytes(0x10000))
        self.backend.set_register(53, 0x1000)
        self.backend.set_register(0, 0)

    def write(self, address, value, size=4):
        self.backend.write(address, value.to_bytes(size, 'little'))

    def test_cycle_budget_is_exact_and_independent_of_disabled_cycles_counter(self):
        self.backend.set_register(48, 0x30)
        before = self.backend.clock_status()['cycles']
        self.assertEqual(self.backend.advance(7)['cycles'], 7)
        self.assertEqual(self.backend.clock_status()['cycles'], before + 7)
        self.assertEqual(self.backend.register(44), 0)

    def test_enabled_cycles_counter_tracks_partial_instruction_time(self):
        self.backend.set_register(48, 0x32)
        self.backend.write(0x1000, struct.pack('<2H', 0x2000, 0))
        self.backend.advance(1)
        self.assertEqual(self.backend.register(44), 1)
        self.backend.advance(3)
        self.assertEqual(self.backend.register(44), 4)
        self.backend.set_register(48, 0x30)
        self.backend.advance(9)
        self.assertEqual(self.backend.register(44), 4)
        self.assertEqual(self.backend.clock_status()['cycles'], 13)

    def test_unknown_rom_call_reports_context_during_cycle_execution(self):
        self.backend.set_register(53, 0xEF000100)
        with self.assertRaisesRegex(BackendError, 'ROM.*caller=.*PC='):
            self.backend.advance(5)

    def test_multi_cycle_instruction_retains_its_remaining_cycles(self):
        self.backend.write(0x1000, struct.pack('<3H', 0x2002, 0, 0x6038))
        first = self.backend.advance(1)
        self.assertEqual(first['steps'], 1)
        self.assertEqual(self.backend.register(53), 0x1004)
        self.assertEqual(self.backend.clock_status()['remaining'], 4)
        self.assertEqual(self.backend.advance(3)['steps'], 0)
        self.assertEqual(self.backend.register(0), 0)
        self.assertEqual(self.backend.advance(2)['steps'], 1)
        self.assertEqual(self.backend.register(0), 7)

    def test_slicing_preserves_registers_and_total_time(self):
        self.backend.write(0x1000, struct.pack('<2H', 0x6038, 0x2FFF))
        self.backend.advance(100)
        expected = [self.backend.register(n) for n in (0, 44, 45, 53)]
        with BlackfinBackend(WORKER, operating=True) as other:
            other.write(0x1000, struct.pack('<2H', 0x6038, 0x2FFF))
            other.set_register(53, 0x1000)
            for n in (1, 7, 13, 2, 31, 46):
                other.advance(n)
            self.assertEqual([other.register(n) for n in (0, 44, 45, 53)], expected)
            self.assertEqual(other.clock_status(), self.backend.clock_status())

    def test_idle_does_not_execute_next_instruction_when_time_boundary_arrives(self):
        self.backend.write(0x1000, struct.pack('<3H', 0x0020, 0x6038, 0x2000))
        self.backend.advance(3)
        self.assertTrue(self.backend.clock_status()['idle'])
        self.backend.advance(100)
        self.assertEqual(self.backend.register(0), 0)
        self.assertEqual(self.backend.register(53), 0x1002)

    def test_sic_wakeup_is_independent_of_interrupt_mask(self):
        self.backend.write(0x1000, struct.pack('<3H', 0x0020, 0x6038, 0x2000))
        self.write(0xFFC03400, 0x345, 2)
        self.write(0xFFC00164, 1 << 17)
        self.backend.advance(2)
        self.backend.host_event(1)
        self.backend.advance(10)
        self.assertEqual(self.backend.register(0), 7)
        self.assertFalse(self.backend.clock_status()['idle'])

    def test_already_asserted_wake_request_prevents_sleep(self):
        self.backend.write(0x1000, struct.pack('<3H', 0x0020, 0x6038, 0x2000))
        self.write(0xFFC03400, 0x345, 2)
        self.backend.host_event(1)
        self.backend.advance(5)
        self.assertFalse(self.backend.clock_status()['idle'])
        self.assertEqual(self.backend.register(0), 7)

    def test_masked_wakeup_does_not_resume_sleeping_core(self):
        self.backend.write(0x1000, struct.pack('<3H', 0x0020, 0x6038, 0x2000))
        self.write(0xFFC03400, 0x345, 2)
        self.write(0xFFC00164, 0)
        self.backend.advance(2)
        self.backend.host_event(1)
        self.backend.advance(10)
        self.assertEqual(self.backend.register(0), 0)
        self.assertTrue(self.backend.clock_status()['idle'])

    def test_frdy_uses_fifo_depth_without_advancing_time(self):
        self.write(0xFFC03400, 0x345, 2)
        for word in (0xAB, 0, 2, 32, 2, 0, 0):
            self.backend.host_control(word)
        self.backend.advance(2)
        self.assertEqual(self.backend.host_frdy(), 0)

        before = self.backend.clock_status()
        self.assertEqual(self.backend.host_frdy(), 0)
        self.assertEqual(self.backend.clock_status(), before)
        self.backend.host_write(1)
        self.assertEqual(self.backend.host_frdy(), 1)
        for word in range(15):
            self.backend.host_write(word)
        self.backend.advance(3)
        self.assertEqual(self.backend.host_frdy(), 0)


    def test_sport_dma_keeps_time_while_core_sleeps_then_pending_iwr_wakes_it(self):
        self.backend.write(0x1000, struct.pack('<3H', 0x0020, 0x6038, 0x2000))
        self.backend.set_register(48, 0x32)
        self.write(0xFFC00124, 0)
        self.write(0xFFC00164, 0)
        self.backend.configure_sport(core_hz=4800000)
        for address, value, size in ((0xFFC00820, 0x4404, 2), (0xFFC00824, 0x31F, 2),
                                     (0xFFC00CC4, 0x20000, 4), (0xFFC00CD0, 16, 2),
                                     (0xFFC00CD4, 4, 2), (0xFFC00CC8, 0x8B, 2),
                                     (0xFFC00820, 0x4405, 2)):
            self.write(address, value, size)
        self.backend.advance(805)
        self.assertTrue(self.backend.clock_status()['idle'])
        self.assertEqual(self.backend.register(44), 1)
        self.assertEqual(self.backend.register(0), 0)
        self.assertEqual(self.backend.sport_status()['rx_frames'], 8)
        self.assertEqual(self.backend.sport_status()['rx_words'], 16)
        self.write(0xFFC00124, 1 << 16)
        self.backend.advance(10)
        self.assertFalse(self.backend.clock_status()['idle'])
        self.assertEqual(self.backend.register(0), 7)
        self.assertEqual(self.backend.register(44), 11)

    def test_frdy_is_high_outside_the_descriptor_data_window(self):
        self.write(0xFFC03400, 0x345, 2)
        self.assertEqual(self.backend.host_frdy(), 1)

        for word in (0xAB, 0, 2, 16, 2, 0, 0):
            self.backend.host_control(word)
        self.backend.advance(2)
        self.assertEqual(self.backend.host_frdy(), 0)
        for word in range(16):
            self.backend.host_write(word)
        self.backend.advance(3)
        self.assertEqual(self.backend.host_frdy(), 1)

    def test_frdy_does_not_hide_unsupported_acknowledge_mode(self):
        self.write(0xFFC03400, 0x305, 2)
        with self.assertRaises(BackendError):
            self.backend.host_frdy()


class BoundPort(unittest.TestCase):
    def test_clock_configuration_is_owned_by_the_port(self):
        config = dict(core_hz=4800000)
        port = BlackfinPort('unused', operating=True, host_transport='fifo', sport=config)
        port.bind_clock(0)
        port.backend = Mock()
        port.loaded = True
        port.backend.read.return_value = bytes(4)
        port.backend.advance.return_value = dict(cycles=48)
        config['core_hz'] = 9600000
        port.advance_to(10000)
        port.backend.advance.assert_called_once_with(48)
        with self.assertRaises(TypeError):
            port.sport['core_hz'] = 9600000

    def test_cold_host_pin_is_high_but_failed_boot_is_not_hidden(self):
        port = BlackfinPort('unused', operating=True, host_transport='fifo',
                            sport=dict(core_hz=4800000))
        self.assertEqual(port.frdy(), 1)
        with self.assertRaises(BackendError):
            port.boot(bytes(2))
        with self.assertRaises(BackendError):
            port.frdy()

    def test_bound_transport_does_not_run_instructions_for_bus_polls(self):
        port = BlackfinPort('unused', operating=True, host_transport='fifo',
                            sport=dict(core_hz=4800000))
        port.bind_clock(0)
        port.backend = Mock()
        port.backend.process.poll.return_value = None
        port.backend.advance.return_value = dict(cycles=48)
        port.loaded = True
        port.advance_to(10000)
        port.backend.advance.assert_called_once_with(48)
        port.status()
        port.control(0xAB)
        port.write_word(1)
        port.read_word()
        port.backend.run.assert_not_called()

    def test_common_time_rejects_rewind_and_missing_test_frequency(self):
        with self.assertRaises(ValueError):
            BlackfinPort('unused', operating=True, host_transport='fifo').bind_clock(0)
        port = BlackfinPort('unused', operating=True, host_transport='fifo',
                            sport=dict(core_hz=4800000))
        port.bind_clock(200)
        with self.assertRaises(ValueError):
            port.advance_to(199)

    def test_readiness_is_observed_after_bound_execution(self):
        port = BlackfinPort('unused', operating=True, host_transport='fifo',
                            sport=dict(core_hz=4800000))
        port.bind_clock(0)
        port.loaded = True
        port.backend = Mock()
        port.backend.advance.return_value = dict(cycles=48, steps=7)
        port.backend.read.return_value = bytes(4)
        port.advance_to(10000)
        self.assertFalse(port.initialized)
        port.backend.read.return_value = b'\x01\x00\x00\x00'
        port.advance_to(20000)
        self.assertTrue(port.initialized)
        self.assertTrue(port.boot_report['ready'])
        self.assertEqual(port.boot_report['clock_cycles'], 96)

    def test_gpio_reads_native_frdy_instead_of_toggling(self):
        from machine import Machine
        machine = Machine.__new__(Machine)
        machine.gpio, machine.inputs = {}, {}
        machine.dsp_backend = Mock(host_transport='fifo', clock_bound=True)
        machine.dsp_backend.frdy.return_value = 1
        machine.time_ns = 100
        self.assertEqual(machine.gpio_read(0x98) & 2, 2)
        self.assertEqual(machine.gpio_read(0x98) & 2, 2)
        machine.dsp_backend.frdy.return_value = 0
        self.assertEqual(machine.gpio_read(0x98) & 2, 0)


class CoupledSetup(unittest.TestCase):
    def test_synth_case_uses_blue_hardware_markers(self):
        from blackfin_cases import cases
        from machine import hardware_of_flash
        profile = SimpleNamespace(build='synth')
        machine = Mock(time_ns=10000000, asserts=[], powered=True)
        with patch('blackfin_cases.identify', return_value=profile), \
             patch('blackfin_cases.Machine', return_value=machine) as constructor, \
             patch('blackfin_cases.BlackfinPort') as endpoint:
            endpoint.return_value.__enter__.return_value.loaded = False
            report = cases(bytes(32), 'unused', core_hz=4800000, seconds=.01)
        self.assertFalse(report['ok'])
        self.assertEqual(hardware_of_flash(constructor.call_args.kwargs['flash']), 'blue')


@unittest.skipUnless(WORKER, 'build the GNU Blackfin worker and set BFIN_WORKER')
class ArmClock(unittest.TestCase):
    def test_default_slice_has_a_finite_boundary_when_arm_waits_without_events(self):
        from machine import Machine, AINTC
        from test_blackfin_backend import stream
        profile = SimpleNamespace(assert_handler=0xC0100000, flash_read=0xC0100004,
                                  dsp_upload=0xC0100008, tx_full=0xC010000C,
                                  user_mark=bytes(12))
        with BlackfinPort(WORKER, operating=True, host_transport='fifo',
                          sport=dict(core_hz=4800000)) as port:
            machine = Machine(bytes(0x1000), profile=profile, dsp_backend=port)
            machine.pace = False
            port.boot(stream(struct.pack('<2H', 0, 0x2FFF)))
            machine.uc.mem_write(0xC0000070, struct.pack('<I', 0xEE070F90))
            machine.uc.reg_write(machine.A.UC_ARM_REG_PC, 0xC0000070)
            machine.run_slice()
            self.assertLessEqual(machine.time_ns, 1000000)
            self.assertEqual(port.backend.clock_status()['cycles'], machine.time_ns * 4800000 // 1000000000)
            machine.uc.mem_write(0xC0000074, struct.pack('<2I', 0xE3A00007, 0xEAFFFFFE))
            machine.run_slice()
            self.assertEqual(machine.reg(machine.A.UC_ARM_REG_PC), 0xC0000074)
            self.assertEqual(machine.reg(machine.A.UC_ARM_REG_R0), 0)
            self.assertEqual(machine.insns, 1)
            machine.raw.add(7)
            machine.enabled.add(7)
            machine.cmr[7] = 2
            machine.run_slice(machine.time_ns + 100)
            self.assertEqual(machine.reg(machine.A.UC_ARM_REG_R0), 0)
            machine.regs[AINTC + 0x10] = 1
            machine.regs[AINTC + 0x1500] = 2
            machine.run_slice(machine.time_ns + 100)
            self.assertEqual(machine.reg(machine.A.UC_ARM_REG_R0), 7)
            machine.raw.clear()
            machine.uc.reg_write(machine.A.UC_ARM_REG_PC, 0xC0000070)
            machine.uc.reg_write(machine.A.UC_ARM_REG_R0, 0)
            machine.run_slice()
            machine.uc.mem_write(0x18, struct.pack('<2I', 0xE3A00009, 0xEAFFFFFE))
            machine.uc.reg_write(machine.A.UC_ARM_REG_CPSR, 0x13)
            machine.raw.add(7)
            machine.irq()
            machine.raw.clear()
            machine.run_slice(machine.time_ns + 100)
            self.assertEqual(machine.reg(machine.A.UC_ARM_REG_R0), 9)

    def test_generated_arm_instructions_and_gpio_share_the_dsp_clock(self):
        from machine import Machine
        from test_blackfin_backend import stream
        profile = SimpleNamespace(assert_handler=0xC0100000, flash_read=0xC0100004,
                                  dsp_upload=0xC0100008, tx_full=0xC010000C,
                                  user_mark=bytes(12))
        with BlackfinPort(WORKER, operating=True, host_transport='fifo',
                          sport=dict(core_hz=4800000)) as port:
            machine = Machine(bytes(0x1000), profile=profile, dsp_backend=port)
            machine.pace = False
            port.boot(stream(struct.pack('<2H', 0, 0x2FFF)))
            machine.uc.mem_write(0xC0000070, struct.pack('<2I', 0xE5910000, 0xEAFFFFFD))
            machine.uc.reg_write(machine.A.UC_ARM_REG_R1, 0x01E26098)
            machine.uc.reg_write(machine.A.UC_ARM_REG_PC, 0xC0000070)
            machine.run_slice(10000)
            self.assertEqual(machine.time_ns, 10000)
            self.assertEqual(machine.insns, 2000)
            self.assertEqual(port.backend.clock_status()['cycles'], 48)
            self.assertEqual(machine.reg(machine.A.UC_ARM_REG_R0) & 2, 2)


if __name__ == '__main__':
    unittest.main()
