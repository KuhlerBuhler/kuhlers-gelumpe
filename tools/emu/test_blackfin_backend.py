# SPDX-License-Identifier: GPL-2.0-only
"""Generated Blackfin programs; no firmware or sample fixtures."""
import os
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from blackfin_backend import BlackfinBackend, BlackfinPort, BackendError
import blackfin_worker

WORKER = blackfin_worker.find()
ENTRY, DATA = 0x1000, 0x100000


def program(address=DATA):
    return struct.pack('<9H', 0x6038, 0x63F9, 0xE108, address & 65535,
                       0xE148, address >> 16, 0xE600, 0, 0x2000)


def stream(data, target=0xFFA00000):
    header = bytearray(struct.pack('<IIII', 0xAD008000, target, len(data), 0))
    checksum = 0
    for value in header:
        checksum ^= value
    header[2] = checksum
    return bytes(header) + data


class Failures(unittest.TestCase):
    def test_old_worker_requires_rebuilding_the_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worker'
            path.write_text("#!/usr/bin/env python3\nimport os,struct,time\nos.write(1,struct.pack('<II',0,5)+b'BFIN8')\ntime.sleep(30)\n")
            path.chmod(0o755)
            with self.assertRaisesRegex(BackendError, 'rebuild.*BFIN9'):
                BlackfinBackend(path)

    def test_missing_worker_reports_the_required_build(self):
        with self.assertRaisesRegex(BackendError, 'worker'):
            BlackfinBackend('/does/not/exist')

    def test_unresponsive_worker_is_terminated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worker'
            path.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n')
            path.chmod(0o755)
            with self.assertRaisesRegex(BackendError, 'deadline'):
                BlackfinBackend(path, timeout=.1)

    def test_a_worker_that_stops_reading_cannot_block_a_large_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worker'
            path.write_text("#!/usr/bin/env python3\nimport os,struct,time\nos.write(1,struct.pack('<II',0,5)+b'BFIN9')\ntime.sleep(30)\n")
            path.chmod(0o755)
            with BlackfinBackend(path, timeout=3) as backend:
                backend.timeout = .1
                with self.assertRaisesRegex(BackendError, 'deadline'):
                    backend.write(DATA, bytes(1 << 20))

    def test_a_crashed_worker_is_a_failure_and_cannot_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worker'
            path.write_text("#!/usr/bin/env python3\nimport os,struct\nos.write(1,struct.pack('<II',0,5)+b'BFIN9')\nos.read(0,12)\nos._exit(139)\n")
            path.chmod(0o755)
            with BlackfinBackend(path, timeout=3) as backend:
                with self.assertRaisesRegex(BackendError, 'exited before answering'):
                    backend.read(DATA, 4)
                self.assertIsNone(backend.process)
                with self.assertRaisesRegex(BackendError, 'closed'):
                    backend.run(20)


@unittest.skipUnless(WORKER, 'build a Blackfin worker (tools/dsp/build_qemu.py) or set BFIN_WORKER')
class Execution(unittest.TestCase):
    def setUp(self):
        self.backend = BlackfinBackend(WORKER)
        self.addCleanup(self.backend.close)

    def test_shared_memory_channel_carries_full_size_transfers_around_the_ring(self):
        import blackfin_backend
        if os.environ.get('BLECH_WORKER_CHANNEL') == 'pipe' or blackfin_backend._channel_library() is None:
            self.skipTest('shared-memory channel not in use')
        self.assertIsNotNone(self.backend._channel)
        size = blackfin_backend.LIMIT
        for round_ in range(6):        # 6 MiB each way through 4 MiB rings
            data = bytes((round_ * 7 + i) & 0xFF for i in range(256)) * (size // 256)
            self.backend.write(DATA, data)
            self.assertEqual(self.backend.read(DATA, size), data)

    def _timer_loop(self, backend):
        backend.write(ENTRY, struct.pack('<H', 0x2000))       # a jump to itself, the core timer counts
        backend.set_register(53, ENTRY)
        backend.set_register(48, 0x32)
        for address, value in ((0xFFE03008, 0), (0xFFE0300C, 100000), (0xFFE03000, 3)):
            backend.write(address, struct.pack('<I', value))
        backend.run(37)

    @staticmethod
    def _state(backend):
        return ([backend.register(i) for i in range(54)], backend.read(0xFFE0300C, 4),
                backend.read(DATA, 64), backend.clock_status())

    def test_a_worker_copy_goes_on_exactly_as_the_original(self):
        with BlackfinBackend(WORKER, operating=True) as backend:
            self._timer_loop(backend)
            backend.write(DATA, bytes(range(64)))
            with backend.fork() as copy:
                self.assertEqual(self._state(copy), self._state(backend))
                for _ in range(3):
                    backend.run(500)
                    copy.run(500)
                    self.assertEqual(self._state(copy), self._state(backend))
                copy.write(DATA, bytes(64))                   # the copy's memory is its own
                self.assertEqual(backend.read(DATA, 64), bytes(range(64)))
            backend.run(10)                                   # the original outlives its copy

    @staticmethod
    def _status_later(backend, nops):
        """`nops` NOPs, then a halfword store of 0x10 to HOST_STATUS (the bus status changes), then a jump to itself."""
        store = 0x8000 | (1 << 11) | (1 << 9)
        backend.write(ENTRY, bytes(2 * nops) + struct.pack('<3H', store, 0x2000, 0x2000))
        for number, value in ((8, 0xFFC03404), (0, 0x10), (53, ENTRY)):
            backend.set_register(number, value)

    def test_poll_ahead_matches_one_advance_per_poll(self):
        steps = [3, 0, 5, 7, 2] * 40
        for nops in (60, 5000):              # the status changes within the steps, and not at all
            with BlackfinBackend(WORKER, operating=True) as one, BlackfinBackend(WORKER, operating=True) as many:
                for backend in (one, many):
                    self._status_later(backend, nops)
                status = one.host_status()
                done = 0
                for step in steps:
                    done += 1
                    if step:
                        one.advance(step)
                    if one.host_status() != status:
                        break
                self.assertEqual(many.ahead(status, steps), (done, one.host_status()))
                self.assertEqual(done < len(steps), nops == 60)
                self.assertEqual(self._state(many), self._state(one))

    def test_cases_run_from_one_state_in_process_copies(self):
        port = BlackfinPort(WORKER, operating=True)
        port.backend = BlackfinBackend(WORKER, operating=True)
        self.addCleanup(port.close)
        self._timer_loop(port.backend)
        before = self._state(port.backend)

        def case():
            port.backend.run(800)
            return self._state(port.backend)
        first, second = port.run_copy(case), port.run_copy(case)
        self.assertEqual(first, second)
        self.assertEqual(self._state(port.backend), before)   # the parent's worker did not move
        self.assertEqual(case(), first)
        with self.assertRaisesRegex(BackendError, 'process copy failed: ValueError: broken case'):
            port.run_copy(lambda: (_ for _ in ()).throw(ValueError('broken case')))

    def test_real_instructions_produce_memory_and_sign_extended_registers(self):
        self.backend.write(ENTRY, program())
        self.backend.set_register(53, ENTRY)
        result = self.backend.run(20)
        self.assertEqual(result['steps'], 20)
        self.assertEqual(self.backend.register(0), 7)
        self.assertEqual(self.backend.register(1), 0xFFFFFFFF)
        self.assertEqual(self.backend.read(DATA, 4), struct.pack('<I', 7))
        self.assertEqual(self.backend.register(53), ENTRY + 16)

    def test_parallel_arithmetic_store_reads_the_original_source_register(self):
        # DSP32ALU fields and LDST follow GNU include/opcode/bfin.h.
        cases = ((False, False, 100, 104), (True, False, 100, 96),
                 (False, True, 100, 104), (True, True, 100, 96),
                 (False, True, 0x7FFFFFFF, 0x7FFFFFFF),
                 (True, True, 0x80000000, 0x80000000))
        for subtract, saturate, before, after in cases:
            with self.subTest(subtract=subtract, saturate=saturate):
                operation = (int(subtract) << 14) | (int(saturate) << 13) | (1 << 9) | (1 << 3) | 2
                code = struct.pack('<6H', 0xCC04, operation, 0x9301, 0, 0xB041, 0x2000)
                self.backend.write(ENTRY, code)
                self.backend.set_register(1, before)
                self.backend.set_register(2, 4)
                self.backend.set_register(8, DATA)
                self.backend.set_register(53, ENTRY)
                self.backend.run(10)
                self.assertEqual(self.backend.read(DATA, 8), struct.pack('<II', before, after))
                self.assertEqual(self.backend.register(1), after)

    def test_parallel_signbits_store_reads_the_original_destination_register(self):
        cases = ((5, 0, 0x02000000, 5), (5, 1, 0x200, 5), (5, 2, 0x02000000, 5),
                 (5, 0, 0, 31), (5, 0, 0xFFFFFFFF, 31), (5, 1, 0x8000, 0),
                 (6, 0, 0x0200000000, 0xFFFD), (6, 1, 0x0200000000, 0xFFFD),
                 (6, 0, 0, 31), (6, 1, 0x8000000000, 0xFFF8))
        for opcode, operation, value, expected in cases:
            with self.subTest(opcode=opcode, operation=operation, value=value):
                instruction = 0xC6000000 | (1 << 27) | (opcode << 16) | (operation << 14) | (1 << 9) | 3
                self.backend.write(ENTRY, struct.pack('<6H', instruction >> 16, instruction & 65535,
                                                     0x9301, 0, 0xB041, 0x2000))
                self.backend.set_register(1, 0xAABBF75F)
                if opcode == 5:
                    self.backend.set_register(3, value)
                else:
                    self.backend.set_register(32+operation*2, value >> 32)
                    self.backend.set_register(33+operation*2, value & 0xFFFFFFFF)
                self.backend.set_register(8, DATA)
                self.backend.set_register(53, ENTRY)
                self.backend.run(10)
                self.assertEqual(self.backend.read(DATA, 8), struct.pack('<II', 0xAABBF75F, 0xAABB0000 | expected))

    def test_parallel_pointer_load_store_reads_the_original_register(self):
        # MNOP || R0 = [P0++] || [I1++] = R0, the copy loop the native DSP uses for its handler table.
        self.backend.write(ENTRY, struct.pack('<5H', 0xC803, 0x1800, 0x9000, 0x9E08, 0x2000))
        self.backend.write(DATA, struct.pack('<5I', 0xAAAAAAAA, 0, 0, 0, 0x55555555))
        self.backend.set_register(0, 0x11111111)
        self.backend.set_register(8, DATA)
        self.backend.set_register(17, DATA + 16)
        self.backend.set_register(53, ENTRY)
        self.backend.run(3)
        self.assertEqual(self.backend.read(DATA + 16, 4), struct.pack('<I', 0x11111111))
        self.assertEqual(self.backend.register(0), 0xAAAAAAAA)
        self.assertEqual(self.backend.register(8), DATA + 4)
        self.assertEqual(self.backend.register(17), DATA + 20)

    def test_parallel_negate_store_reads_the_original_register(self):
        # R1 = -R0 (NS) || [P2 + 0x10] = R1 || NOP
        self.backend.write(ENTRY, struct.pack('<5H', 0xCC07, 0xC200, 0xB111, 0x0000, 0x2000))
        self.backend.set_register(0, 5)
        self.backend.set_register(1, 0x12345678)
        self.backend.set_register(10, DATA)
        self.backend.set_register(53, ENTRY)
        self.backend.run(3)
        self.assertEqual(self.backend.read(DATA + 16, 4), struct.pack('<I', 0x12345678))
        self.assertEqual(self.backend.register(1), 0xFFFFFFFB)

    def test_run_stops_at_a_requested_pc(self):
        self.backend.write(ENTRY, program())
        self.backend.set_register(53, ENTRY)
        result = self.backend.run(100, until=ENTRY + 16)
        self.assertEqual(result['steps'], 5)
        self.assertTrue(result['reached'])

    def test_rewritten_l1_code_runs_the_new_instructions(self):
        with BlackfinBackend(WORKER, operating=True) as backend:
            for entry in (ENTRY, 0xFFA00000):
                for value in (1, 2, 3):
                    with self.subTest(entry=hex(entry), value=value):
                        backend.write(entry, struct.pack('<2H', 0x6000 | value << 3, 0x2000))   # R0 = value
                        backend.set_register(53, entry)
                        backend.run(2)
                        self.assertEqual(backend.register(0), value)

    def test_queued_requests_never_reach_the_dsp_as_uart_input(self):
        # GNU's UART reads the simulator's stdin; requests queued behind this one must not show up there.
        with BlackfinBackend(WORKER, operating=True) as backend:
            data = bytes(range(256)) * 1024   # more than stdio buffers, so part of it waits on the pipe
            backend._send(struct.pack('<III', 1, 0xFFC00414, 2) + struct.pack('<III', 2, DATA, len(data)) + data
                          + struct.pack('<III', 1, DATA + len(data) - 4, 4))
            status, = struct.unpack('<H', backend._response())
            self.assertFalse(status & 1)   # LSR DR: no received byte
            self.assertEqual(backend._response(), b'')
            self.assertEqual(backend._response(), data[-4:])

    def test_core_timer_observes_all_modeled_instruction_cycles(self):
        with BlackfinBackend(WORKER, operating=True) as backend:
            backend.write(ENTRY, struct.pack('<H', 0x2000))
            backend.set_register(53, ENTRY)
            backend.set_register(48, 0x32)
            self.assertEqual(backend.run(1, until=ENTRY)['steps'], 0)
            for address, value in ((0xFFE03008, 0), (0xFFE0300C, 10000), (0xFFE03000, 3)):
                backend.write(address, struct.pack('<I', value))
            before = backend.register(44)
            result = backend.run(100)
            cycles = (backend.register(44) - before) & 0xFFFFFFFF
            remaining, = struct.unpack('<I', backend.read(0xFFE0300C, 4))
            self.assertEqual(result['steps'], 100)
            self.assertGreater(cycles, 100)
            self.assertEqual(10000 - remaining, cycles)
            backend.run(100)
            after, = struct.unpack('<I', backend.read(0xFFE0300C, 4))
            self.assertEqual(remaining - after, cycles)

    def test_illegal_instruction_raises_and_invalidates_the_backend(self):
        self.backend.write(ENTRY, b'\xff\x00')
        self.backend.set_register(53, ENTRY)
        with self.assertRaises(BackendError):
            self.backend.run(10)
        with self.assertRaises(BackendError):
            self.backend.read(DATA, 4)

    def test_invalid_memory_and_oversized_requests_are_rejected(self):
        with self.assertRaises(BackendError):
            self.backend.read(0x40000000, 4)
        with self.assertRaises((ValueError, BackendError)):
            self.backend.read(DATA, 1 << 25)

    def test_empty_gnu_boot_rom_is_not_mapped_as_executable_memory(self):
        with BlackfinBackend(WORKER, operating=True) as backend:
            with self.assertRaises(BackendError):
                backend.read(0xEF000038, 4)

    def test_executing_missing_rom_fails_before_a_fake_rom_instruction(self):
        with BlackfinBackend(WORKER, operating=True) as backend:
            backend.set_register(53, 0xEF000038)
            with self.assertRaisesRegex(BackendError, 'on-chip ROM'):
                backend.run(20)

    def test_unknown_rom_reports_the_stopped_pc_caller_and_registers(self):
        self.backend.set_register(0, 0x711)
        self.backend.set_register(1, DATA)
        self.backend.set_register(37, ENTRY + 2)
        self.backend.set_register(53, 0xEF00007E)
        with self.assertRaises(BackendError) as caught:
            self.backend.run(20)
        detail = str(caught.exception)
        for value in ('PC=0xef00007e', 'RETS=0x00001002', 'R0=0x00000711', 'R1=0x00100000', 'SP='):
            self.assertIn(value, detail)
        with self.assertRaises(BackendError):
            self.backend.read(DATA, 4)

    def test_rom_entry_cannot_be_accepted_as_a_successful_breakpoint(self):
        self.backend.set_register(53, 0xEF00007E)
        with self.assertRaisesRegex(BackendError, 'on-chip ROM'):
            self.backend.run(20, until=0xEF00007E)

    def test_rom_stop_identifies_the_executed_call_site(self):
        self.backend.write(ENTRY, struct.pack('<5H', 0xE108, 0x7E, 0xE148, 0xEF00, 0x0060))
        self.backend.set_register(53, ENTRY)
        with self.assertRaises(BackendError) as caught:
            self.backend.run(20)
        self.assertIn('caller=0x00001008', str(caught.exception))
        self.assertIn('RETS=0x0000100a', str(caught.exception))

    def test_rom_entry_at_the_instruction_budget_is_still_a_failure(self):
        self.backend.write(ENTRY, struct.pack('<5H', 0xE108, 0x7E, 0xE148, 0xEF00, 0x0060))
        self.backend.set_register(53, ENTRY)
        with self.assertRaisesRegex(BackendError, 'on-chip ROM'):
            self.backend.run(3)


    def test_host_port_reads_words_created_by_executed_dsp_code(self):
        with BlackfinPort(WORKER, ready_address=DATA, boot_steps=100) as port:
            port.boot(stream(program()))
            for word in (0xA9, DATA & 65535, DATA >> 16, 2, 2, 0, 0):
                port.control(word)
            self.assertEqual([port.read_word(), port.read_word()], [7, 0])
            for word in (0xAB, (DATA+4) & 65535, DATA >> 16, 2, 2, 0, 0):
                port.control(word)
            port.write_word(0xBEEF)
            port.write_word(0xCAFE)
            for word in (0xA9, (DATA+4) & 65535, DATA >> 16, 2, 2, 0, 0):
                port.control(word)
            self.assertEqual([port.read_word(), port.read_word()], [0xBEEF, 0xCAFE])

    def test_boot_never_claims_ready_for_a_program_that_only_loops(self):
        with BlackfinPort(WORKER, ready_address=DATA, boot_steps=100) as port:
            port.boot(stream(b'\x00\x20'))
            self.assertTrue(port.loaded)
            self.assertFalse(port.initialized)
            with self.assertRaisesRegex(BackendError, 'initialization'):
                port.wait_ready()
            with self.assertRaises(BackendError):
                port.read_word()

    def test_short_host_transfer_invalidates_the_port(self):
        with BlackfinPort(WORKER, ready_address=DATA, boot_steps=100) as port:
            port.boot(stream(program()))
            for word in (0xAB, DATA & 65535, DATA >> 16, 2, 2, 0, 0):
                port.control(word)
            port.write_word(7)
            with self.assertRaisesRegex(BackendError, 'short'):
                port.control(0xA9)
            with self.assertRaisesRegex(BackendError, 'not loaded'):
                port.status()

    def test_boot_rejects_truncated_and_corrupt_streams(self):
        with BlackfinPort(WORKER, ready_address=DATA, boot_steps=100) as port:
            for data in (stream(program())[:-1], stream(program())[:8], b'x'*16):
                with self.subTest(length=len(data)), self.assertRaises(BackendError):
                    port.boot(data)

    def test_machine_dispatch_uses_the_executed_dsp_memory_and_rejects_snapshots(self):
        from machine import Machine, DSP_DATA, DSP_CTRL, DSP_SYNC
        with BlackfinPort(WORKER, ready_address=DATA, boot_steps=100) as port:
            machine = Machine.__new__(Machine)
            machine.dsp_backend = port
            port.boot(stream(program()))
            machine.write(DSP_CTRL, DSP_SYNC)
            for word in (0xA9, DATA & 65535, DATA >> 16, 2, 2, 0, 0):
                machine.write(DSP_CTRL, word)
            self.assertEqual([machine.read(DSP_DATA), machine.read(DSP_DATA)], [7, 0])
            with self.assertRaisesRegex(ValueError, 'Blackfin'):
                machine.snapshot()
            with self.assertRaisesRegex(ValueError, 'Blackfin'):
                machine.restore(b'not a snapshot')

    def test_machine_upload_passes_the_actual_cpu_stream_to_the_backend(self):
        from machine import Machine
        data = stream(program())
        registers = {0: 0, 1: 0xC0100000, 2: len(data), 14: 0xC0000100}
        machine = Machine.__new__(Machine)
        with BlackfinPort(WORKER, ready_address=DATA, boot_steps=100) as port:
            machine.dsp_backend = port
            machine.time_ns, machine.dsp_uploads = 0, []
            machine.A = SimpleNamespace(UC_ARM_REG_R0=0, UC_ARM_REG_R1=1, UC_ARM_REG_R2=2,
                                        UC_ARM_REG_LR=14, UC_ARM_REG_PC=15)
            def memory(address, count):
                self.assertEqual((address, count), (0xC0100000, len(data)))
                return data
            machine.uc = SimpleNamespace(reg_read=registers.__getitem__, reg_write=registers.__setitem__, mem_read=memory)
            machine._dsp_upload()
            self.assertEqual((registers[0], registers[15]), (1, registers[14]))
            self.assertTrue(port.loaded)
            self.assertTrue(port.initialized)


if __name__ == '__main__':
    unittest.main()
