# SPDX-License-Identifier: GPL-2.0-only
"""Generated Blackfin programs; no firmware or sample fixtures."""
import os
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from blackfin_backend import BlackfinBackend, BlackfinPort, BackendError

WORKER = os.environ.get('BFIN_WORKER')
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
            path.write_text("#!/usr/bin/env python3\nimport os,struct,time\nos.write(1,struct.pack('<II',0,5)+b'BFIN2')\ntime.sleep(30)\n")
            path.chmod(0o755)
            with BlackfinBackend(path, timeout=3) as backend:
                backend.timeout = .1
                with self.assertRaisesRegex(BackendError, 'deadline'):
                    backend.write(DATA, bytes(1 << 20))

    def test_a_crashed_worker_is_a_failure_and_cannot_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worker'
            path.write_text("#!/usr/bin/env python3\nimport os,struct\nos.write(1,struct.pack('<II',0,5)+b'BFIN2')\nos.read(0,12)\nos._exit(139)\n")
            path.chmod(0o755)
            with BlackfinBackend(path, timeout=3) as backend:
                with self.assertRaisesRegex(BackendError, 'exited before answering'):
                    backend.read(DATA, 4)
                self.assertIsNone(backend.process)
                with self.assertRaisesRegex(BackendError, 'closed'):
                    backend.run(20)


@unittest.skipUnless(WORKER, 'build the GNU Blackfin worker and set BFIN_WORKER')
class Execution(unittest.TestCase):
    def setUp(self):
        self.backend = BlackfinBackend(WORKER)
        self.addCleanup(self.backend.close)

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

    def test_run_stops_at_a_requested_pc(self):
        self.backend.write(ENTRY, program())
        self.backend.set_register(53, ENTRY)
        result = self.backend.run(100, until=ENTRY + 16)
        self.assertEqual(result['steps'], 5)
        self.assertTrue(result['reached'])

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
