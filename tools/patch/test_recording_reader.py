"""Native capture ownership, stereo conversion and ring deadlines with own PCM."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.patch.test_recording_writer import UNICORN
if UNICORN:
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC


class Reader:
    def __init__(self):
        from tools.patch.recording_reader import build
        self.code = build(origin=0x100000)
        self.symbols = self.code.symbols
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.ctx, self.ring, self.stack, self.stop = 0x200100, 0x300000, 0x400000, 0x500000
        for address, size in [(0x100000, 0x10000), (0x200000, 0x10000), (self.ring, 0x20000), (self.stack, 0x10000), (self.stop, 0x1000)]:
            self.uc.mem_map(address, size)
        self.uc.mem_write(self.code.origin, self.code.bytes)
        targets = {self.s('RR_FW_' + name): name for name in ('READ', 'WRITE_RAW', 'GET', 'LOCK', 'UNLOCK', 'BEGIN', 'END')}
        for page in {a & ~4095 for a in targets} | {self.s('RR_TICKS') & ~4095}:
            self.uc.mem_map(page, 4096)
        self.targets, self.memory, self.events, self.after_read = targets, {}, [], None
        self.put(self.s('RR_MAGIC_ADDRESS'), struct.pack('<I', self.s('RR_MAGIC')))
        self.info(1, self.s('RR_DSP_BYTES'))
        self.info(2, self.s('RR_DSP_RING'))
        self.info(3, self.s('RR_INPUT'))
        self.initial_frames = []
        self.lock_depth = 0
        self.end_failures = 0
        for address in targets:
            self.uc.mem_write(address, struct.pack('<I', 0xE12FFF1E))
            self.uc.hook_add(UC_HOOK_CODE, self.firmware, begin=address, end=address)

    def s(self, name):
        return self.symbols[name]

    def field(self, name, value=None):
        address = self.ctx + self.s(name)
        if value is not None:
            self.uc.mem_write(address, struct.pack('<I', value & 0xFFFFFFFF))
        return struct.unpack('<I', self.uc.mem_read(address, 4))[0]

    def put(self, address, data):
        self.memory.update((address + index, byte) for index, byte in enumerate(data))

    def get(self, address, length):
        return bytes(self.memory.get(address + i, 0) for i in range(length))

    def info(self, index, value=None):
        address = self.s('RR_DSP_STATE') + index * 4
        if value is not None:
            self.put(address, struct.pack('<I', value))
        return struct.unpack('<I', self.get(address, 4))[0]

    def tick(self, value=None):
        address = self.s('RR_TICKS')
        if value is not None:
            self.uc.mem_write(address, struct.pack('<I', value & 0xFFFFFFFF))
        return struct.unpack('<I', self.uc.mem_read(address, 4))[0]

    def capture(self, words, elapsed=10):
        pointer = self.info(2)
        base, size = self.s('RR_DSP_RING'), self.s('RR_DSP_BYTES')
        for word in words:
            self.put(pointer, struct.pack('<I', word))
            pointer = base + (pointer - base + 4) % size
        self.info(2, pointer)
        self.tick(self.tick() + elapsed)

    def call(self, name, *args):
        self.uc.reg_write(UC_ARM_REG_SP, self.stack + 0xF000)
        self.uc.reg_write(UC_ARM_REG_LR, self.stop)
        saved = tuple(0x12340000 + n for n in range(4, 12))
        for n, value in enumerate(saved, 4):
            self.uc.reg_write(UC_ARM_REG_R0 + n, value)
        for n, value in enumerate((self.ctx, *args)):
            self.uc.reg_write(UC_ARM_REG_R0 + n, value)
        self.uc.emu_start(self.s('rec_reader_' + name), self.stop, count=2000000)
        assert self.uc.reg_read(UC_ARM_REG_PC) == self.stop, name
        assert self.uc.reg_read(UC_ARM_REG_SP) == self.stack + 0xF000
        assert tuple(self.uc.reg_read(UC_ARM_REG_R0 + n) for n in range(4, 12)) == saved
        return self.uc.reg_read(UC_ARM_REG_R0)

    def firmware(self, uc, address, size, data):
        r = [uc.reg_read(UC_ARM_REG_R0 + n) for n in range(4)]
        name = self.targets[address]
        assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0
        if name == 'READ':
            self.events.append((name, r[0], r[2] * 2))
            assert r[3] == 2
            uc.mem_write(r[1], self.get(r[0], r[2] * 2))
            if self.after_read:
                self.after_read(r[0])
        elif name == 'LOCK':
            assert r[0] == 1 and self.lock_depth == 0
            self.lock_depth += 1
        elif name == 'UNLOCK':
            assert r[0] == 1 and self.lock_depth == 1
            self.lock_depth -= 1
        elif name == 'GET':
            assert self.lock_depth == 1
        elif name == 'WRITE_RAW':
            assert self.lock_depth == 1 and r[0] == 0xD5D5D5D5
            step = struct.unpack('<I', uc.mem_read(uc.reg_read(UC_ARM_REG_SP), 4))[0]
            assert step == 2
            self.events.append(('WRITE', r[1], r[3] * 2))
            self.put(r[1], bytes(uc.mem_read(r[2], r[3] * 2)))
        elif name == 'BEGIN':
            self.events.append((name, r[0]))
            assert r[0] == 0
            self.info(0, 1)
            self.info(2, self.s('RR_DSP_RING'))
            self.info(3, self.s('RR_INPUT'))
            self.capture(self.initial_frames, elapsed=0)
        elif name == 'END':
            self.events.append((name,))
            if self.end_failures:
                self.end_failures -= 1
            else:
                self.info(0, 0)
                self.info(3, self.s('RR_INPUT'))
        for n in (0, 1, 2, 3, 12):
            uc.reg_write(UC_ARM_REG_R0 + n, 0xDEAD0000)
        if name == 'GET':
            uc.reg_write(UC_ARM_REG_R0, 0xD5D5D5D5)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))


def pcm(words):
    return b''.join(struct.pack('<HH', word >> 16, word & 65535) for word in words)


@unittest.skipUnless(UNICORN, 'Unicorn is required for the native ring reader')
class RecordingReaderTests(unittest.TestCase):
    def test_prepare_checks_availability_without_starting_or_writing_the_dsp(self):
        m = Reader()
        self.assertEqual(m.call('prepare', m.ring, 65536), 0)
        self.assertEqual(m.field('RR_OWNED'), 0)
        self.assertFalse(any(e[0] in ('WRITE', 'BEGIN', 'END') for e in m.events))
        m.info(0, 1)
        self.assertEqual(m.call('prepare', m.ring, 65536), m.s('RR_BUSY'))

    def test_start_retargets_capture_and_discards_frames_from_the_old_source(self):
        m = Reader()
        m.initial_frames = [0xDEADBEEF] * 50
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        self.assertEqual(m.info(3), m.s('RR_CAPTURE'))
        self.assertEqual(m.get(m.s('RR_ENABLE'), 4), struct.pack('<I', 1))
        words = [0x12340000 + i for i in range(1000)]
        m.capture(words)
        self.assertEqual(m.call('poll'), 0)
        size = m.field('RR_PRODUCED')
        self.assertEqual(size, (1000 - 256) * 4)
        self.assertEqual(bytes(m.uc.mem_read(m.ring, size)), pcm(words[:-256]))
        self.assertEqual(m.call('finish'), 0)
        self.assertEqual(m.field('RR_PRODUCED'), 4000)
        self.assertEqual(bytes(m.uc.mem_read(m.ring, 4000)), pcm(words))
        self.assertEqual(m.get(m.s('RR_ENABLE'), 4), bytes(4))
        self.assertEqual(m.field('RR_OWNED'), 0)

    def test_both_rings_wrap_without_repeating_or_swapping_frames(self):
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        captured, received = [], bytearray()
        for step in range(20):
            words = [((step * 2000 + n) * 104729) & 0xFFFFFFFF for n in range(2000)]
            captured += words
            m.capture(words, elapsed=40)
            self.assertEqual(m.call('poll'), 0)
            start, end = m.field('RR_CONSUMED'), m.field('RR_PRODUCED')
            for position in range(start, end, 4):
                received += m.uc.mem_read(m.ring + (position & 65535), 4)
            m.field('RR_CONSUMED', end)
        self.assertEqual(m.call('finish'), 0)
        start, end = m.field('RR_CONSUMED'), m.field('RR_PRODUCED')
        for position in range(start, end, 4):
            received += m.uc.mem_read(m.ring + (position & 65535), 4)
        self.assertEqual(received, pcm(captured))

    def test_a_late_reader_reports_a_gap_before_copying_aliased_dsp_data(self):
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.capture([0x12345678] * 5000, elapsed=110)
        self.assertEqual(m.call('poll'), m.s('RR_GAP'))
        self.assertEqual(m.field('RR_PRODUCED'), 0)
        self.assertEqual(m.call('finish'), m.s('RR_GAP'))
        self.assertIn(('END',), m.events)
        self.assertEqual(m.field('RR_OWNED'), 0)

    def test_arm_ring_overflow_is_visible_and_copies_no_partial_batch(self):
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.field('RR_PRODUCED', 65536 - 512)
        m.capture([0x12345678] * 1000)
        self.assertEqual(m.call('poll'), m.s('RR_OVERFLOW'))
        self.assertEqual(m.field('RR_PRODUCED'), 65536 - 512)

    def test_foreign_capture_and_sampling_are_never_stopped_or_retargeted(self):
        for index in (0, 10):
            with self.subTest(index=index):
                m = Reader()
                m.info(index, 1)
                self.assertEqual(m.call('begin', m.ring, 65536), m.s('RR_BUSY'))
                self.assertFalse(any(e[0] in ('WRITE', 'BEGIN', 'END') for e in m.events))
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.info(3, 0xFF90197C)
        self.assertEqual(m.call('poll'), m.s('RR_LOST'))
        self.assertEqual(m.call('finish'), m.s('RR_LOST'))
        self.assertNotIn(('END',), m.events)
        self.assertEqual(m.info(0), 1)

    def test_missing_dsp_program_and_bad_ring_arguments_have_no_dsp_writes(self):
        m = Reader()
        m.put(m.s('RR_MAGIC_ADDRESS'), bytes(4))
        self.assertEqual(m.call('begin', m.ring, 65536), m.s('RR_NO_PATCH'))
        self.assertFalse(any(e[0] == 'WRITE' for e in m.events))
        for pointer, size in [(0, 65536), (m.ring + 1, 65536), (m.ring, 65532), (m.ring, 32768), (m.ring, 4194304)]:
            m = Reader()
            self.assertEqual(m.call('begin', pointer, size), m.s('RR_BAD_ARG'))
            self.assertFalse(m.events)

    def test_tick_wrap_is_valid_but_time_spent_inside_a_read_is_checked(self):
        m = Reader()
        m.tick(0xFFFFFFF0)
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.capture([0x12345678] * 1000, elapsed=32)
        self.assertEqual(m.call('poll'), 0)
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.capture([0x12345678] * 1000)
        def stall(address):
            if m.s('RR_DSP_RING') <= address < m.s('RR_DSP_RING') + m.s('RR_DSP_BYTES'):
                m.tick(100)
        m.after_read = stall
        self.assertEqual(m.call('poll'), m.s('RR_GAP'))
        self.assertEqual(m.field('RR_PRODUCED'), 0)

    def test_transfer_completion_cannot_reset_the_age_of_the_snapshot(self):
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.capture([0x12345678] * 480, elapsed=10)
        stalled = False
        def stall(address):
            nonlocal stalled
            if not stalled and m.s('RR_DSP_RING') <= address < m.s('RR_DSP_RING') + m.s('RR_DSP_BYTES'):
                stalled = True
                m.capture([0xAABBCCDD] * 2880, elapsed=60)
        m.after_read = stall
        self.assertEqual(m.call('poll'), 0)
        before = m.field('RR_PRODUCED')
        m.after_read = None
        m.capture([0xDEADBEEF] * 3360, elapsed=70)
        self.assertEqual(m.call('poll'), m.s('RR_GAP'))
        self.assertEqual(m.field('RR_PRODUCED'), before)

    def test_start_snapshot_keeps_the_tick_before_its_info_transfer(self):
        m = Reader()
        stalled = False
        def stall(address):
            nonlocal stalled
            if not stalled and address == m.s('RR_DSP_STATE') and m.info(3) == m.s('RR_CAPTURE'):
                stalled = True
                m.capture([0x12345678] * 2160, elapsed=45)
        m.after_read = stall
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.after_read = None
        m.capture([0xAABBCCDD] * 3360, elapsed=70)
        self.assertEqual(m.call('poll'), m.s('RR_GAP'))
        self.assertEqual(m.field('RR_PRODUCED'), 0)

    def test_failed_stop_retains_ownership_until_retry(self):
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.end_failures = 1
        self.assertEqual(m.call('finish'), m.s('RR_LOST'))
        self.assertEqual(m.field('RR_OWNED'), 1)
        self.assertEqual(m.get(m.s('RR_ENABLE'), 4), struct.pack('<I', 1))
        self.assertEqual(m.call('finish'), m.s('RR_LOST'))
        self.assertEqual(m.field('RR_OWNED'), 0)
        self.assertEqual(m.get(m.s('RR_ENABLE'), 4), bytes(4))

    def test_monotonic_byte_counters_cross_uint32_without_losing_ring_position(self):
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.field('RR_PRODUCED', 0xFFFFF000)
        m.field('RR_CONSUMED', 0xFFFFF000)
        words = [(i * 104729) & 0xFFFFFFFF for i in range(2000)]
        m.capture(words, elapsed=40)
        self.assertEqual(m.call('poll'), 0)
        size = (2000 - 256) * 4
        self.assertEqual(m.field('RR_PRODUCED'), (0xFFFFF000 + size) & 0xFFFFFFFF)
        data = bytearray()
        for position in range(0xFFFFF000, 0xFFFFF000 + size, 4):
            data += m.uc.mem_read(m.ring + (position & 65535), 4)
        self.assertEqual(data, pcm(words[:-256]))

    def test_unaligned_dsp_cursor_and_ownership_change_during_read_do_not_publish(self):
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.info(2, m.s('RR_DSP_RING') + 3)
        self.assertEqual(m.call('poll'), m.s('RR_LOST'))
        m = Reader()
        self.assertEqual(m.call('begin', m.ring, 65536), 0)
        m.capture([0x12345678] * 1000)
        def steal(address):
            if m.s('RR_DSP_RING') <= address < m.s('RR_DSP_RING') + m.s('RR_DSP_BYTES'):
                m.info(3, 0xFF90197C)
        m.after_read = steal
        self.assertEqual(m.call('poll'), m.s('RR_LOST'))
        self.assertEqual(m.field('RR_PRODUCED'), 0)


if __name__ == '__main__':
    unittest.main()
