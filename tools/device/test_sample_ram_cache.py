"""Generated ARM926 cache and physical-memory models, no hardware or firmware."""
import hashlib
import json
import struct
import unittest
from unittest.mock import patch

import unicorn
from unicorn import arm_const as R

import sample_ram_canary as old
import sample_ram_cache as p


class CacheMachine:
    def __init__(self, case, operation, start=old.START, end=old.START + 8192, seed=77, control=0x5107D):
        self.case, self.start, self.end = case, start, end
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.uc.mem_map(0xC0000000, 0x800000)
        self.uc.mem_map(old.STUB, 0x10000)
        lo, hi = start - 4096, end + 4096
        self.uc.mem_map(lo, hi - lo)
        self.uc.mem_map(lo + p.ALIAS, hi - lo)
        self.uc.mem_write(lo, b'K' * (hi - lo))
        self.uc.mem_write(lo + p.ALIAS, b'P' * (hi - lo))
        self.uc.mem_write(old.SCREENS, struct.pack('<I', 0xC06B0000))
        self.uc.mem_write(0xC06B002C, struct.pack('<I', 1))
        self.uc.mem_write(old.TRANSPORT, struct.pack('<I', 0xC06B1000))
        self.code, self.symbols = p.build(operation, start, end, seed, 123)
        self.uc.mem_write(old.STUB, self.code)
        self.trap = old.STUB + 0xF000
        self.events, self.pending, self.upper_reads, self.upper_writes = [], {}, [], []
        self.tcm_reads = []
        self.values = {0xEE116F10: control, 0xEE100F10: 0x41069265,
                       0xEE120F10: 0x8001C000, 0xEE130F10: 3, 0xEE1D0F10: 0,
                       0xEE190F11: 0x1C, 0xEE190F31: 0x1C}
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.cp15, begin=old.STUB, end=old.STUB + len(self.code) - 1)
        for first in (lo, lo + p.ALIAS):
            self.uc.hook_add(unicorn.UC_HOOK_MEM_READ, self.read, begin=first, end=first + hi - lo - 1)
            self.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, self.write, begin=first, end=first + hi - lo - 1)

    def read(self, uc, access, address, size, value, _):
        self.upper_reads.append(address)

    def write(self, uc, access, address, size, value, _):
        self.upper_writes.append(address)

    def cp15(self, uc, address, size, _):
        word = struct.unpack('<I', uc.mem_read(address, 4))[0]
        if word in self.values:
            if word in (0xEE190F11, 0xEE190F31): self.tcm_reads.append(word)
            register = R.UC_ARM_REG_R6 if word == 0xEE116F10 else R.UC_ARM_REG_R0
            uc.reg_write(register, self.values[word])
        elif word == 0xEE070F3A:
            line = uc.reg_read(R.UC_ARM_REG_R0)
            self.case.assertTrue(self.start <= line <= self.end - 32 and not line & 31)
            self.pending[line] = bytes(uc.mem_read(line, 32))
            self.events.append(('clean', line))
        elif word == 0xEE070F9A:
            for line, data in self.pending.items():
                uc.mem_write(line + p.ALIAS, data)
            self.pending.clear()
            self.events.append(('drain', 0))
        else:
            if word & 0x0F100010 == 0x0E000010 and word >> 8 & 15 == 15:
                self.case.fail('unexpected CP15 write')
            return
        uc.reg_write(R.UC_ARM_REG_PC, address + 4)

    def run(self, token=123):
        self.uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
        self.uc.reg_write(R.UC_ARM_REG_SP, old.STUB + 0xE000)
        self.uc.reg_write(R.UC_ARM_REG_R0, token)
        self.uc.reg_write(R.UC_ARM_REG_LR, self.trap)
        saved = {R.UC_ARM_REG_R0 + i: 0xA000 + i for i in range(4, 13)}
        for reg, value in saved.items():
            self.uc.reg_write(reg, value)
        self.uc.emu_start(old.STUB, self.trap, count=1500000)
        self.case.assertEqual(self.uc.reg_read(R.UC_ARM_REG_PC), self.trap)
        for reg, value in saved.items():
            self.case.assertEqual(self.uc.reg_read(reg), value)
        return struct.unpack('<8I', self.uc.mem_read(old.RESULT, 32))

    def expected(self, seed=77):
        return b''.join(struct.pack('<I', address ^ seed) for address in range(self.start, self.end, 4))


class CacheProbe(unittest.TestCase):
    def test_host_stops_on_view_disagreement_and_restores_owned_scratch(self):
        states, rows = [], []
        class Link:
            def __init__(self): self.restored = []
            def read(self, address, size):
                if address in (old.STUB, old.STUB + p.ALIAS): return b'B' * size
                if address == old.MAP: return bytes([1, 0, 1, 0, 1, 0])
                raise AssertionError(hex(address))
            def write_at(self, address, data): self.restored.append((address, data))
        link = Link()
        words = (old.MAGIC, 123, 0, 0x5107D, old.START, old.START + 8192, 1, 1)
        with patch.object(p, 'preflight_backend'), patch.object(p.mmu, 'diagnose', return_value={'cpu': {}, 'layout': {}}), \
             patch.object(p, 'validate_mapping'), patch.object(old, 'quiescent'), \
             patch.object(old, 'execute_code', return_value=words) as execute:
            with self.assertRaisesRegex(ValueError, 'views disagree'):
                p.measure(link, b'', {}, 'check', 77, rows.append, states.append,
                          start=old.START, end=old.START + 8192)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(link.restored, [(old.STUB, b'B' * 1024)])
        self.assertEqual(states, [False, True])
        self.assertEqual(rows[-1]['view_disagreements'], [[old.START, 1]])

    def test_host_never_reads_or_restores_after_unconfirmed_exec(self):
        class Link:
            def read(self, address, size):
                if address != old.STUB: raise AssertionError('read after uncertain EXEC')
                return b'B' * size
            def write_at(self, address, data): raise AssertionError('restore after uncertain EXEC')
        states = []
        with patch.object(p, 'preflight_backend'), patch.object(p.mmu, 'diagnose', return_value={'cpu': {}, 'layout': {}}), \
             patch.object(p, 'validate_mapping'), patch.object(old, 'quiescent'), \
             patch.object(old, 'execute_code', side_effect=RuntimeError('unconfirmed')) as execute:
            with self.assertRaisesRegex(RuntimeError, 'unconfirmed'):
                p.measure(Link(), b'', {}, 'seed', 77, lambda row: None, states.append,
                          start=old.START, end=old.START + 2 * p.CHUNK)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(states, [False])

    def test_later_unconfirmed_chunk_does_not_restore_after_earlier_success(self):
        class Link:
            def read(self, address, size):
                if address == old.STUB: return b'B' * size
                if address == old.MAP: return bytes(size)
                raise AssertionError('read after uncertain later chunk')
            def write_at(self, address, data): raise AssertionError('restore after uncertain later chunk')
        states = []
        done = (old.MAGIC, 1, 0, 0x5107D, old.START, old.START + p.CHUNK, 0, 0)
        with patch.object(p, 'preflight_backend'), patch.object(p.mmu, 'diagnose', return_value={'cpu': {}, 'layout': {}}), \
             patch.object(p, 'validate_mapping'), patch.object(old, 'quiescent'), \
             patch.object(old, 'execute_code', side_effect=[done, RuntimeError('unconfirmed')]) as execute:
            with self.assertRaisesRegex(RuntimeError, 'unconfirmed'):
                p.measure(Link(), b'', {}, 'seed', 77, lambda row: None, states.append,
                          start=old.START, end=old.START + 2 * p.CHUNK)
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(states, [False, False])

    def test_tail_chunk_ends_exactly_at_the_arena_boundary(self):
        start = old.END - p.CHUNK - 4096
        class Link:
            def read(self, address, size): return b'B' * size if address in (old.STUB, old.STUB + p.ALIAS) else bytes(size)
            def write_at(self, address, data): pass
        words = [(old.MAGIC, 1, 0, 0x5107D, start, old.END - 4096, 0, 0),
                 (old.MAGIC, 2, 0, 0x5107D, old.END - 4096, old.END, 0, 0)]
        rows, states = [], []
        with patch.object(p, 'preflight_backend'), patch.object(p.mmu, 'diagnose', return_value={'cpu': {}, 'layout': {}}), \
             patch.object(p, 'validate_mapping'), patch.object(old, 'quiescent'), \
             patch.object(old, 'execute_code', side_effect=words):
            p.measure(Link(), b'', {}, 'seed', 77, rows.append, states.append, start=start, end=old.END)
        self.assertEqual([(r['start'], r['end']) for r in rows if r['operation'] == 'seed'],
                         [(start, old.END - 4096), (old.END - 4096, old.END)])
        self.assertTrue(states[-1])

    def test_mapping_must_match_both_views_and_stable_cpu_registers(self):
        import sample_ram_mmu as mmu
        table = bytearray(0x4000)
        for index in range(0xC00, 0xC40):
            struct.pack_into('<I', table, index * 4, index << 20 | 0xC1E)
            struct.pack_into('<I', table, (index + 0x40) * 4, index << 20 | 0xC12)
        struct.pack_into('<I', table, 0x800 * 4, 0x80000C1E)
        cpu = dict(cpu_id=0x41069265, control=0x5107D, ttbr=0x8001C000, domain_control=3, fcse=0, dtcm_region=0x1C, itcm_region=0x1C)
        report = dict(cpu=cpu, cpu_after=dict(cpu), layout=mmu.decode_table(table, 0x8001C000, cpu))
        p.validate_mapping(report)
        for key, value in (('policy', 'write_through'), ('domain_access', 'client'), ('ap', 0)):
            changed = json.loads(json.dumps(report));changed['layout']['regions'][0][key] = value
            with self.assertRaises(ValueError):p.validate_mapping(changed)
        for key, value in (('control', 0x5007D), ('dtcm_region', 0xC300001D), ('itcm_region', 0xC300001D)):
            changed = json.loads(json.dumps(report))
            changed['cpu'][key] = value;changed['cpu_after'][key] = value
            with self.assertRaises(ValueError):p.validate_mapping(changed)
        changed = json.loads(json.dumps(report));changed['cpu_after']['ttbr'] = 0xC2000000
        with self.assertRaises(ValueError):p.validate_mapping(changed)
        changed = json.loads(json.dumps(report));changed['layout']['mirror_regions'][0]['physical_start'] += 4096
        with self.assertRaises(ValueError):p.validate_mapping(changed)

    def test_baseline_rejects_old_upload_backend_and_mismatched_image(self):
        vsb = bytearray(0x200100)
        changes = []
        for index in range(5):
            at = 0x200 + index * 4
            data = bytes.fromhex('3a0f07ee') if index == 4 else bytes([index + 1]) * 4
            vsb[at:at+4] = data
            changes.append(dict(file=at, bytes=data.hex()))
        patch_data = dict(format='gelumpe-patch', id='blech-sysex', builds=['hacktribe'], changes=changes)
        with patch.object(old.sample_swap_io, 'validate_firmware', return_value='hacktribe'):
            self.assertEqual(len(p.baseline(vsb, patch_data)), 5)
            damaged = bytearray(vsb);damaged[0x200] ^= 1
            with self.assertRaises(ValueError):p.baseline(damaged, patch_data)
            changed = json.loads(json.dumps(patch_data));changed['changes'][-1]['bytes'] = '00000000'
            vsb[0x210:0x214] = bytes(4)
            with self.assertRaisesRegex(ValueError, 'publication'):p.baseline(vsb, changed)

    def test_execute_requires_every_confirmation_and_files_before_midi(self):
        for args in (['--execute'], ['--execute', '--operation', 'seed', '--seed', '77']):
            with self.assertRaises(ValueError):p.arguments(args)
        self.assertFalse(p.arguments([]).execute)

    def test_seed_publishes_only_its_chunk_and_verifies_physical_memory(self):
        for start, size in ((old.START, 4096), (old.START, p.CHUNK), (old.END - 4096, 4096)):
            with self.subTest(start=start, size=size):
                m = CacheMachine(self, 'seed', start=start, end=start + size)
                result = m.run()
                self.assertEqual(result[:3], (old.MAGIC, 123, 0))
                self.assertEqual(result[4:], (m.start, m.end, 0, 0))
                self.assertEqual(bytes(m.uc.mem_read(m.start + p.ALIAS, size)), m.expected())
                self.assertEqual([a for op, a in m.events if op == 'clean'], list(range(m.start, m.end, 32)))
                self.assertEqual(m.events[-1], ('drain', 0))
                self.assertEqual(bytes(m.uc.mem_read(m.start - 4, 4)), b'K' * 4)
                self.assertEqual(bytes(m.uc.mem_read(m.end + p.ALIAS, 4)), b'P' * 4)
                self.assertEqual(m.upper_writes, list(range(m.start, m.end, 4)))

    def test_check_observes_cached_cpu_and_uncached_dma_changes_without_cleaning(self):
        m = CacheMachine(self, 'check')
        m.uc.mem_write(m.start, m.expected())
        m.uc.mem_write(m.start + p.ALIAS, m.expected())
        m.uc.mem_write(m.start + 4 + p.ALIAS, b'DMA!')
        m.uc.mem_write(m.start + 4096 + 8, b'CPU!')
        self.assertEqual(m.run()[6:], (1, 1))
        self.assertEqual(bytes(m.uc.mem_read(old.MAP, 6)), bytes([1, 0, 0, 1, 1, 1]))
        self.assertEqual(m.events, [])
        self.assertEqual(m.upper_writes, [])
        first_cached = next(i for i, a in enumerate(m.upper_reads) if a < old.END)
        self.assertEqual(first_cached, (m.end - m.start) // 4 + 1)

    def test_same_change_counts_do_not_hide_different_view_contents(self):
        m = CacheMachine(self, 'check')
        m.uc.mem_write(m.start, m.expected())
        m.uc.mem_write(m.start + p.ALIAS, m.expected())
        m.uc.mem_write(m.start, b'CPU!')
        m.uc.mem_write(m.start + p.ALIAS, b'DMA!')
        self.assertEqual(m.run()[6:], (1, 1))
        self.assertEqual(bytes(m.uc.mem_read(old.MAP, 6)), bytes([1, 0, 1, 0, 1, 0]))

    def test_context_or_cpu_mismatch_refuses_before_upper_access(self):
        for word, value in ((0xEE116F10, 0), (0xEE116F10, 1), (0xEE116F10, 4),
                            (0xEE100F10, 0), (0xEE120F10, 0xC2000000),
                            (0xEE130F10, 1), (0xEE1D0F10, 0x02000000),
                            (0xEE116F10, 0x5007D), (0xEE190F11, 0xC300001D),
                            (0xEE190F31, 0xC300001D)):
            m = CacheMachine(self, 'seed');m.values[word] = value
            self.assertNotEqual(m.run()[2], 0)
            self.assertFalse(m.upper_reads or m.upper_writes or m.events)
        for address, value in ((old.SCREENS, 0), (0xC06B002C, 42), (0xC06B0024, 1), (0xC06B1308, 1)):
            m = CacheMachine(self, 'check');m.uc.mem_write(address, struct.pack('<I', value))
            self.assertNotEqual(m.run()[2], 0)
            self.assertFalse(m.upper_reads or m.upper_writes or m.events)

    def test_foreign_cpu_is_refused_before_tcm_register_reads(self):
        m = CacheMachine(self, 'seed');m.values[0xEE100F10] = 0
        self.assertNotEqual(m.run()[2], 0)
        self.assertEqual(m.tcm_reads, [])

    def test_bad_token_and_ranges_never_write_upper_ram(self):
        m = CacheMachine(self, 'seed');m.run(124)
        self.assertFalse(m.upper_reads or m.upper_writes or m.events)
        for start, end, seed, token in ((old.START - 4096, old.START, 1, 1),
                (old.END - 4096, old.END + 4096, 1, 1), (old.START + 4, old.START + 4096, 1, 1),
                (old.START, old.START + p.CHUNK + 4096, 1, 1), (old.START, old.START, 1, 1),
                (old.START, old.START + 4096, 0, 1), (old.START, old.START + 4096, 1, 0)):
            with self.assertRaises(ValueError):p.build('seed', start, end, seed, token)

    def test_existing_uncached_probe_blobs_remain_identical(self):
        cases = [('fill', old.END, 'd300c7e63ece28e4f3fa67cf6423cfff75a92d5d1cd95c1b16554ab2ef4b44f6'),
                 ('check', old.START + 8192, '2a0cb59e98d303d440912a1e564358b12d380521bae67ba0051698f464a85d98'),
                 ('check', old.START + 224 * 4096, '4478e84cea71c42b2712ca4ef06186bf49b30c84670eec728236896deeef6b70')]
        for operation, end, expected in cases:
            self.assertEqual(hashlib.sha256(old.build(operation, old.START, end, 77)[0]).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
