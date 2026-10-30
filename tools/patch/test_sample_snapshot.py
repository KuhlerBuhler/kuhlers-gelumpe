"""A streamed native descriptor and DSP PCM become a journalled sample entry."""
import importlib.util
import struct
import unittest

import arm
import sample_store
from test_sample_store import Machine, LIBRARY, JOURNAL, ORIGIN, STATE, header, word
from unicorn import UC_HOOK_CODE, arm_const as R

spec = importlib.util.find_spec("sample_snapshot")
snapshot = None
if spec is not None:
    import sample_snapshot as snapshot

CONTEXT, NATIVE, TRANSFER = STATE + 0x20000, 0xC0003000, 0xC0004000
DSP_BASE = 0x365EC2


class SnapshotTests(unittest.TestCase):
    def machine(self, frames=40001, channels=1):
        self.assertIsNotNone(snapshot, "the streaming DSP snapshot source is missing")
        m = Machine(bytes(header()) + b"old generated entry")
        m.uc.mem_map(CONTEXT, 0x12000)
        code = arm.assemble(sample_store.source(STATE) + snapshot.source(
            CONTEXT, native=NATIVE, transfer=TRANSFER), origin=ORIGIN)
        m.uc.mem_write(ORIGIN, code.bytes)
        m.symbols = code.symbols
        m.pcm = bytes((i * 37 + 19) % 256 for i in range(frames * channels * 2))
        m.desc = bytearray(0x494)
        m.desc[2:18] = b"Generated sample"
        m.desc[65] = channels - 1
        m.desc[67] = 1
        struct.pack_into("<I", m.desc, 72, 44100)
        m.transfers, m.snapshot_calls = [], []
        m.snapshot_ok, m.transfer_error = True, False
        m.base, m.transfer_short, m.fail_after = DSP_BASE, False, None

        def native(uc, at, size, _):
            slot, dest, base_out, length_out = [uc.reg_read(R.UC_ARM_REG_R0 + i) for i in range(4)]
            stack = uc.reg_read(R.UC_ARM_REG_SP)
            m.snapshot_calls.append((slot, struct.unpack('<I', uc.mem_read(stack, 4))[0]))
            self.assertEqual(stack % 8, 0)
            if m.snapshot_ok:
                desc = bytearray(m.desc)
                struct.pack_into('<H', desc, 0, slot)
                uc.mem_write(dest, bytes(desc))
                uc.mem_write(base_out, word(m.base))
                uc.mem_write(length_out, word(len(m.pcm)))
            uc.reg_write(R.UC_ARM_REG_R0, int(m.snapshot_ok))

        def transfer(uc, at, size, _):
            op, dest, base, count = [uc.reg_read(R.UC_ARM_REG_R0 + i) for i in range(4)]
            self.assertEqual(uc.reg_read(R.UC_ARM_REG_SP) % 8, 0)
            self.assertEqual(op, 0)
            self.assertEqual(dest % 2, 0)
            self.assertEqual(base % 2, 0)
            self.assertTrue(0 < count <= 32768)
            offset = base - m.base
            self.assertTrue(0 <= offset and offset + count * 2 <= len(m.pcm))
            m.transfers.append((base, count))
            failed = m.transfer_error or (m.fail_after is not None and len(m.transfers) > m.fail_after)
            if not failed:
                uc.mem_write(dest, m.pcm[offset:offset + count * 2])
            uc.reg_write(R.UC_ARM_REG_R0, 5 if failed else 0)
            uc.reg_write(R.UC_ARM_REG_R1, 0 if failed else count - int(m.transfer_short))

        for at, callback in ((NATIVE, native), (TRANSFER, transfer)):
            m.uc.mem_write(at, word(0xE12FFF1E))
            m.uc.hook_add(UC_HOOK_CODE, callback, begin=at, end=at)
        return m

    def expected(self, m, slot=500):
        channels = m.desc[65] + 1
        rate = struct.unpack_from('<I', m.desc, 72)[0]
        pcm = m.pcm
        desc = bytearray(m.desc)
        struct.pack_into('<H', desc, 0, slot)
        struct.pack_into('<H', desc, 20, slot + 50)
        struct.pack_into('<H', desc, 78, slot)
        return (b'RIFF' + word(len(pcm) + 1224) + b'WAVEfmt ' + word(16)
                + struct.pack('<HHIIHH', 1, channels, rate, rate * channels * 2, channels * 2, 16)
                + b'data' + word(len(pcm)) + pcm
                + b'korg' + word(1180) + b'esli' + word(1172) + desc)

    def test_snapshot_appends_complete_mono_and_stereo_entries(self):
        for channels in (1, 2):
            with self.subTest(channels=channels):
                m = self.machine(channels=channels)
                before = bytes(m.files[LIBRARY])
                self.assertEqual(m.call('store_snapshot', m.path, 500), 0)
                self.assertEqual(m.files[LIBRARY][len(before):], self.expected(m))
                self.assertEqual(struct.unpack_from('<I', m.files[LIBRARY], 16 + 500 * 4)[0], len(before))
                self.assertEqual(m.files[LIBRARY][4096:len(before)], before[4096:])
                self.assertNotIn(JOURNAL, m.files)
                self.assertEqual(m.snapshot_calls, [(500, 0)])

    def test_unchanged_snapshot_does_not_append_again(self):
        m = self.machine(channels=2)
        self.assertEqual(m.call('store_snapshot', m.path, 500), 0)
        saved = bytes(m.files[LIBRARY])
        m.writes.clear()
        self.assertEqual(m.call('store_snapshot', m.path, 500), 0)
        self.assertEqual(len(m.files[LIBRARY]), len(saved))
        self.assertEqual(m.files[LIBRARY], saved)
        self.assertEqual(m.writes, [])

    def test_runtime_import_key_is_not_persisted_as_the_logical_slots_key(self):
        m = self.machine()
        struct.pack_into('<H', m.desc, 20, 651)
        struct.pack_into('<H', m.desc, 78, 601)
        before = len(m.files[LIBRARY])
        self.assertEqual(m.call('store_snapshot', m.path, 500), 0)
        entry = m.files[LIBRARY][before:]
        record = 44 + len(m.pcm) + 16
        self.assertEqual(tuple(struct.unpack_from('<H', entry, record + n)[0] for n in (0, 20, 78)),
                         (500, 550, 500))

    def test_reader_handles_odd_offsets_and_every_entry_boundary(self):
        m = self.machine(frames=33, channels=2)
        self.assertEqual(m.call('snapshot_prepare', 998), 0)
        expected = self.expected(m, 998)
        dest = CONTEXT + 0x11001
        for at, length in ((0, 1), (3, 46), (43, 7), (44, 1), (45, 15),
                           (44 + len(m.pcm) - 1, 20), (len(expected) - 3, 20),
                           (len(expected), 50), (0xFFFFFFFF, 10), (40, 0)):
            with self.subTest(at=at, length=length):
                m.uc.mem_write(dest - 1, b'H' + b'X' * 100 + b'T')
                self.assertEqual(m.call('snapshot_read', CONTEXT + 8, at, dest, length), 0)
                count = m.uc.reg_read(R.UC_ARM_REG_R1)
                data = expected[at:at + length]
                self.assertEqual(count, len(data))
                self.assertEqual(bytes(m.uc.mem_read(dest, count)), data)
                self.assertEqual(bytes(m.uc.mem_read(dest - 1, 1)), b'H')
                self.assertEqual(bytes(m.uc.mem_read(dest + count, 1)), b'X')

    def test_failed_native_snapshot_performs_no_card_writes(self):
        m = self.machine()
        before = bytes(m.files[LIBRARY])
        m.snapshot_ok = False
        self.assertNotEqual(m.call('store_snapshot', m.path, 500), 0)
        self.assertEqual(m.files[LIBRARY], before)
        self.assertEqual(m.writes, [])
        self.assertEqual(m.transfers, [])

    def test_invalid_slot_is_refused_before_snapshot_or_card_access(self):
        for slot in (499, 999, 0xFFFFFFFF):
            m = self.machine()
            self.assertNotEqual(m.call('store_snapshot', m.path, slot), 0)
            self.assertEqual(m.snapshot_calls, [])
            self.assertEqual(m.calls, [])

    def test_invalid_pcm_or_format_never_writes_the_card(self):
        for invalid in ('empty', 'odd', 'channels', 'rate'):
            m = self.machine(frames=17)
            if invalid == 'empty':
                m.pcm = b''
            elif invalid == 'odd':
                m.pcm += b'X'
            elif invalid == 'channels':
                m.desc[65] = 2
            else:
                struct.pack_into('<I', m.desc, 72, 0)
            self.assertNotEqual(m.call('store_snapshot', m.path, 500), 0)
            self.assertEqual(m.writes, [])

    def test_dsp_failure_keeps_the_old_slot_index(self):
        m = self.machine()
        before = bytes(m.files[LIBRARY][:4096])
        m.transfer_error = True
        self.assertNotEqual(m.call('store_snapshot', m.path, 500), 0)
        self.assertEqual(m.files[LIBRARY][:4096], before)
        self.assertNotIn(JOURNAL, m.files)

    def test_card_failure_is_not_reported_as_success(self):
        m = self.machine()
        m.short_write = True
        before = bytes(m.files[LIBRARY][:4096])
        self.assertNotEqual(m.call('store_snapshot', m.path, 500), 0)
        self.assertEqual(m.files[LIBRARY][:4096], before)

    def test_a_later_dsp_error_leaves_only_an_unindexed_partial_append(self):
        m = self.machine(frames=80000)
        before = bytes(m.files[LIBRARY][:4096])
        m.fail_after = 1
        self.assertNotEqual(m.call('store_snapshot', m.path, 500), 0)
        self.assertEqual(m.files[LIBRARY][:4096], before)
        self.assertNotIn(JOURNAL, m.files)
        self.assertTrue(m.writes)
        self.assertEqual(m.handles, {})

    def test_short_dsp_success_is_still_a_failed_source(self):
        m = self.machine()
        before = bytes(m.files[LIBRARY][:4096])
        m.transfer_short = True
        self.assertNotEqual(m.call('store_snapshot', m.path, 500), 0)
        self.assertEqual(m.files[LIBRARY][:4096], before)

    def test_invalid_extents_and_rate_overflow_are_refused_before_card_access(self):
        for base in (0x365EBE, DSP_BASE + 1, 0x1C65EC0 - 2, 0xFFFFFFFE):
            m = self.machine(frames=4)
            m.base = base
            self.assertNotEqual(m.call('store_snapshot', m.path, 500), 0)
            self.assertEqual(m.calls, [])
        m = self.machine(frames=4, channels=2)
        struct.pack_into('<I', m.desc, 72, 0x40000000)
        self.assertNotEqual(m.call('store_snapshot', m.path, 500), 0)
        self.assertEqual(m.calls, [])

    def test_stereo_requires_complete_frames(self):
        m = self.machine(frames=4, channels=2)
        m.pcm = m.pcm[:-2]
        self.assertNotEqual(m.call('store_snapshot', m.path, 500), 0)
        self.assertEqual(m.calls, [])


if __name__ == '__main__':
    unittest.main()
