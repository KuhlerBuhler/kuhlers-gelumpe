"""Native SysEx capacity, in-place packing and command bounds on synthetic data."""
import struct
import sys
from pathlib import Path
from importlib.util import find_spec
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.patch.sysex_fixture import NativeSysex, TARGET_END, exercise, generator, payload


@unittest.skipUnless(find_spec('unicorn'), 'Unicorn not installed')
class SysexBufferTests(unittest.TestCase):
    def cache_machine(self, build='hacktribe', control=0x5107D):
        import unicorn
        machine = NativeSysex(build=build)
        b = machine.spec
        machine.uc.mem_map(b.EXEC_START + 0x4000000, 0x1000)
        events, pending = [], {}
        def store(uc, access, address, size, value, _):
            if control & 5 != 5:
                uc.mem_write(address + 0x4000000, (value & ((1 << (size*8))-1)).to_bytes(size, 'little'))
        def cache(uc, address, size, _):
            word = struct.unpack('<I', uc.mem_read(address, 4))[0]
            if word == 0xEE110F10:
                uc.reg_write(machine.a.UC_ARM_REG_R0, control)
                uc.reg_write(machine.a.UC_ARM_REG_PC, address + 4)
            elif word == 0xEE070F3A:
                line = uc.reg_read(machine.a.UC_ARM_REG_R0)
                self.assertTrue(b.EXEC_START <= line < b.EXEC_END and line & 31 == 0)
                pending[line] = bytes(uc.mem_read(line, 32))
                events.append(('clean', line))
                uc.reg_write(machine.a.UC_ARM_REG_PC, address + 4)
            elif word == 0xEE070F9A:
                for line, data in pending.items():
                    uc.mem_write(line + 0x4000000, data)
                pending.clear()
                events.append(('drain', 0))
                uc.reg_write(machine.a.UC_ARM_REG_PC, address + 4)
            elif word & 0x0F100010 == 0x0E000010 and (word >> 8) & 15 == 15:
                self.fail('WRITE DATA must not change CP15 configuration')
        machine.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, store, begin=b.EXEC_START, end=b.EXEC_END-1)
        for start, end in ((b.CODE_AT, b.CODE_END), (b.SAMPLE_AT, b.SAMPLE_END)):
            machine.uc.hook_add(unicorn.UC_HOOK_CODE, cache, begin=start, end=end-1)
        return machine, events, pending

    def test_exec_uploads_are_published_before_the_write_ack(self):
        for build in ('hacktribe', 'stock'):
            m, events, pending = self.cache_machine(build)
            b = m.spec
            for offset, count in ((0, 1024), (5, 64), (1023, 1), (1, 31)):
                with self.subTest(build=build, offset=offset, count=count):
                    initial = payload(1024)
                    m.uc.mem_write(b.EXEC_START, initial)
                    m.uc.mem_write(b.EXEC_START + 0x4000000, initial)
                    events.clear()
                    data, start = b'E' * count, b.EXEC_START + offset
                    self.assertEqual(struct.unpack_from('<I', m.words(b.FUNC_BEGIN, start, count, zlib.crc32(data)))[0], b.STATUS_OK)
                    self.assertEqual(struct.unpack('<4I', m.request(b.FUNC_DATA, data)), (b.STATUS_OK, start, count, zlib.crc32(data)))
                    self.assertEqual(bytes(m.uc.mem_read(start + 0x4000000, count)), data,
                                     'WRITE ACK must include physical publication of EXEC bytes')
                    self.assertEqual(events, [('clean', address) for address in range(start & ~31, start + count, 32)] + [('drain', 0)])
                    self.assertEqual(pending, {})
            m.check_guards()

    def test_exec_publication_excludes_other_ram_files_and_rejected_writes(self):
        m, events, pending = self.cache_machine()
        b, data = m.spec, b'own generated data'
        for start in (0xC3000000,):
            m.words(b.FUNC_BEGIN, start, len(data), zlib.crc32(data))
            self.assertEqual(struct.unpack_from('<I', m.request(b.FUNC_DATA, data))[0], b.STATUS_OK)
            self.assertEqual(events, [])
        m.words(b.FUNC_FBEGIN, 0, len(data), zlib.crc32(data))
        self.assertEqual(struct.unpack_from('<I', m.request(b.FUNC_DATA, data))[0], b.STATUS_OK)
        self.assertEqual(events, [])
        m.words(b.FUNC_BEGIN, b.EXEC_START, len(data), zlib.crc32(data) ^ 1)
        self.assertEqual(struct.unpack_from('<I', m.request(b.FUNC_DATA, data))[0], b.STATUS_BAD_CRC)
        self.assertEqual(events, [])
        for start, length in ((b.EXEC_START - 1, 2), (b.EXEC_END, 1)):
            self.assertEqual(struct.unpack_from('<I', m.words(b.FUNC_BEGIN, start, length, 0))[0], b.STATUS_REFUSED)
        self.assertEqual(events, [])
        self.assertEqual(pending, {})
        synth, synth_events, _ = self.cache_machine('synth')
        self.assertEqual(struct.unpack_from('<I', synth.words(synth.spec.FUNC_BEGIN, b.EXEC_START, 32, 0))[0], b.STATUS_REFUSED)
        self.assertEqual(synth_events, [])

    def test_disabled_cache_skips_cleaning_old_lines_and_drains_exec_writes(self):
        for control in (0, 1, 4):
            m, events, pending = self.cache_machine(control=control)
            b, data = m.spec, b'own code bytes'
            m.words(b.FUNC_BEGIN, b.EXEC_START + 3, len(data), zlib.crc32(data))
            self.assertEqual(struct.unpack_from('<I', m.request(b.FUNC_DATA, data))[0], b.STATUS_OK)
            self.assertEqual(events, [('drain', 0)])
            self.assertEqual(pending, {})
    def test_current_protocol_matrix_on_both_native_ports(self):
        machine = NativeSysex()
        result = exercise(machine)
        self.assertGreater(result['cases'], 400)
        self.assertEqual(machine.spec.MAX_BLOCK, 32768)
        self.assertFalse(machine.locked)

    def test_released_area_is_untouched_by_maximum_file_reply(self):
        machine = NativeSysex(freed_start=TARGET_END)
        b = machine.spec
        data = payload(b.MAX_BLOCK)
        machine.files[machine.folder + 'System/SYSTEM.VSB'] = bytearray(data)
        reply = machine.words(b.FUNC_FREAD, 0, len(data))
        self.assertEqual(reply[20:], data)
        machine.check_guards()

    def test_capacity_covers_every_length_header_and_alignment(self):
        b = generator()
        self.assertEqual(b.MAX_BLOCK, 32768)
        self.assertEqual(b.BUF_END, TARGET_END)
        self.assertGreaterEqual(b.FILE_AREA - b.BUF_END, 19456)
        self.assertEqual(b.BUF_END & 255, 0)
        for header in (16, 20):
            for length in range(b.MAX_BLOCK + 1):
                raw = header + length
                groups = (raw + 6) // 7
                start = ((b.BUFFER_REQUIRED - length) & ~3) - header
                self.assertGreaterEqual(start, 7 + groups)
                self.assertLessEqual(8 + raw + groups, b.BUFFER_REQUIRED)
        with patch.object(b, 'BUF_END', b.BUF + b.BUFFER_REQUIRED - 1):
            with self.assertRaisesRegex(SystemExit, 'buffer is too small'):
                b.build_patch(b'', b'', 'hacktribe')

    def test_crc_pending_and_range_errors_do_not_escape_the_buffer(self):
        m = NativeSysex()
        b = m.spec
        self.assertIsNone(m.request(b.FUNC_DATA, b'x'))
        data = payload(b.MAX_BLOCK)
        m.words(b.FUNC_BEGIN, 0xc3000000, len(data), zlib.crc32(data) ^ 1)
        self.assertEqual(struct.unpack_from('<I', m.request(b.FUNC_DATA, data))[0], b.STATUS_BAD_CRC)
        self.assertIsNone(m.request(b.FUNC_DATA, data))
        m.words(b.FUNC_BEGIN, 0xc3000000, 1, zlib.crc32(b'x'))
        failed = m.words(b.FUNC_BEGIN, b.BUF, 1, zlib.crc32(b'x'))
        self.assertEqual(struct.unpack_from('<I', failed)[0], b.STATUS_REFUSED)
        self.assertIsNone(m.request(b.FUNC_DATA, b'x'))
        for function in (b.FUNC_READ, b.FUNC_FLASH, b.FUNC_FREAD):
            # bits 31 and 30 of a FILE offset select the sample file's temp file, whose limit is 256 MiB: 0xf8000000 is past it
            for address, length in ((0xfffffff0, 32), (0xf8000000 if function == b.FUNC_FREAD else 0xc8000000, 1)):
                reply = m.words(function, address, length)
                self.assertEqual(struct.unpack_from('<I', reply)[0], b.STATUS_RANGE)
        m.check_guards()

    def test_file_eof_short_io_failures_and_names(self):
        m = NativeSysex()
        b = m.spec
        path = m.folder + 'System/SYSTEM.VSB'
        m.files[path] = bytearray(b'abc')
        for offset, length, expected in ((1, b.MAX_BLOCK, b'bc'), (3, 1, b''), (4, 0, b'')):
            reply = m.words(b.FUNC_FREAD, offset, length)
            self.assertEqual(struct.unpack_from('<5I', reply), (0, offset, len(expected), zlib.crc32(expected), 3))
            self.assertEqual(reply[20:], expected)
        m.short_read = 1
        self.assertEqual(m.words(b.FUNC_FREAD, 0, 3)[20:], b'a')
        m.short_read = None
        data = payload(32)
        for failed in ('FS_OPEN', 'FS_LSEEK', 'FS_READ', 'FS_CLOSE'):
            m.failures = {failed: 1}
            reply = m.words(b.FUNC_FREAD, 0, 1)
            self.assertEqual(struct.unpack_from('<I', reply)[0], b.STATUS_FILE, failed)
        m.failures = {}
        for failed in ('FS_OPEN', 'FS_LSEEK', 'FS_WRITE', 'FS_READ', 'FS_CLOSE'):
            m.words(b.FUNC_FBEGIN, 0, len(data), zlib.crc32(data))
            m.failures = {failed: 1}
            reply = m.request(b.FUNC_DATA, data)
            self.assertEqual(struct.unpack_from('<I', reply)[0], b.STATUS_FILE, failed)
            m.failures = {}
        m.words(b.FUNC_FBEGIN, 0, len(data), zlib.crc32(data))
        m.short_write = 1
        self.assertEqual(struct.unpack_from('<I', m.request(b.FUNC_DATA, data))[0], b.STATUS_FILE)
        m.short_write = None
        m.words(b.FUNC_FBEGIN, 0, len(data), zlib.crc32(data))
        m.corrupt_read = True
        self.assertEqual(struct.unpack_from('<I', m.request(b.FUNC_DATA, data))[0], b.STATUS_VERIFY)
        m.corrupt_read = False
        for name in (b'', b'../x', b'a/b', b'a.b', b'a\x00b', b'\xff'):
            reply = m.request(b.FUNC_PBEGIN, struct.pack('<III', 0, 1, 0) + name.ljust(16, b'\0'))
            self.assertEqual(struct.unpack_from('<I', reply)[0], b.STATUS_RANGE)
        for offset, length, expected in ((b.FILE_LIMIT - 1, 1, 0), (b.FILE_LIMIT, 1, b.STATUS_RANGE), (b.FILE_LIMIT - 1, 2, b.STATUS_RANGE)):
            reply = m.words(b.FUNC_FBEGIN, offset, length, 0)
            self.assertEqual(struct.unpack_from('<I', reply)[0], expected)
        m.check_guards()

    def test_flash_fault_exit_and_original_dispatch(self):
        m = NativeSysex()
        b = m.spec
        m.failures = {'FLASH_READ': 1}
        self.assertEqual(struct.unpack_from('<I', m.words(b.FUNC_FLASH, 0, b.FLASH_MAX))[0], b.STATUS_FLASH)
        for function in (0, 0x1c, 0x68, 0x7f):
            self.assertEqual(m.call('classify_hook', m.message, function), 0x7777)
            m.uc.mem_write(m.message, bytes([function]))
            m.call('process_hook', m.message)
        self.assertEqual(len(m.fallback), 8)
        for function in range(0x52, 0x58):      # Hacktribe's commands are dropped in both hooks
            self.assertEqual(m.call('classify_hook', m.message, function), 0)
            m.uc.mem_write(m.message, bytes([function]))
            m.call('process_hook', m.message)
        self.assertEqual(len(m.fallback), 8)
        m.write_word(m.panel + 0x18, b.KILL_SWITCH)
        for function in range(0x52, 0x58):      # with EXIT held at power-on they go on, all but the flash write
            expected = 0 if function == 0x56 else 0x7777
            self.assertEqual(m.call('classify_hook', m.message, function), expected)
            m.uc.mem_write(m.message, bytes([function]))
            m.call('process_hook', m.message)
        self.assertEqual(len(m.fallback), 18)
        for function, request in ((b.FUNC_INFO, b''), (b.FUNC_READ, struct.pack('<II', 0xc3000000, 1)), (b.FUNC_FREAD, bytes(8))):
            self.assertIsNone(m.request(function, request))
        m.check_guards()

    def test_folder_prefix_stays_within_the_file_workspace(self):
        m = NativeSysex()
        b = m.spec
        for count in (0, 62, 63, 64):
            prefix = 'x' * count
            m.uc.mem_write(m.folder_at, prefix.encode() + b'\0')
            path = prefix[:63] + 'System/SYSTEM.VSB'
            m.files[path] = bytearray(b'x')
            reply = m.words(b.FUNC_FREAD, 0, 1)
            self.assertEqual(struct.unpack_from('<I', reply)[0], b.STATUS_OK)
            self.assertEqual(reply[20:], b'x')
            m.check_guards()


if __name__ == '__main__':
    unittest.main()
