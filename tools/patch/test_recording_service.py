"""Native reader-to-WAV worker with a synthetic DSP and fault-injecting FatFs."""
import io
from pathlib import Path
import struct
import sys
import unittest
import wave

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.patch.test_recording_writer import Writer, UNICORN
from tools.patch.test_recording_reader import Reader, pcm
if UNICORN:
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_CPSR


class Recorder(Writer):
    get, put, info, tick, capture = Reader.get, Reader.put, Reader.info, Reader.tick, Reader.capture

    def __init__(self, capacity=131072, code=None, build='hacktribe'):
        from tools.patch.recording_service import build as build_service
        super().__init__(code=code if code is not None else build_service(build=build, origin=0x100000))
        dsp_targets = {self.s('RR_FW_' + name): name for name in ('READ', 'WRITE_RAW', 'GET', 'LOCK', 'UNLOCK', 'BEGIN', 'END')}
        for page in {a & ~4095 for a in dsp_targets} | {self.s('RR_TICKS') & ~4095}:
            if not 0x100000 <= page < 0x110000:
                self.uc.mem_map(page, 4096)
        self.targets.update(dsp_targets)
        self.memory, self.after_read, self.initial_frames, self.end_failures = {}, None, [], 0
        self.lock_depth = 0
        self.on_fat = None
        self.require_irq_enabled = False
        self.put(self.s('RR_MAGIC_ADDRESS'), struct.pack('<I', self.s('RR_MAGIC')))
        self.info(1, self.s('RR_DSP_BYTES'))
        self.info(2, self.s('RR_DSP_RING'))
        self.info(3, self.s('RR_INPUT'))
        for address in dsp_targets:
            self.uc.mem_write(address, struct.pack('<I', 0xE12FFF1E))
            self.uc.hook_add(UC_HOOK_CODE, self.dsp, begin=address, end=address)
        self.write(self.s('RC_RING'), self.pcm)
        self.write(self.s('RC_CAPACITY'), capacity)
        self.write(self.s('RC_CHANNELS'), 2)

    def dsp(self, *args):
        if self.require_irq_enabled:
            assert not self.uc.reg_read(UC_ARM_REG_CPSR) & 0xC0
        Reader.firmware(self, *args)

    def fat(self, uc, address, size, data):
        name = self.targets[address]
        if self.require_irq_enabled:
            assert not self.uc.reg_read(UC_ARM_REG_CPSR) & 0xC0
        super().fat(uc, address, size, data)
        if self.on_fat:
            self.on_fat(name)

    def rr(self, name, value=None):
        offset = self.s('RC_READER') + self.s(name)
        if value is not None:
            self.write(offset, value)
        return self.read(offset)

    def command(self, start):
        return self.call('recorder_command', start)

    def pump(self):
        return self.call('recorder_pump')

    def finish(self):
        self.assert_command_stop()
        for _ in range(64):
            self.pump()
            if not self.field('RC_ACTIVE'):
                return self.field('RC_ERROR')
        raise AssertionError('recorder did not finish')

    def assert_command_stop(self):
        assert self.command(0) == 0


@unittest.skipUnless(UNICORN, 'Unicorn is required for the native recording worker')
class RecordingServiceTests(unittest.TestCase):
    def test_synth_records_one_pcm_channel_from_q31_capture(self):
        m = Recorder(build='synth')
        m.write(m.s('RC_CHANNELS'), 1)
        self.assertEqual(m.command(1), 0)
        self.assertEqual(m.pump(), 0)
        captured = []
        for step in range(3):
            words = [((step * 2000 + n) * 104729) & 0xFFFFFFFF for n in range(2000)]
            captured += words
            m.capture(words, elapsed=40)
            self.assertEqual(m.pump(), 0)
        self.assertEqual(m.finish(), 0)
        data = bytes(m.files['SD:Recordings/REC0001.WAV'])
        with wave.open(io.BytesIO(data)) as wav:
            self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getsampwidth()), (1, 48000, 2))
            self.assertEqual(wav.getnframes(), len(captured))
            self.assertEqual(wav.readframes(wav.getnframes()), b''.join(struct.pack('<H', w >> 16) for w in captured))
        self.assertFalse(m.handles)

    def test_file_limit_splits_frames_without_an_empty_following_file(self):
        for words in ([0x12345678], [0x12345678, 0x90ABCDEF]):
            with self.subTest(frames=len(words)):
                m = Recorder()
                m.command(1)
                self.assertEqual(m.pump(), 0)
                # Exercise the real 32-bit limit without allocating a 4-GiB mock file.
                m.write(m.s('RW_DATA_BYTES'), m.s('RW_MAX_DATA') - 4)
                m.capture(words, elapsed=20)
                self.assertEqual(m.finish(), 0)
                self.assertEqual(m.field('RC_DROPPED'), 0)
                self.assertEqual(m.field('RW_NUMBER'), len(words))
                first = m.files['SD:Recordings/REC0001.WAV']
                self.assertEqual(first[-4:], pcm(words[:1]))
                self.assertEqual(struct.unpack_from('<I', first, 508)[0], m.s('RW_MAX_DATA'))
                self.assertEqual(len(m.files), len(words))
                if len(words) == 2:
                    self.assertEqual(m.files['SD:Recordings/REC0002.WAV'][512:], pcm(words[1:]))
                self.assertFalse(m.handles)

    def test_checkpoint_failure_stops_capture_and_keeps_the_card_error_visible(self):
        m = Recorder()
        m.command(1)
        self.assertEqual(m.pump(), 0)
        m.sync_fault = (2, 3)
        result = 0
        for _ in range(30):
            m.capture([0x12345678] * 2000, elapsed=40)
            result = m.pump()
            if result:
                break
        self.assertEqual(result, m.s('RW_IO'))
        self.assertEqual(m.field('RC_ERROR'), m.s('RW_IO'))
        self.assertEqual(m.field('RW_FS_ERROR'), 3)
        self.assertEqual(m.rr('RR_OWNED'), 0)
        self.assertEqual(m.field('RC_ACTIVE'), 0)
        self.assertFalse(m.handles)

    def test_commands_only_post_requests_and_the_worker_writes_exact_pcm(self):
        m = Recorder()
        self.assertEqual(m.command(1), 0)
        self.assertFalse(m.events)
        self.assertEqual(m.call('recorder_busy'), 1)
        self.assertEqual(m.pump(), 0)
        self.assertEqual(m.field('RC_ACTIVE'), 1)
        captured = []
        for step in range(30):
            words = [((step * 2000 + n) * 104729) & 0xFFFFFFFF for n in range(2000)]
            captured += words
            m.capture(words, elapsed=40)
            self.assertEqual(m.pump(), 0)
        saved = m.durable['SD:Recordings/REC0001.WAV']
        with wave.open(io.BytesIO(saved)) as wav:
            count = wav.getnframes()
            self.assertGreaterEqual(count, 48000)
            self.assertLess(count, len(captured))
            self.assertEqual(wav.readframes(count), pcm(captured[:count]))
        self.assertEqual(m.finish(), 0)
        self.assertEqual(m.call('recorder_busy'), 0)
        data = bytes(m.files['SD:Recordings/REC0001.WAV'])
        with wave.open(io.BytesIO(data)) as wav:
            self.assertEqual((wav.getnchannels(), wav.getnframes()), (2, len(captured)))
            self.assertEqual(wav.readframes(wav.getnframes()), pcm(captured))
        self.assertEqual(data[512:], pcm(captured))
        self.assertFalse(m.handles)
        writes = [e for e in m.events if e[0] == 'WRITE' and len(e) == 4]
        self.assertTrue(any(e[2] == 65536 for e in writes))
        self.assertTrue(all(e[2] <= 65536 for e in writes))

    def test_worker_requires_space_for_two_storage_blocks(self):
        m = Recorder(capacity=65536)
        self.assertEqual(m.command(1), 0)
        self.assertEqual(m.pump(), m.s('RW_BAD_ARG'))
        self.assertFalse(m.files)
        self.assertEqual(m.field('RC_ACTIVE'), 0)

    def test_busy_sampling_or_missing_dsp_patch_creates_no_file(self):
        for fault in ('sampling', 'capture', 'patch'):
            with self.subTest(fault=fault):
                m = Recorder()
                if fault == 'sampling':
                    m.info(10, 1)
                elif fault == 'capture':
                    m.info(0, 1)
                else:
                    m.put(m.s('RR_MAGIC_ADDRESS'), bytes(4))
                self.assertEqual(m.command(1), 0)
                self.assertNotEqual(m.pump(), 0)
                self.assertFalse(m.files)
                self.assertEqual(m.field('RC_ACTIVE'), 0)
                self.assertNotIn(('END',), m.events)

    def test_stop_posted_while_the_worker_claims_start_is_preserved(self):
        m = Recorder()
        m.uc.reg_write(UC_ARM_REG_CPSR, 0x60000013)
        m.require_irq_enabled = True
        self.assertEqual(m.command(1), 0)
        pending = fired = False
        def interrupt(uc, address, size, data):
            nonlocal pending, fired
            if address == m.s('recorder_claim_loaded'):
                pending = True
            if pending and not fired and not uc.reg_read(UC_ARM_REG_CPSR) & 0x80:
                fired = True
                if m.field('RC_ACTIVE') or m.field('RC_REQUEST') == 1:
                    m.write(m.s('RC_REQUEST'), 2)
        hook = m.uc.hook_add(UC_HOOK_CODE, interrupt)
        try:
            for _ in range(4):
                m.pump()
        finally:
            m.uc.hook_del(hook)
        self.assertTrue(fired)
        self.assertEqual(m.field('RC_ACTIVE'), 0)
        self.assertEqual(m.call('recorder_busy'), 0)
        self.assertFalse(m.handles)
        self.assertEqual(m.uc.reg_read(UC_ARM_REG_CPSR) & 0xC0, 0)

    def test_stop_during_file_open_is_not_lost(self):
        m = Recorder()
        def stop(name):
            if name == 'OPEN':
                m.write(m.s('RC_REQUEST'), 2)
        m.on_fat = stop
        self.assertEqual(m.command(1), 0)
        self.assertEqual(m.pump(), 0)
        for _ in range(4):
            m.pump()
        self.assertEqual(m.field('RC_ACTIVE'), 0)
        self.assertFalse(m.handles)
        self.assertIn(('END',), m.events)

    def test_stop_before_first_worker_call_cancels_the_start(self):
        m = Recorder()
        self.assertEqual(m.command(1), 0)
        self.assertEqual(m.command(0), 0)
        self.assertEqual(m.pump(), 0)
        self.assertFalse(m.events)
        self.assertFalse(m.files)
        self.assertEqual(m.call('recorder_busy'), 0)

    def test_partial_pcm_write_stops_capture_and_reports_discarded_bytes(self):
        m = Recorder()
        self.assertEqual(m.command(1), 0)
        self.assertEqual(m.pump(), 0)
        m.write_fault = (2, 0, 7)
        for _ in range(10):
            m.capture([0x12345678] * 2000, elapsed=40)
            m.pump()
            if m.field('RC_ACTIVE') != 1:
                break
        for _ in range(4):
            m.pump()
        self.assertEqual(m.field('RC_ERROR'), m.s('RW_FULL'))
        self.assertGreater(m.field('RC_DROPPED'), 0)
        self.assertEqual(m.rr('RR_OWNED'), 0)
        self.assertFalse(m.handles)
        self.assertEqual(m.field('RC_ACTIVE'), 0)
        data = next(iter(m.files.values()))
        self.assertEqual(struct.unpack_from('<I', data, 508)[0], 4)

    def test_slow_card_write_causes_a_visible_dsp_gap(self):
        m = Recorder()
        self.assertEqual(m.command(1), 0)
        self.assertEqual(m.pump(), 0)
        def stall(name):
            if name == 'WRITE' and m.write_number == 2:
                m.capture([0xAABBCCDD] * 5280, elapsed=110)
        m.on_fat = stall
        for _ in range(10):
            m.capture([0x12345678] * 2000, elapsed=40)
            m.pump()
            if m.write_number >= 2:
                break
        self.assertEqual(m.pump(), m.s('RC_READER_ERROR') + m.s('RR_GAP'))
        for _ in range(4):
            m.pump()
        self.assertEqual(m.field('RC_ACTIVE'), 0)
        self.assertEqual(m.rr('RR_OWNED'), 0)
        self.assertFalse(m.handles)

    def test_close_and_capture_stop_failures_remain_busy_until_retried(self):
        for failure in ('file', 'capture'):
            with self.subTest(failure=failure):
                m = Recorder()
                self.assertEqual(m.command(1), 0)
                self.assertEqual(m.pump(), 0)
                if failure == 'file':
                    m.close_failures = 1
                else:
                    m.end_failures = 1
                self.assertEqual(m.command(0), 0)
                self.assertNotEqual(m.pump(), 0)
                self.assertEqual(m.call('recorder_busy'), 1)
                self.assertEqual(m.command(1), m.s('RW_BAD_STATE'))
                for _ in range(4):
                    m.pump()
                self.assertEqual(m.call('recorder_busy'), 0)
                self.assertFalse(m.handles)
                self.assertEqual(m.rr('RR_OWNED'), 0)

    def test_failed_rollover_does_not_reuse_a_previous_write_count(self):
        m = Recorder()
        self.assertEqual(m.command(1), 0)
        self.assertEqual(m.pump(), 0)
        m.write(m.s('RW_DATA_BYTES'), m.s('RW_MAX_DATA'))
        m.write(m.s('RW_NUMBER'), 9999)
        m.rr('RR_PRODUCED', 65536)
        self.assertEqual(m.pump(), m.s('RW_NO_NAME'))
        for _ in range(4):
            m.pump()
        self.assertEqual(m.field('RC_DROPPED'), 65536)
        self.assertEqual(m.rr('RR_CONSUMED'), 65536)
        self.assertEqual(m.field('RC_ERROR'), m.s('RW_NO_NAME'))

    def test_next_recording_uses_a_new_file_and_resets_stream_counters(self):
        m = Recorder()
        for index in (1, 2):
            self.assertEqual(m.command(1), 0)
            self.assertEqual(m.pump(), 0)
            m.capture([0x12345678] * 1000)
            self.assertEqual(m.pump(), 0)
            self.assertEqual(m.finish(), 0)
            self.assertEqual(m.field('RW_NUMBER'), index)
            self.assertEqual(m.field('RW_DATA_BYTES'), 4000)
        self.assertEqual(len(m.files), 2)

    def test_terminal_capture_faults_write_a_labelled_cue_without_inventing_lost_pcm(self):
        for failure, reason, label in (('late', 1, b'Capture gap'), ('foreign', 2, b'Capture lost')):
            m = Recorder()
            m.command(1)
            m.pump()
            m.capture([0x12345678] * 1000, elapsed=20)
            m.pump()
            if failure == 'late':
                m.tick(m.tick() + 100)
            else:
                m.info(3, m.s('RR_INPUT'))
            for _ in range(8):
                m.pump()
                if not m.field('RC_ACTIVE'):
                    break
            self.assertNotEqual(m.field('RC_ERROR'), 0)
            self.assertEqual(m.field('RW_MARKER'), reason)
            data = bytes(m.files['SD:Recordings/REC0001.WAV'])
            self.assertEqual(data[12:16], b'cue ')
            self.assertIn(label + b'\0', data[:512])
            with wave.open(io.BytesIO(data)) as wav:
                self.assertEqual(wav.readframes(wav.getnframes()), pcm([0x12345678] * wav.getnframes()))
            self.assertEqual(struct.unpack_from('<I', data, 44)[0], (len(data) - 512) // 4)


if __name__ == '__main__':
    unittest.main()
