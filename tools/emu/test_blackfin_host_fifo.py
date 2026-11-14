# SPDX-License-Identifier: GPL-3.0-or-later
"""Generated HOSTDP bus words, RAM patterns and interrupt handlers."""
import os
import struct
import unittest

from blackfin_backend import BlackfinBackend, BackendError

WORKER = os.environ.get('BFIN_WORKER')
CONTROL, STATUS = 0xFFC03400, 0xFFC03404
DMA1, DATA = 0xFFC00C40, 0x20000


@unittest.skipUnless(WORKER, 'build the GNU Blackfin worker and set BFIN_WORKER')
class HostFIFO(unittest.TestCase):
    def setUp(self):
        self.backend = BlackfinBackend(WORKER, operating=True)
        self.addCleanup(self.backend.close)
        self.assertTrue(callable(getattr(self.backend, 'host_status', None)),
                        'native HOSTDP bus API is missing')
        self.backend.write(0x1000, bytes(0x10000))
        self.backend.set_register(53, 0x1000)
        self.write(CONTROL, 0x345)

    def write(self, address, value, size=2):
        self.backend.write(address, value.to_bytes(size, 'little'))

    def read(self, address, size=2):
        return int.from_bytes(self.backend.read(address, size), 'little')

    def header(self, command, address=DATA, count=16, modify=2):
        return (command, address & 65535, address >> 16, count, modify, 0, 0)

    def configure(self, command, address=DATA, count=16):
        self.assertTrue(self.backend.host_status() & 0x80)
        for word in self.header(command, address, count):
            self.backend.host_control(word)
        self.backend.run(3)

    def acknowledge_write(self):
        self.write(DMA1 + 0x28, 1)
        self.write(STATUS, 8)

    def test_descriptor_is_only_forwarded_after_all_seven_words(self):
        words = self.header(0xAB)
        for word in words[:-1]:
            self.backend.host_control(word)
        self.backend.run(5)
        self.assertEqual(self.read(DMA1 + 4, 4), 0)
        self.assertFalse(self.backend.host_status() & 1)
        self.backend.host_control(words[-1])
        self.assertFalse(self.backend.host_status() & 1)
        self.backend.run(2)
        self.assertEqual(self.read(DMA1 + 4, 4), DATA)
        self.assertEqual(self.read(DMA1 + 0x10), 16)
        self.assertEqual(self.read(DMA1 + 0x14), 2)
        self.assertEqual(self.backend.host_status() & 0x109, 0x101)

    def test_host_write_waits_in_fifo_then_dma_changes_only_its_target(self):
        self.backend.write(DATA - 2, b'\xA5' * 36)
        self.configure(0xAB)
        for word in range(16):
            self.backend.host_write(word)
        self.assertTrue(self.backend.host_status() & 2)
        self.assertEqual(self.backend.read(DATA - 2, 36), b'\xA5' * 36)
        self.backend.run(3)
        self.assertEqual(self.backend.read(DATA - 2, 36), b'\xA5' * 2 + struct.pack('<16H', *range(16)) + b'\xA5' * 2)
        self.assertTrue(self.backend.host_status() & 4)
        self.assertEqual(self.read(DMA1 + 0x28) & 9, 1)
        self.assertTrue(self.read(0xFFC00120, 4) & (1 << 28))
        self.assertFalse(self.backend.host_status() & 8)
        self.acknowledge_write()
        self.assertEqual(self.backend.host_status() & 9, 8)

    def test_fifo_does_not_silently_accept_a_seventeenth_word(self):
        self.configure(0xAB, count=32)
        for word in range(16):
            self.backend.host_write(word)
        with self.assertRaises(BackendError):
            self.backend.host_write(17)

    def test_multiple_fifo_chunks_use_16_bit_counts_and_modifiers(self):
        self.configure(0xAB, count=32)
        for start in (0, 16):
            for word in range(start, start + 16):
                self.backend.host_write(word ^ 0xA55A)
            self.backend.run(3)
        self.assertEqual(self.backend.read(DATA, 64), struct.pack('<32H', *(v ^ 0xA55A for v in range(32))))

    def test_read_done_is_after_the_last_host_read_not_dma_prefill(self):
        values = [i * 193 + 17 for i in range(16)]
        self.backend.write(DATA, struct.pack('<16H', *values))
        self.configure(0xA9)
        self.assertTrue(self.backend.host_status() & 2)
        self.assertFalse(self.backend.host_status() & 0x8000)
        self.assertFalse(self.read(0xFFC00120, 4) & (1 << 28))
        self.assertEqual([self.backend.host_read() for _ in range(15)], values[:15])
        self.assertFalse(self.backend.host_status() & 0x8000)
        self.assertEqual(self.backend.host_read(), values[-1])
        self.assertTrue(self.backend.host_status() & 0x8000)
        self.assertTrue(self.read(0xFFC00160, 4) & (1 << 18))

    def test_read_fifo_refills_for_a_second_chunk(self):
        self.backend.write(DATA, struct.pack('<32H', *range(32)))
        self.configure(0xA9, count=32)
        result = [self.backend.host_read() for _ in range(16)]
        self.backend.run(3)
        result += [self.backend.host_read() for _ in range(16)]
        self.assertEqual(result, list(range(32)))

    def test_empty_fifo_is_an_error_instead_of_an_invented_zero(self):
        self.configure(0xA9, count=32)
        for _ in range(16):
            self.backend.host_read()
        with self.assertRaises(BackendError):
            self.backend.host_read()

    def test_configuration_word_equal_to_finish_is_not_a_command(self):
        address = DATA + 0x2C
        self.configure(0xAB, address)
        self.assertEqual(self.read(DMA1 + 4, 4), address)

    def test_following_descriptor_waits_for_native_completion_ack(self):
        self.configure(0xAB)
        for word in self.header(0xA9, DATA + 0x100):
            self.backend.host_control(word)
        self.backend.run(3)
        self.assertEqual(self.read(DMA1 + 4, 4), DATA)
        self.assertTrue(self.backend.host_status() & 0x100)
        self.assertFalse(self.backend.host_status() & 0x80)
        for word in range(16):
            self.backend.host_write(word)
        self.backend.run(3)
        self.acknowledge_write()
        self.backend.run(3)
        self.assertEqual(self.read(DMA1 + 4, 4), DATA + 0x100)
        self.assertFalse(self.backend.host_status() & 0x100)

    def test_reset_cancels_queued_descriptor_and_pending_dma(self):
        self.configure(0xAB, count=32)
        for word in range(16):
            self.backend.host_write(word)
        for word in self.header(0xA9, DATA + 0x100):
            self.backend.host_control(word)
        self.write(CONTROL, 0x34D)
        self.backend.run(10)
        self.assertEqual(self.backend.read(DATA, 64), bytes(64))
        self.assertFalse(self.read(DMA1 + 0x28) & 8)
        self.assertTrue(self.backend.host_status() & 4)
        self.assertFalse(self.backend.host_status() & 1)

    def test_finish_drops_host_fifo_and_notifies_write_completion(self):
        self.configure(0xAB, count=32)
        for word in range(16):
            self.backend.host_write(word)
        self.backend.host_control(0x2C)
        self.backend.run(5)
        self.assertEqual(self.backend.read(DATA, 64), bytes(64))
        self.assertEqual(self.read(DMA1 + 0x28) & 9, 1)
        self.assertTrue(self.backend.host_status() & 4)

    def test_acknowledged_descriptor_releases_dma1_ownership_before_reset(self):
        self.configure(0xAB)
        for word in range(16):
            self.backend.host_write(word)
        self.backend.run(3)
        self.acknowledge_write()
        self.write(DMA1 + 0x2C, 0x3000)
        self.write(DMA1 + 0x14, 4)
        self.write(DMA1 + 8, 0x8B)
        self.write(CONTROL, 0x34D)
        self.assertTrue(self.read(DMA1 + 0x28) & 8)
        self.assertEqual(self.read(DMA1 + 0x2C), 0x3000)

    def test_reset_refuses_a_channel_replaced_before_completion_ack(self):
        self.configure(0xAB)
        for word in range(16):
            self.backend.host_write(word)
        self.backend.run(3)
        self.write(DMA1 + 0x2C, 0x3000)
        self.write(DMA1 + 0x14, 4)
        self.write(DMA1 + 8, 0x8B)
        with self.assertRaises(BackendError):
            self.write(CONTROL, 0x34D)

    def test_active_override_is_rejected_before_queued_data_can_move(self):
        self.configure(0xAB, count=32)
        for word in range(16):
            self.backend.host_write(word)
        with self.assertRaises(BackendError):
            self.write(CONTROL, 0x365)

    def test_disabling_a_pending_descriptor_is_rejected_instead_of_losing_it(self):
        for word in self.header(0xAB):
            self.backend.host_control(word)
        with self.assertRaises(BackendError):
            self.write(CONTROL, 0x344)

    def test_identical_dma_reprogramming_does_not_preserve_old_host_ownership(self):
        self.configure(0xAB)
        for word in range(16):
            self.backend.host_write(word)
        self.backend.run(3)
        self.write(DMA1 + 8, self.read(DMA1 + 8))
        with self.assertRaises(BackendError):
            self.write(STATUS, 8)

    def test_early_completion_does_not_discard_incomplete_data(self):
        self.configure(0xAB)
        self.backend.host_write(0x1234)
        with self.assertRaises(BackendError):
            self.write(STATUS, 8)

    def test_active_timeout_mode_is_not_silently_accepted(self):
        self.configure(0xAB)
        with self.assertRaises(BackendError):
            self.write(CONTROL, 0x3C5)

    def test_active_burst_mode_is_not_silently_accepted(self):
        self.configure(0xAB)
        with self.assertRaises(BackendError):
            self.write(CONTROL, 0x745)

    def test_access_disable_does_not_discard_words_already_accepted(self):
        self.configure(0xAB)
        for word in range(16):
            self.backend.host_write(word)
        self.write(CONTROL, 0x245)
        self.backend.run(3)
        self.assertEqual(self.backend.read(DATA, 32), struct.pack('<16H', *range(16)))

    def test_disabled_host_read_does_not_return_an_invented_word(self):
        self.configure(0xA9)
        self.write(CONTROL, 0x145)
        with self.assertRaises(BackendError):
            self.backend.host_read()

    def test_unimplemented_active_read_finish_fails_explicitly(self):
        self.configure(0xA9)
        with self.assertRaises(BackendError):
            self.backend.host_control(0x2C)

    def test_unsupported_size_is_rejected_before_a_dma_descriptor_is_started(self):
        with self.assertRaises(BackendError):
            for word in self.header(0xAB, count=2):
                self.backend.host_control(word)

    def test_mmio_target_is_not_treated_as_dma_ram(self):
        with self.assertRaises(BackendError):
            for word in self.header(0xAB, address=CONTROL):
                self.backend.host_control(word)

    def test_data_direction_is_checked_before_touching_the_fifo(self):
        self.configure(0xAB)
        with self.assertRaises(BackendError):
            self.backend.host_read()

    def interrupt_program(self, read):
        entry, main, handler, counter = 0x12000, 0x12100, 0x12200, 0x12300
        code = [0xE108, counter & 65535, 0xE148, counter >> 16, 0x9100, 0x6408, 0x9300]
        if not read:
            irq = DMA1 + 0x28
            code += [0xE108, irq & 65535, 0xE148, irq >> 16, 0xE120, 1, 0x8A00]
        code += [0xE108, STATUS & 65535, 0xE148, STATUS >> 16, 0xE120, 0x8008 if read else 8, 0x8A00, 0x0011]
        self.backend.write(handler, struct.pack('<' + 'H' * len(code), *code))
        self.backend.write(entry, struct.pack('<H', 0x0011))
        self.backend.write(main, struct.pack('<H', 0x2000))
        self.write(counter, 0, 4)
        for address, value in ((0xFFE02024, handler),
                               (0xFFC00158 if read else 0xFFC0011C, 2 << (8 if read else 16)),
                               (0xFFC0014C if read else 0xFFC0010C, 1 << (18 if read else 28)),
                               (0xFFE02104, 1 << 9)):
            self.write(address, value, 4)
        self.backend.set_register(49, main)
        self.backend.set_register(53, entry)
        return counter

    def test_native_write_interrupt_acknowledges_dma_and_host(self):
        counter = self.interrupt_program(False)
        self.configure(0xAB)
        for word in range(16):
            self.backend.host_write(word)
        self.backend.run(200)
        self.assertEqual(self.read(counter, 4), 1)
        self.assertEqual(self.backend.host_status() & 9, 8)
        self.assertFalse(self.read(0xFFC00120, 4) & (1 << 28))

    def test_native_read_interrupt_runs_only_after_final_host_word(self):
        counter = self.interrupt_program(True)
        self.configure(0xA9)
        self.backend.run(200)
        self.assertEqual(self.read(counter, 4), 0)
        for _ in range(16):
            self.backend.host_read()
        self.backend.run(200)
        self.assertEqual(self.read(counter, 4), 1)
        self.assertEqual(self.backend.host_status() & 0x8009, 8)
