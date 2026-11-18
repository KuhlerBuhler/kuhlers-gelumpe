"""Native WAV writer against a fault-injecting FatFs, without firmware bytes."""
import io
from pathlib import Path
import re
import struct
import sys
import unittest
import wave

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
    UNICORN = True
except ModuleNotFoundError:
    UNICORN = False


class Writer:
    def __init__(self, build='hacktribe', code=None):
        from tools.patch.recording_writer import build as assemble_writer
        self.code = code if code is not None else assemble_writer(build=build, origin=0x100000)
        self.symbols = self.code.symbols
        self.context_size = self.symbols.get('RC_SIZE', self.s('RW_SIZE'))
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.ctx, self.pcm, self.stack, self.stop = 0x200100, 0x300000, 0x400000, 0x500000
        for address, size in [(0x100000, 0x10000), (0x200000, 0x10000), (self.pcm, 0x20000), (self.stack, 0x10000), (self.stop, 0x1000)]:
            self.uc.mem_map(address, size)
        self.uc.mem_write(self.code.origin, self.code.bytes)
        self.uc.mem_write(self.ctx - 4, struct.pack('<I', 0xAABBCCDD))
        self.uc.mem_write(self.ctx + self.context_size, struct.pack('<I', 0xDDCCBBAA))
        self.files, self.handles, self.events = {}, {}, []
        self.write_fault = self.seek_fault = None
        self.mkdir_result, self.close_failures, self.write_number = 0, 0, 0
        self.targets = {self.s('REC_FS_' + name): name for name in ('OPEN', 'WRITE', 'LSEEK', 'CLOSE', 'MKDIR')}
        for page in {address & ~4095 for address in self.targets}:
            self.uc.mem_map(page, 4096)
        for address in self.targets:
            self.uc.mem_write(address, struct.pack('<I', 0xE12FFF1E))
            self.uc.hook_add(UC_HOOK_CODE, self.fat, begin=address, end=address)

    def s(self, name):
        return self.symbols[name]

    def read(self, offset):
        return struct.unpack('<I', self.uc.mem_read(self.ctx + offset, 4))[0]

    def write(self, offset, value):
        self.uc.mem_write(self.ctx + offset, struct.pack('<I', value))

    def field(self, name):
        return self.read(self.s(name))

    def call(self, name, *args):
        self.uc.reg_write(UC_ARM_REG_SP, self.stack + 0xF000)
        self.uc.reg_write(UC_ARM_REG_LR, self.stop)
        for index, value in enumerate((self.ctx, *args)):
            self.uc.reg_write(UC_ARM_REG_R0 + index, value)
        saved = tuple(0x12340000 + n for n in range(4, 12))
        for index, value in enumerate(saved, 4):
            self.uc.reg_write(UC_ARM_REG_R0 + index, value)
        self.uc.emu_start(self.s(name if name in self.symbols else 'rec_writer_' + name), self.stop, count=2000000)
        if self.uc.reg_read(UC_ARM_REG_PC) != self.stop:
            raise AssertionError(f'{name} did not return')
        assert self.uc.reg_read(UC_ARM_REG_SP) == self.stack + 0xF000
        assert tuple(self.uc.reg_read(UC_ARM_REG_R0 + n) for n in range(4, 12)) == saved
        assert bytes(self.uc.mem_read(self.ctx - 4, 4)) == bytes.fromhex('ddccbbaa')
        assert bytes(self.uc.mem_read(self.ctx + self.context_size, 4)) == bytes.fromhex('aabbccdd')
        return self.uc.reg_read(UC_ARM_REG_R0)

    def append(self, data):
        self.uc.mem_write(self.pcm, data)
        return self.call('append', self.pcm, len(data))

    def string(self, pointer):
        return bytes(self.uc.mem_read(pointer, 40)).split(b'\0', 1)[0].decode('ascii')

    def fat(self, uc, address, size, data):
        r = [uc.reg_read(UC_ARM_REG_R0 + n) for n in range(4)]
        name, result = self.targets[address], 0
        assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0, (name, 'stack alignment')
        if name == 'MKDIR':
            self.events.append((name, self.string(r[0])))
            result = self.mkdir_result
        elif name == 'OPEN':
            path = self.string(r[1])
            self.events.append((name, path, r[2]))
            assert re.fullmatch(r'SD:Recordings/REC\d{4}\.WAV', path)
            assert r[2] == 6, 'FA_WRITE | FA_CREATE_NEW'
            assert r[0] not in self.handles
            if path in self.files:
                result = 8
            else:
                self.files[path] = bytearray()
                self.handles[r[0]] = [path, 0]
                uc.mem_write(r[0], b'\xAA' * 0x240)
        elif name == 'WRITE':
            self.write_number += 1
            path, offset = self.handles[r[0]]
            count = r[2]
            if self.write_fault and self.write_fault[0] == self.write_number:
                _, result, count = self.write_fault
                count = min(count, r[2])
            self.events.append((name, offset, r[2], count))
            content = self.files[path]
            content[offset:offset + count] = bytes(uc.mem_read(r[1], count))
            self.handles[r[0]][1] += count
            uc.mem_write(r[3], struct.pack('<I', count))
        elif name == 'LSEEK':
            self.events.append((name, r[1]))
            result = self.seek_fault or 0
            if not result:
                self.handles[r[0]][1] = r[1]
        elif name == 'CLOSE':
            self.events.append((name,))
            if self.close_failures:
                self.close_failures -= 1
                result = 1
            else:
                del self.handles[r[0]]
        for reg in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12):
            uc.reg_write(reg, 0xDEAD0000)
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))


@unittest.skipUnless(UNICORN, 'Unicorn is required for native recording tests')
class RecordingWriterTests(unittest.TestCase):
    def test_stereo_wav_has_a_sector_header_exact_pcm_and_final_lengths(self):
        m = Writer()
        self.assertEqual(m.call('open', 2), 0)
        frames = bytes((i * 37) & 255 for i in range(65536))
        self.assertEqual(m.append(frames), 0)
        self.assertEqual(m.append(b'\x34\x12\xCD\xAB'), 0)
        self.assertEqual(m.call('finish'), 0)
        data = bytes(m.files['SD:Recordings/REC0001.WAV'])
        self.assertEqual(data[512:], frames + b'\x34\x12\xCD\xAB')
        self.assertEqual(struct.unpack_from('<I', data, 4)[0], len(data) - 8)
        self.assertEqual(data[12:16], b'JUNK')
        self.assertEqual(data[480:484], b'fmt ')
        self.assertEqual(data[504:508], b'data')
        with wave.open(io.BytesIO(data)) as wav:
            self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getsampwidth()), (2, 48000, 2))
            self.assertEqual(wav.readframes(wav.getnframes()), data[512:])
        self.assertEqual([e[2] for e in m.events if e[0] == 'WRITE'], [512, 65536, 4, 512])
        self.assertFalse(m.handles)

    def test_create_new_skips_existing_files_and_never_truncates_them(self):
        m = Writer()
        m.files['SD:Recordings/REC0001.WAV'] = bytearray(b'keep')
        self.assertEqual(m.call('open', 2), 0)
        self.assertEqual(m.field('RW_NUMBER'), 2)
        self.assertEqual(m.call('finish'), 0)
        self.assertEqual(m.call('open', 2), 0)
        self.assertEqual(m.field('RW_NUMBER'), 3)
        self.assertEqual(m.call('finish'), 0)
        self.assertEqual(m.files['SD:Recordings/REC0001.WAV'], b'keep')

    def test_mono_writer_for_each_firmware_profile(self):
        for build in ('hacktribe', 'stock', 'synth'):
            with self.subTest(build=build):
                m = Writer(build)
                m.mkdir_result = 8
                self.assertEqual(m.call('open', 1), 0)
                self.assertEqual(m.append(b'\x00\x80\xFF\x7F'), 0)
                self.assertEqual(m.call('finish'), 0)
                with wave.open(io.BytesIO(bytes(next(iter(m.files.values()))))) as wav:
                    self.assertEqual((wav.getnchannels(), wav.getnframes()), (1, 2))

    def test_bad_channels_and_unaligned_or_oversized_pcm_never_reach_fatfs(self):
        m = Writer()
        for channels in (0, 3, 0xFFFFFFFF):
            self.assertEqual(m.call('open', channels), m.s('RW_BAD_ARG'))
        self.assertFalse(m.events)
        self.assertEqual(m.call('open', 2), 0)
        before = list(m.events)
        for count in (1, 2, 3, 65540):
            self.assertEqual(m.call('append', m.pcm, count), m.s('RW_BAD_ARG'))
        self.assertEqual(m.call('append', 0, 0), 0)
        self.assertEqual(m.events, before)
        self.assertEqual(m.call('finish'), 0)

    def test_open_and_finish_respect_file_ownership(self):
        m = Writer()
        self.assertEqual(m.call('append', m.pcm, 4), m.s('RW_BAD_STATE'))
        self.assertEqual(m.call('finish'), m.s('RW_BAD_STATE'))
        self.assertEqual(m.call('open', 2), 0)
        before = list(m.events)
        self.assertEqual(m.call('open', 2), m.s('RW_BAD_STATE'))
        self.assertEqual(m.events, before)
        self.assertEqual(m.call('finish'), 0)

    def test_short_write_stops_appending_and_finalizes_only_complete_frames(self):
        m = Writer()
        self.assertEqual(m.call('open', 2), 0)
        m.write_fault = (2, 0, 7)
        self.assertEqual(m.append(bytes(16)), m.s('RW_FULL'))
        self.assertEqual(m.field('RW_DATA_BYTES'), 4)
        before = list(m.events)
        self.assertEqual(m.append(bytes(4)), m.s('RW_FULL'))
        self.assertEqual(m.events, before)
        self.assertEqual(m.call('finish'), m.s('RW_FULL'))
        data = next(iter(m.files.values()))
        self.assertEqual(struct.unpack_from('<I', data, 508)[0], 4)
        self.assertFalse(m.handles)

    def test_io_error_is_retained_even_when_header_rewrite_and_close_succeed(self):
        m = Writer()
        self.assertEqual(m.call('open', 2), 0)
        m.write_fault = (2, 1, 8)
        self.assertEqual(m.append(bytes(16)), m.s('RW_IO'))
        self.assertEqual(m.field('RW_FS_ERROR'), 1)
        self.assertEqual(m.call('finish'), m.s('RW_IO'))
        self.assertEqual(struct.unpack_from('<I', next(iter(m.files.values())), 508)[0], 8)
        self.assertFalse(m.handles)

    def test_header_short_write_closes_and_seek_failure_still_closes(self):
        m = Writer()
        m.write_fault = (1, 0, 16)
        self.assertEqual(m.call('open', 2), m.s('RW_FULL'))
        self.assertFalse(m.handles)
        m = Writer()
        self.assertEqual(m.call('open', 2), 0)
        m.seek_fault = 1
        self.assertEqual(m.call('finish'), m.s('RW_IO'))
        self.assertFalse(m.handles)
        self.assertEqual(m.field('RW_STATE'), 0)

    def test_close_failure_keeps_handle_owned_until_a_successful_retry(self):
        m = Writer()
        self.assertEqual(m.call('open', 2), 0)
        m.close_failures = 1
        self.assertEqual(m.call('finish'), m.s('RW_IO'))
        self.assertTrue(m.handles)
        self.assertEqual(m.call('open', 2), m.s('RW_BAD_STATE'))
        before = m.write_number
        self.assertEqual(m.call('finish'), m.s('RW_IO'))
        self.assertEqual(m.write_number, before, 'retry only closes')
        self.assertFalse(m.handles)

    def test_directory_failure_and_filename_exhaustion_do_not_create_a_file(self):
        m = Writer()
        m.mkdir_result = 5
        self.assertEqual(m.call('open', 2), m.s('RW_IO'))
        self.assertFalse(m.files)
        m = Writer()
        m.write(m.s('RW_NUMBER'), 9999)
        self.assertEqual(m.call('open', 2), m.s('RW_NO_NAME'))
        self.assertFalse(m.files)

    def test_riff_and_fat32_boundary_is_reported_before_writing(self):
        m = Writer()
        self.assertEqual(m.call('open', 2), 0)
        m.write(m.s('RW_DATA_BYTES'), m.s('RW_MAX_DATA') - 4)
        self.assertEqual(m.append(bytes(4)), 0)
        before = list(m.events)
        self.assertEqual(m.append(bytes(4)), m.s('RW_LIMIT'))
        self.assertEqual(m.events, before)
        self.assertEqual(m.field('RW_DATA_BYTES'), m.s('RW_MAX_DATA'))

    def test_capture_failure_marker_keeps_pcm_sector_aligned_and_names_its_frame(self):
        for channels, reason, label in ((1, 1, b'Capture gap'), (2, 2, b'Capture lost'), (2, 3, b'Ring overflow')):
            m = Writer()
            self.assertEqual(m.call('open', channels), 0)
            frames = bytes(range(128))
            self.assertEqual(m.append(frames), 0)
            m.write(m.s('RW_MARKER'), reason)
            self.assertEqual(m.call('finish'), 0)
            data = bytes(m.files['SD:Recordings/REC0001.WAV'])
            chunks, at = {}, 12
            while at < len(data):
                ident, size = struct.unpack_from('<4sI', data, at)
                self.assertLessEqual(at + 8 + size, len(data))
                chunks[ident] = data[at + 8:at + 8 + size]
                at += 8 + size + (size & 1)
            self.assertEqual(at, len(data))
            count = len(frames) // (channels * 2)
            self.assertEqual(struct.unpack('<III4sIII', chunks[b'cue ']), (1, 1, count, b'data', 0, 0, count))
            associated = chunks[b'LIST']
            self.assertEqual(associated[:4], b'adtl')
            ident, size, cue_id = struct.unpack_from('<4sII', associated, 4)
            self.assertEqual((ident, cue_id), (b'labl', 1))
            self.assertEqual(associated[16:12 + size].split(b'\0', 1)[0], label)
            self.assertEqual(data[512:], frames)
            with wave.open(io.BytesIO(data)) as wav:
                self.assertEqual(wav.readframes(count), frames)
            self.assertEqual(len([e for e in m.events if e[0] == 'WRITE']), 3)


if __name__ == '__main__':
    unittest.main()
