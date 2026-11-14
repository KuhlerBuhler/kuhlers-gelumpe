# SPDX-License-Identifier: GPL-3.0-or-later
"""Generated SPORT0, DMA and interrupt programs; no audio fixtures."""
import os
import struct
import unittest

from blackfin_backend import BlackfinBackend, BackendError

WORKER = os.environ.get('BFIN_WORKER')
SPORT, RXDMA, TXDMA = 0xFFC00800, 0xFFC00CC0, 0xFFC00D00


@unittest.skipUnless(WORKER, 'build the GNU Blackfin worker and set BFIN_WORKER')
class Sport(unittest.TestCase):
    def setUp(self):
        self.backend = BlackfinBackend(WORKER, operating=True)
        self.addCleanup(self.backend.close)
        self.backend.write(0x1000, bytes(0x10000))
        self.backend.set_register(53, 0x1000)

    def read(self, address, size=2):
        return int.from_bytes(self.backend.read(address, size), 'little')

    def write(self, address, value, size=2):
        self.backend.write(address, value.to_bytes(size, 'little'))

    def clock(self, mode='silence', core_hz=4800000):
        self.backend.configure_sport(core_hz=core_hz, input=mode, seed=1)

    def setup_rx(self, count=16, mode='silence', core_hz=4800000):
        self.clock(mode, core_hz)
        self.write(SPORT + 0x20, 0x4404)
        self.write(SPORT + 0x24, 0x31F)
        self.backend.write(0x20000, b'\xA5' * (count * 4))
        self.write(RXDMA + 4, 0x20000, 4)
        self.write(RXDMA + 0x10, count)
        self.write(RXDMA + 0x14, 4)
        self.write(RXDMA + 8, 0x8B)
        self.write(SPORT + 0x20, 0x4405)

    def test_reset_values_and_register_widths(self):
        self.assertEqual(self.read(SPORT + 0x30), 0x40)
        self.assertEqual(self.read(SPORT + 0x20, 4), 0)
        self.write(SPORT + 4, 0x31F)
        self.assertEqual(self.read(SPORT + 4), 0x31F)
        with self.assertRaises(BackendError):
            self.write(SPORT + 4, 0x31F, 4)

    def test_explicit_clock_is_required(self):
        self.write(SPORT + 0x24, 0x31F)
        with self.assertRaises(BackendError):
            self.write(SPORT + 0x20, 0x4405)

    def test_clock_configuration_is_fixed_for_the_session(self):
        self.clock()
        with self.assertRaises(BackendError):
            self.backend.configure_sport(core_hz=9600000, input='lcg')

    def test_native_block_is_four_stereo_primary_secondary_frames(self):
        self.setup_rx()
        self.backend.run(399)
        self.assertFalse(self.read(RXDMA + 0x28) & 1)
        self.backend.run(4)
        self.assertEqual(self.backend.read(0x20000, 64), bytes(64))
        self.assertEqual(self.read(RXDMA + 0x28) & 9, 1)
        self.assertEqual(self.backend.sport_status()['rx_words'], 16)
        self.assertTrue(self.read(0xFFC00120, 4) & (1 << 16))
        self.write(RXDMA + 0x28, 1)
        self.assertFalse(self.read(0xFFC00120, 4) & (1 << 16))

    def test_lcg_words_are_reproducible_and_advance_only_on_input_frames(self):
        self.setup_rx(mode='lcg')
        self.backend.run(403)
        state, expected = 1, []
        for _ in range(16):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            expected.append(state)
        self.assertEqual(self.backend.read(0x20000, 64), struct.pack('<16I', *expected))
        self.assertEqual(self.backend.sport_status()['lcg_state'], state)

    def test_fractional_clock_has_no_accumulating_frame_drift(self):
        self.setup_rx(count=400, core_hz=4800001)
        self.backend.run(10003)
        self.assertEqual(self.backend.sport_status()['rx_frames'], 100)
        self.assertEqual(self.read(RXDMA + 0x28) & 1, 1)

    def test_fractional_frame_boundary_carries_the_cycle_remainder(self):
        self.setup_rx(core_hz=4824000)
        self.backend.run(200)
        self.assertEqual(self.backend.sport_status()['rx_frames'], 1)
        self.backend.run(2)
        self.assertEqual(self.backend.sport_status()['rx_frames'], 2)

    def test_lcg_input_is_independent_of_service_slice_boundaries(self):
        self.setup_rx(mode='lcg')
        for count in (50, 53, 100, 200):
            self.backend.run(count)
            self.backend.sport_status()
        state, expected = 1, []
        for _ in range(16):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            expected.append(state)
        self.assertEqual(self.backend.read(0x20000, 64), struct.pack('<16I', *expected))

    def test_shared_multichannel_registers_are_locked_when_transmit_is_active(self):
        self.clock()
        self.write(SPORT + 4, 0x31F)
        self.write(SPORT, 0x4401)
        self.write(SPORT + 0x3C, 0x10)
        self.assertEqual(self.read(SPORT + 0x3C), 0)

    def test_disabled_receiver_does_not_copy_or_generate_more_input(self):
        self.setup_rx()
        self.backend.run(103)
        before = self.backend.sport_status()
        self.write(SPORT + 0x20, 0x4404)
        self.backend.run(600)
        after = self.backend.sport_status()
        self.assertEqual(after['rx_frames'], before['rx_frames'])
        self.assertEqual(self.backend.read(0x20010, 48), b'\xA5' * 48)

    def test_descriptor_ring_tracks_the_current_descriptor_and_both_buffers(self):
        self.setup_rx(mode='lcg')
        self.write(RXDMA + 8, 0)
        for descriptor, next_descriptor, target in ((0x30000, 0x30010, 0x20000),
                                                     (0x30010, 0x30000, 0x20100)):
            self.backend.write(descriptor, struct.pack('<IIHHI', next_descriptor, target, 0x768B, 16, 0))
        self.write(RXDMA, 0x30000, 4)
        self.write(RXDMA + 8, 0x760B)
        self.assertEqual(self.read(RXDMA + 0x20, 4), 0x30000)
        self.backend.run(805)
        state, values = 1, []
        for _ in range(32):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            values.append(state)
        for target, words in ((0x20000, values[:16]), (0x20100, values[16:])):
            self.assertEqual(self.backend.read(target, 64), struct.pack('<16I', *words))
        self.assertEqual(self.backend.sport_status()['rx_words'], 32)

    def test_descriptor_cannot_hide_an_unsupported_transfer_width(self):
        self.setup_rx()
        self.write(RXDMA + 8, 0)
        self.backend.write(0x30000, struct.pack('<IIHHI', 0x30000, 0x20000, 0x7687, 16, 0))
        self.write(RXDMA, 0x30000, 4)
        with self.assertRaises(BackendError):
            self.write(RXDMA + 8, 0x760B)
            self.backend.run(110)

    def test_unsupported_word_length_fails_without_a_successful_transfer(self):
        self.clock()
        self.write(SPORT + 0x24, 0x30F)
        with self.assertRaises(BackendError):
            self.write(SPORT + 0x20, 0x4405)

    def wrong_dma_direction(self, channel, config, control, enable):
        self.clock()
        self.write(control, enable & ~1)
        self.write(control + 4, 0x31F)
        self.backend.write(0x20000, bytes(64))
        self.write(channel + 4, 0x20000, 4)
        self.write(channel + 0x10, 16)
        self.write(channel + 0x14, 4)
        self.write(channel + 8, config)
        self.write(control, enable)
        with self.assertRaises(BackendError):
            self.backend.run(110)

    def test_transmit_peripheral_map_cannot_receive_from_sport(self):
        self.wrong_dma_direction(TXDMA, 0x8B, SPORT + 0x20, 0x4405)

    def test_receive_peripheral_map_cannot_transmit_to_sport(self):
        self.wrong_dma_direction(RXDMA, 0x89, SPORT, 0x4401)

    def test_tx_fifo_is_bounded_and_status_is_write_one_to_clear(self):
        for i in range(4):
            self.write(SPORT + 0x10, i, 4)
        self.assertTrue(self.read(SPORT + 0x30) & 8)
        self.write(SPORT + 0x10, 5, 4)
        self.assertTrue(self.read(SPORT + 0x30) & 0x20)
        self.write(SPORT + 0x30, 0x20)
        self.assertFalse(self.read(SPORT + 0x30) & 0x20)
        self.assertTrue(self.read(SPORT + 0x30) & 8)

    def test_tx_dma_fills_fifo_then_follows_the_external_frame_clock(self):
        self.clock()
        self.write(SPORT, 0x4400)
        self.write(SPORT + 4, 0x31F)
        self.backend.write(0x20000, struct.pack('<16I', *range(16)))
        self.write(TXDMA + 4, 0x20000, 4)
        self.write(TXDMA + 0x10, 16)
        self.write(TXDMA + 0x14, 4)
        self.write(TXDMA + 8, 0x89)
        self.write(SPORT, 0x4401)
        self.backend.run(20)
        self.assertEqual(self.read(TXDMA + 0x30), 12)
        self.backend.run(383)
        stats = self.backend.sport_status()
        self.assertEqual(stats['tx_frames'], 4)
        self.assertEqual(stats['tx_words'], 16)
        self.assertEqual(self.read(TXDMA + 0x28) & 9, 1)

    def run_dma_interrupt(self, ack_after):
        entry, main, handler, counter = 0x12000, 0x12100, 0x12200, 0x12300
        irq = RXDMA + 0x28
        code = (0xE108, counter & 65535, 0xE148, counter >> 16, 0x9100, 0x6408, 0x9300,
                0x0C00 | (ack_after << 3), 0x1008,
                0xE108, irq & 65535, 0xE148, irq >> 16, 0xE120, 1, 0x8A00, 0x0011)
        self.backend.write(handler, struct.pack('<17H', *code))
        self.backend.write(entry, struct.pack('<H', 0x0011))
        self.backend.write(main, struct.pack('<H', 0x2000))
        self.backend.write(counter, bytes(4))
        for address, value in ((0xFFE02024, handler), (0xFFC00118, 2),
                               (0xFFC0010C, 1 << 16), (0xFFE02104, 1 << 9)):
            self.write(address, value, 4)
        self.backend.set_register(49, main)
        self.backend.set_register(53, entry)
        self.write(SPORT, 0x4400)
        self.write(SPORT + 4, 0x31F)
        self.backend.write(0x21000, bytes(64))
        self.write(TXDMA + 4, 0x21000, 4)
        self.write(TXDMA + 0x10, 16)
        self.write(TXDMA + 0x14, 4)
        self.write(TXDMA + 8, 0x09)
        self.setup_rx(core_hz=480000)
        self.write(SPORT, 0x4401)
        self.backend.run(200)
        self.assertEqual(self.read(counter, 4), ack_after)
        self.assertFalse(self.read(0xFFC00120, 4) & (1 << 16))
        self.assertEqual(self.backend.register(47) & 63, 0)

    def test_native_dma_interrupt_executes_and_acknowledges(self):
        self.run_dma_interrupt(1)

    def test_unacknowledged_level_interrupt_returns_after_rti(self):
        self.run_dma_interrupt(2)


if __name__ == '__main__':
    unittest.main()
