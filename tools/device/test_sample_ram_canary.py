"""Synthetic ARM tests for the upper-only RAM canary, with no device or firmware."""
import struct
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import unicorn
from unicorn import arm_const as R
import sample_ram_canary as p


class Canary(unittest.TestCase):
    def machine(self, operation, control=0):
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        uc.mem_map(0xC0000000, 0x800000)
        uc.mem_map(p.STUB, 0x10000)
        uc.mem_write(p.SCREENS, struct.pack('<I', 0xC06B0000))
        uc.mem_write(0xC06B0000 + 0x2C, struct.pack('<I', 1))
        uc.mem_write(p.TRANSPORT, struct.pack('<I', 0xC06B1000))
        uc.mem_map(p.START - 4096, 4 * 4096)
        trap = p.STUB + 0xF000
        uc.mem_write(p.START - 4096, b'K' * 4096)
        uc.mem_write(p.START + 8192, b'E' * 4096)
        code, symbols = p.build(operation, p.START, p.START + 8192, 77)
        uc.mem_write(p.STUB, code)

        def cp15(machine, address, size, data):
            machine.reg_write(R.UC_ARM_REG_R6, control)
            machine.reg_write(R.UC_ARM_REG_PC, address + 4)

        uc.hook_add(unicorn.UC_HOOK_CODE, cp15, begin=symbols['read_control'], end=symbols['read_control'])
        def run(token=77):
            uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
            uc.reg_write(R.UC_ARM_REG_SP, p.STUB + 0xE000)
            uc.reg_write(R.UC_ARM_REG_R0, token)
            uc.reg_write(R.UC_ARM_REG_LR, trap)
            uc.emu_start(p.STUB, trap, count=100000)
            self.assertEqual(uc.reg_read(R.UC_ARM_REG_PC), trap)
            self.assertEqual(uc.reg_read(R.UC_ARM_REG_SP), p.STUB + 0xE000)
            return tuple(struct.unpack('<8I', uc.mem_read(p.RESULT, 32)))
        return uc, run

    def test_fill_excludes_both_stacks_and_preserves_registers(self):
        uc, run = self.machine('fill')
        expected = {R.UC_ARM_REG_R0 + i: 0xA000 + i for i in range(4, 13)}
        for register, value in expected.items():
            uc.reg_write(register, value)
        result = run()
        self.assertEqual(result[:3], (p.MAGIC, 77, 0))
        self.assertEqual(uc.reg_read(R.UC_ARM_REG_R0), p.MAGIC)
        for address in range(p.START, p.START + 8192, 4):
            self.assertEqual(struct.unpack('<I', uc.mem_read(address, 4))[0], address ^ p.KEY)
        for register, value in expected.items():
            self.assertEqual(uc.reg_read(register), value)
        self.assertEqual(bytes(uc.mem_read(p.START - 4096, 4096)), b'K' * 4096)
        self.assertEqual(bytes(uc.mem_read(p.START + 8192, 4096)), b'E' * 4096)

    def test_cpu_info_reads_registers_with_cache_enabled_without_upper_ram_access(self):
        try:
            uc, run = self.machine('info', control=0x5107D)
        except ValueError as error:
            self.fail(f'CPU register capture must support active caches: {error}')
        preserved = {R.UC_ARM_REG_R0 + index: 0xAA00 + index for index in range(4, 13)}
        for register, value in preserved.items():
            uc.reg_write(register, value)
        values = {0xEE126F10: 0xC200003F, 0xEE136F10: 0xFFFFFFFF,
                  0xEE1D6F10: 0x02000000, 0xEE106F10: 0x41069265,
                  0xEE106F30: 0x1D112152, 0xEE196F11: 0x0000000A, 0xEE196F31: 0x0001000C}
        seen = []
        def registers(machine, address, size, _):
            word = struct.unpack('<I', machine.mem_read(address, 4))[0]
            if word in values:
                seen.append(word)
                machine.reg_write(R.UC_ARM_REG_R6, values[word])
                machine.reg_write(R.UC_ARM_REG_PC, address + 4)
        touched = []
        uc.hook_add(unicorn.UC_HOOK_CODE, registers, begin=p.STUB, end=p.RESULT - 4)
        uc.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE,
                    lambda machine, access, address, size, value, _: touched.append(address),
                    begin=p.START, end=p.START + 8191)
        result = run()
        self.assertEqual(result, (p.MAGIC, 77, 0, 0x5107D, 0xC200003F,
                                  0xFFFFFFFF, 0x02000000, 0x41069265))
        self.assertEqual(struct.unpack('<3I', uc.mem_read(p.MAP, 12)),
                         (0x1D112152, 0xA, 0x1000C))
        self.assertEqual(set(seen), set(values))
        self.assertEqual(touched, [])
        for register, value in preserved.items():
            self.assertEqual(uc.reg_read(register), value)
        code, symbols = p.build('info', nonce=77)
        for offset in range(0, symbols['invalid'] + 8 - p.STUB, 4):
            word = struct.unpack_from('<I', code, offset)[0]
            self.assertFalse(word & 0x0F100010 == 0x0E000010 and (word >> 8) & 15 == 15,
                             'the diagnostic must not contain MCR')

    def test_cpu_info_refuses_a_modal_context_or_an_unknown_cpu(self):
        for status in (2, 3):
            uc, run = self.machine('info', control=0x5107D)
            if status == 2:
                uc.mem_write(0xC06B0000 + 0x24, struct.pack('<I', 1))
            def identity(machine, address, size, _):
                if struct.unpack('<I', machine.mem_read(address, 4))[0] == 0xEE106F10:
                    machine.reg_write(R.UC_ARM_REG_R6, 0x410FC090)
                    machine.reg_write(R.UC_ARM_REG_PC, address + 4)
            uc.hook_add(unicorn.UC_HOOK_CODE, identity, begin=p.STUB, end=p.RESULT - 4)
            result = run()
            self.assertEqual(result[2], status)
            self.assertEqual(result[4:7], (0, 0, 0))

    def test_cpu_info_restores_scratch_and_decodes_auxiliary_registers(self):
        class Link:
            def __init__(self):
                self.writes = []
            def read(self, address, size):
                return struct.pack('<3I', 0x1D112152, 0xA, 0x1000C) if (address, size) == (p.MAP, 12) else bytes(size)
            def write_at(self, address, data):
                self.writes.append((address, len(data)))
        link, rows = Link(), []
        with patch.object(p, 'preflight'), patch.object(p, 'quiescent'), \
             patch.object(p, 'invoke', return_value=(p.MAGIC, 77, 0, 0x5107D,
                                                     0xC200003F, 0xFFFFFFFF, 0x02000000, 0x41069265)):
            try:
                p.measure(link, b'', 'info', rows.append)
            except ValueError as error:
                self.fail(f'CPU registers must not be interpreted as canary addresses: {error}')
        self.assertEqual(rows, [dict(operation='info', control=0x5107D, ttbr=0xC200003F,
                                     domain_control=0xFFFFFFFF, fcse=0x02000000, cpu_id=0x41069265,
                                     cache_type=0x1D112152, dtcm_region=0xA, itcm_region=0x1000C)])
        self.assertEqual(link.writes, [(p.STUB, 0x300), (p.RESULT, 32), (p.MAP, 224)])

    def test_table_capture_reads_only_the_current_sram_table(self):
        for actual_base, status in ((0x8001C03F, 0), (0x80018000, 4)):
            uc, run = self.machine('fill', control=0x5107D)
            uc.mem_map(0x80000000, 0x20000)
            data = bytes(range(224))
            uc.mem_write(0x8001C000, data)
            try:
                code, symbols = p.build('table', 0x8001C000, 0x8001C0E0, 77)
            except ValueError as error:
                self.fail(f'bounded SRAM table capture is required: {error}')
            uc.mem_write(p.STUB, code)
            def ttbr(machine, address, size, _):
                if struct.unpack('<I', machine.mem_read(address, 4))[0] == 0xEE126F10:
                    machine.reg_write(R.UC_ARM_REG_R6, actual_base)
                    machine.reg_write(R.UC_ARM_REG_PC, address + 4)
            touched = []
            uc.hook_add(unicorn.UC_HOOK_CODE, ttbr, begin=p.STUB, end=p.RESULT - 4)
            uc.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE,
                        lambda machine, access, address, size, value, _: touched.append(address),
                        begin=p.START, end=p.START + 8191)
            uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,
                        lambda machine, access, address, size, value, _: touched.append(address),
                        begin=0x80000000, end=0x8001FFFF)
            result = run()
            self.assertEqual(result[2], status)
            self.assertEqual(bytes(uc.mem_read(p.MAP, 224)), data if status == 0 else bytes(224))
            self.assertEqual(touched, [])
            if status == 0:
                self.assertEqual(result[4:], (0x8001C000, 0x8001C0E0, 224, 0x8001C000))
            for offset in range(0, symbols['invalid'] + 8 - p.STUB, 4):
                word = struct.unpack_from('<I', code, offset)[0]
                self.assertFalse(word & 0x0F100010 == 0x0E000010 and (word >> 8) & 15 == 15)

    def test_sram_table_capture_rejects_unbounded_or_cross_table_requests(self):
        for start, end in ((0xC274F000, 0xC274F004), (0x80020000, 0x80020004),
                           (0x8001C000, 0x8001C0E4), (0x8001C001, 0x8001C005),
                           (0x8001BFFC, 0x8001C004), (0x8001C000, 0x8001C000)):
            with self.subTest(start=hex(start)), self.assertRaisesRegex(ValueError, 'SRAM table'):
                p.build('table', start, end, 77)

    def test_sram_table_streams_inside_the_same_scratch_window(self):
        class Link:
            def __init__(self):
                self.writes = []
            def read(self, address, size):
                return bytes(size)
            def write_at(self, address, data):
                self.writes.append((address, len(data)))
        def invoke(link, operation, start, end, nonce):
            return p.MAGIC, nonce, 0, 0x5107D, start, end, end-start, 0x8001C000
        link, rows = Link(), []
        with patch.object(p, 'preflight'), patch.object(p, 'quiescent'), patch.object(p, 'invoke', invoke):
            try:
                p.measure(link, b'', 'table', rows.append, span=(0x8001C000, 0x80020000))
            except TypeError as error:
                self.fail(f'an explicit bounded table span is required: {error}')
        self.assertEqual(len(rows), 74)
        self.assertEqual(sum(len(row['data']) for row in rows), 0x4000)
        self.assertEqual(len(rows[-1]['data']), 32)
        self.assertEqual(link.writes, [(p.STUB, 0x300), (p.RESULT, 32), (p.MAP, 224)])

    def test_late_unconfirmed_table_exec_suppresses_cleanup_after_successful_parts(self):
        class Link:
            def __init__(self):
                self.writes = []
            def read(self, address, size):
                return bytes(size)
            def write_at(self, address, data):
                self.writes.append(address)
        link, rows, restored, calls = Link(), [], [], []
        def invoke(link, operation, start, end, nonce):
            calls.append(start)
            if len(calls) == 9:
                raise RuntimeError('EXEC marker unconfirmed')
            return p.MAGIC, nonce, 0, 0x5107D, start, end, end-start, 0x8001C000
        with patch.object(p, 'preflight'), patch.object(p, 'quiescent'), patch.object(p, 'invoke', invoke), \
             self.assertRaisesRegex(RuntimeError, 'unconfirmed'):
            p.measure(link, b'', 'table', rows.append, lambda: restored.append(True), span=(0x8001C000, 0x80020000))
        self.assertEqual(len(rows), 8)
        self.assertEqual(link.writes, [])
        self.assertEqual(restored, [])

    def test_check_detects_changed_words_and_saturates_the_block_count(self):
        uc, run = self.machine('check')
        uc.mem_write(p.START, b''.join(struct.pack('<I', address ^ p.KEY)
                                     for address in range(p.START, p.START + 8192, 4)))
        self.assertEqual(run()[6], 0)
        uc.mem_write(p.START + 4, b'BAD!')
        uc.mem_write(p.START + 4096, b'B' * 4096)
        self.assertEqual(run()[6], 2)
        self.assertEqual(bytes(uc.mem_read(p.MAP, 2)), bytes([1, 255]))

    def test_cache_mmu_and_wrong_nonce_refuse_before_the_first_range_write(self):
        for control in (1, 4, 5):
            uc, run = self.machine('fill', control)
            self.assertEqual(run()[2], 1)
            self.assertEqual(bytes(uc.mem_read(p.START, 8192)), bytes(8192))
        uc, run = self.machine('fill')
        self.assertEqual(run(78), (0,) * 8)
        self.assertEqual(bytes(uc.mem_read(p.START, 8192)), bytes(8192))

    def test_a_running_or_modal_context_cannot_touch_the_upper_range(self):
        for address, value in ((0xC06B0000 + 0x2C, 41), (0xC06B0000 + 0x24, 42),
                               (0xC06B1000 + 0x308, 1), (p.SCREENS, 0xFFFFFFFF), (p.TRANSPORT, 0)):
            with self.subTest(address=address):
                uc, run = self.machine('fill')
                uc.mem_write(address, struct.pack('<I', value))
                self.assertEqual(run()[2], 2)
                self.assertEqual(bytes(uc.mem_read(p.START, 8192)), bytes(8192))

    def test_the_map_fits_the_existing_first_kib_write_exception(self):
        self.assertEqual(p.MAP, p.STUB + 0x320)

    def test_a_large_check_streams_maps_inside_the_approved_scratch_window(self):
        class Link:
            def __init__(self):
                self.writes = []
            def read(self, address, size):
                return bytes(size)
            def write_at(self, address, data):
                self.writes.append((address, len(data)))
        spans = []
        def invoke(link, operation, start, end, nonce):
            spans.append((start, end))
            return (p.MAGIC, nonce, 0, 0, start, end, 0, (end-start)//4096)
        link = Link()
        rows = []
        with patch.object(p, 'preflight'), patch.object(p, 'quiescent'), patch.object(p, 'invoke', invoke), \
             patch.object(p, 'END', p.START + 225 * 4096):
            p.measure(link, b'', 'check', rows.append)
        self.assertEqual(spans, [(p.START, p.START + 224*4096), (p.START + 224*4096, p.START + 225*4096)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(link.writes, [(p.STUB, 0x300), (p.RESULT, 32), (p.MAP, 224)])
        self.assertTrue(all(p.STUB <= address < address + size <= p.STUB + 1024 for address, size in link.writes))

    def test_a_check_cannot_overrun_its_bounded_map(self):
        with self.assertRaisesRegex(ValueError, 'scratch'):
            p.build('check', p.START, p.START + 225 * 4096, 77)

    def test_a_confirmed_refusal_records_control_before_restoring_scratch(self):
        class Link:
            def __init__(self):
                self.writes = []
            def read(self, address, size):
                return bytes(size)
            def write_at(self, address, data):
                self.writes.append((address, len(data)))
        link, rows = Link(), []
        with patch.object(p, 'preflight'), patch.object(p, 'quiescent'), \
             patch.object(p, 'invoke', return_value=(p.MAGIC, 77, 1, 0x5107D, 0, 0, 0, 0)):
            with self.assertRaisesRegex(ValueError, 'refused'):
                p.measure(link, b'', 'check', rows.append)
        self.assertEqual(rows, [dict(operation='check', status=1, control=0x5107D,
                                     refused=True, start=p.START, end=p.START + p.MAP_BYTES * 4096)])
        self.assertEqual(link.writes, [(p.STUB, 0x300), (p.RESULT, 32), (p.MAP, 224)])

    def test_a_refusal_report_confirms_successful_scratch_restoration(self):
        import blue_report
        class Link:
            def read(self, address, size):
                return bytes(size)
            def write_at(self, address, data):
                pass
        with tempfile.TemporaryDirectory(prefix='ram-probe-refusal-') as directory:
            original, output = Path(directory) / 'original.bin', Path(directory) / 'report.json'
            original.write_bytes(b'own synthetic image')
            with patch.object(p, 'preflight'), patch.object(p, 'quiescent'), \
                 patch.object(p, 'invoke', return_value=(p.MAGIC, 77, 1, 0x5107D, 0, 0, 0, 0)), \
                 patch.object(p, 'Link', return_value=Link()), \
                 patch.object(blue_report, 'midi_ask', return_value=(None, None)), \
                 patch.object(blue_report, 'search', return_value=dict(model=0x24, version='2.02', channel=0)):
                result = p.main(['--execute', '--operation', 'check', '--ram-overwrite-confirmed',
                                 '--port-idle-confirmed', '--stopped-main-confirmed', '--vsb', str(original),
                                 '--json', str(output)])
            report = json.loads(output.read_text())
        self.assertEqual(result, 1)
        self.assertIn('refused', report['error'])
        self.assertTrue(report['scratch_restored'])

    def test_ranges_cannot_include_the_work_buffer_or_task_stack(self):
        for start, end in ((p.START - 4096, p.END), (p.START + 2, p.END),
                           (p.START, p.END + 4096), (p.START, p.START)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                p.build('fill', start, end, 77)

    def test_observer_does_not_restore_scratch_when_exec_is_unconfirmed(self):
        class Link:
            def __init__(self):
                self.writes = []
            def read(self, address, size):
                return bytes(size)
            def write_at(self, address, data):
                self.writes.append(address)
        link = Link()
        with patch.object(p, 'preflight'), patch.object(p, 'quiescent'), patch.object(p, 'invoke', side_effect=RuntimeError('unconfirmed')):
            with self.assertRaisesRegex(RuntimeError, 'unconfirmed'):
                p.measure(link, b'', 'fill', lambda row: None)
        self.assertEqual(link.writes, [])

    def test_an_installed_swap_refuses_before_any_scratch_upload(self):
        class Link:
            def info(self):
                pass
            def read(self, address, size):
                return bytes([1]) * size
        with patch.object(p.sample_swap_io, 'validate_firmware', return_value='stock'):
            with self.assertRaisesRegex(ValueError, 'sample-swap is installed'):
                p.preflight(Link(), bytes(0x40000))

    def test_extra_firmware_code_or_a_different_variant_refuses_before_upload(self):
        image = bytes(0x200100)
        for changed in (0xC017CC00, 0xC0150300, 0xC014FCF0, 0xC004FAF8):
            class Link:
                def info(self):
                    pass
                def read(self, address, size):
                    offset = address - 0xC0000000 + 0x100
                    data = bytearray(image[offset:offset + size])
                    if address <= changed < address + size:
                        data[changed - address] = 1
                    return bytes(data)
                def write_at(self, address, data):
                    raise AssertionError('preflight must not write RAM')
                def execute(self, token):
                    raise AssertionError('preflight must not execute code')
            with self.subTest(changed=hex(changed)), \
                 patch.object(p.sample_swap_io, 'validate_firmware', return_value='hacktribe'), \
                 patch.object(p, 'quiescent'), \
                 patch.object(p, 'invoke', side_effect=AssertionError('preflight must not upload a probe')), \
                 self.assertRaisesRegex(ValueError, 'baseline differs'):
                p.measure(Link(), image, 'fill', lambda row: None)

    def test_matching_minimal_baseline_passes_the_read_only_preflight(self):
        image = bytes(0x200100)
        class Link:
            def info(self):
                pass
            def read(self, address, size):
                offset = address - 0xC0000000 + 0x100
                return image[offset:offset + size]
        with patch.object(p.sample_swap_io, 'validate_firmware', return_value='hacktribe'):
            p.preflight(Link(), image)

    def test_uncertain_exec_stops_without_restoring_ram_or_retrying(self):
        class Link:
            def __init__(self):
                self.commands = []
                self.uploads = {}
            def write_at(self, address, data):
                self.commands.append(('write', address))
                self.uploads[address] = data
            def read(self, address, size):
                return self.uploads[address - 0x4000000][:size]
            def execute(self, token):
                self.commands.append(('exec', token))
                raise TimeoutError('silent')
        link = Link()
        with patch.object(p, 'quiescent'), self.assertRaisesRegex(RuntimeError, 'unconfirmed'):
            p.invoke(link, 'fill', p.START, p.START + 4096, 77)
        self.assertEqual(link.commands[-1], ('exec', 77))

    def test_code_not_visible_in_uncached_ram_prevents_exec(self):
        class Link:
            def __init__(self):
                self.executed = False
            def write_at(self, address, data):
                pass
            def read(self, address, size):
                if address == p.RESULT:
                    return struct.pack('<8I', p.MAGIC, 77, 0, 0, p.START, p.END, 0, (p.END-p.START)//4096)
                return bytes(size)
            def execute(self, token):
                self.executed = True
        link = Link()
        with patch.object(p, 'quiescent'), self.assertRaisesRegex(ValueError, 'uncached.*EXEC not sent'):
            p.invoke(link, 'fill', p.START, p.END, 77)
        self.assertFalse(link.executed)


if __name__ == '__main__':
    unittest.main()
