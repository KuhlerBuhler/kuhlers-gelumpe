"""Boot loader for e2sPlugin.all over a fake FatFs, without firmware bytes."""
import pathlib
import struct
import sys
import unittest
import zlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import contract_data, blob, UNICORN_AVAILABLE
from tools.patch import test_script_hooks as hooks_tests
if UNICORN_AVAILABLE:
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import *

FS_OPEN, FS_READ, FS_CLOSE = 0xC009DB60, 0xC009DD74, 0xC009E3DC
PATH = b'SD:KORG/blechtribe/Plugin/e2sPlugin.all'
OK, NO_FILE, BAD_HEADER, BAD_CHECKSUM, READ_ERROR, BLOCK_SIZE, KILL_SWITCH, NO_PANEL = 1, 2, 3, 4, 5, 6, 7, 8
STATUS, LOADED, REJECTED, FIRST = 164, 168, 172, 176

def archive(blocks, count=None, total=None, version=1, magic=b'GSAL'):
    body = b''.join(blocks)
    size = 16 + len(body) if total is None else total
    head = struct.pack('<4sHHII', magic, version, len(blocks) if count is None else count, size, zlib.crc32(body))
    return head + body

def store(slot, value):
    """A start body that stores a constant: PUSHB value, STORE slot, HALT."""
    return blob([1, value, 5, slot & 255, slot >> 8, 0], vars=slot + 1, stack=1, flags=1)

def crash():
    """A start body that divides by zero."""
    return blob([1, 1, 1, 0, 13, 9, 0], vars=1, stack=2, flags=1)

class FakeFat:
    """FatFs entry points answered from Python: one file, optional faults."""
    def __init__(self, machine, data=None, fail_read_after=None):
        self.m, self.data, self.pos = machine, data, 0
        self.opened, self.closed, self.reads, self.paths = 0, 0, [], []
        self.fail_read_after = fail_read_after
        uc = machine.uc
        uc.mem_map(0xC009D000, 0x2000)
        for address in (FS_OPEN, FS_READ, FS_CLOSE):
            uc.mem_write(address, struct.pack('<I', 0xE12FFF1E))
        uc.hook_add(UC_HOOK_CODE, self.call, begin=0xC009D000, end=0xC009F000)

    def call(self, uc, address, size, _):
        r = lambda n: uc.reg_read(UC_ARM_REG_R0 + n)
        result = 0
        if address == FS_OPEN:
            path = bytes(uc.mem_read(r(1), len(PATH) + 1))
            self.paths.append(path.split(b'\0')[0])
            self.opened += 1
            if self.data is None or path != PATH + b'\0' or r(2) != 1:
                result = 4
            else:
                self.pos = 0
        elif address == FS_READ:
            want, got = r(2), 0
            self.reads.append(want)
            if self.fail_read_after is not None and len(self.reads) > self.fail_read_after:
                result = 1
            else:
                chunk = self.data[self.pos:self.pos + want]
                uc.mem_write(r(1), chunk)
                self.pos += len(chunk)
                got = len(chunk)
            uc.mem_write(r(3), struct.pack('<I', got))
        elif address == FS_CLOSE:
            self.closed += 1
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native card loader tests')
class NativeCardTests(unittest.TestCase):
    def machine(self, data=None, **fat):
        m, built = hooks_tests.HookTests().machine()
        m.call('script_runtime_init', m.runtime, m.arena, 131072)
        m.write(m.runtime + 96, 0xffffffff)
        for offset in range(STATUS, STATUS + 16, 4): m.write(m.runtime + offset, 0xffffffff)
        m.fat = FakeFat(m, data, **fat)
        m.uc.mem_write(0xC01F7000, b'\xff' * 0x1000)
        return m, built

    def load(self, m):
        return m.call('script_card_load', m.runtime)[0]

    def words(self, m):
        return [m.read(m.runtime + o) for o in (STATUS, LOADED, REJECTED, FIRST)]

    def test_two_blocks_load_their_start_bodies_run_and_the_runtime_arms(self):
        a, b = store(0, 7), store(1, 9)
        m, _ = self.machine(archive([a, b]))
        self.load(m)
        self.assertEqual(self.words(m), [OK, 2, 0, 0])
        self.assertEqual(m.read(m.runtime + 96), 1)
        first = m.read(m.runtime)
        second = m.read(first)
        self.assertEqual(m.variables(first), [7])
        self.assertEqual(m.variables(second), [0, 9])
        self.assertEqual((m.read(first + 12), m.read(second + 12)), (2, 2))
        self.assertEqual((m.fat.opened, m.fat.closed), (3, 1), 'the collection, then the two store files, which are not there')
        self.assertEqual(m.fat.paths, [PATH, PATH.replace(b'e2sPlugin.all', b'store.a.bin'), PATH.replace(b'e2sPlugin.all', b'store.b.bin')])
        self.assertEqual(m.fat.reads, [16, 52, len(a) - 52, 52, len(b) - 52])

    def test_a_block_that_fails_is_rejected_alone_and_the_first_error_is_kept(self):
        bad = bytearray(store(0, 1)); bad[52] ^= 1
        m, _ = self.machine(archive([bytes(bad), store(0, 5), bytes(bad)]))
        self.load(m)
        self.assertEqual(self.words(m), [OK, 1, 2, contract_data()['error']['CHECKSUM']])
        self.assertEqual(m.read(m.runtime + 96), 1)
        self.assertEqual(m.variables(m.read(m.runtime)), [5])

    def test_a_failing_start_body_disables_only_that_script(self):
        m, _ = self.machine(archive([crash(), store(0, 4)]))
        self.load(m)
        first = m.read(m.runtime)
        self.assertEqual(self.words(m), [OK, 2, 0, 0])
        self.assertEqual(m.read(first + 12), 3)
        self.assertEqual(m.read(first + 16), contract_data()['error']['DIV_ZERO'])
        self.assertEqual(m.read(m.read(first) + 12), 2)
        self.assertEqual(m.read(m.runtime + 96), 1)

    def test_an_empty_collection_loads_and_leaves_the_runtime_unarmed(self):
        m, _ = self.machine(archive([]))
        self.load(m)
        self.assertEqual(self.words(m), [OK, 0, 0, 0])
        self.assertEqual(m.read(m.runtime + 96), 0)

    def test_no_file_changes_nothing_but_the_status(self):
        m, _ = self.machine(None)
        self.load(m)
        self.assertEqual(self.words(m), [NO_FILE, 0, 0, 0])
        self.assertEqual(m.read(m.runtime + 96), 0xffffffff)
        self.assertEqual((m.fat.opened, m.fat.closed, m.fat.reads), (1, 0, []))

    def test_kill_switch_and_missing_panel_never_touch_the_card(self):
        for name, setup, status in [('exit', lambda m: m.write(m.input + 0x1018, 0x2000), KILL_SWITCH),
                                    ('no panel', lambda m: m.write(0xC033E6F8, 0), NO_PANEL),
                                    ('bad panel', lambda m: m.write(0xC033E6F8, 0xffffffff), NO_PANEL)]:
            with self.subTest(name):
                m, _ = self.machine(archive([store(0, 1)]))
                setup(m)
                self.load(m)
                self.assertEqual(self.words(m), [status, 0, 0, 0])
                self.assertEqual((m.fat.opened, m.fat.closed), (0, 0))
                self.assertEqual(m.read(m.runtime + 96), 0xffffffff)

    def test_a_damaged_file_is_rejected_as_a_whole_and_the_file_is_closed(self):
        good = archive([store(0, 1), store(1, 2)])
        wrong_crc = bytearray(good); wrong_crc[12] ^= 1
        cases = [
            ('magic', archive([store(0, 1)], magic=b'GSAX'), BAD_HEADER),
            ('version', archive([store(0, 1)], version=2), BAD_HEADER),
            ('crc', bytes(wrong_crc), BAD_CHECKSUM),
            ('total too small', archive([store(0, 1)], total=20), BAD_HEADER),
            ('total too large', archive([store(0, 1)], total=500), BAD_HEADER),
            ('count too large', archive([store(0, 1)], count=2), READ_ERROR),
            ('truncated', good[:-8], READ_ERROR),
            ('header only 10 bytes', good[:10], READ_ERROR),
        ]
        for name, data, status in cases:
            with self.subTest(name):
                m, _ = self.machine(data)
                self.load(m)
                self.assertEqual(self.words(m)[0], status)
                self.assertEqual(m.read(m.runtime + 96), 0)
                self.assertEqual(m.read(m.runtime), 0)
                self.assertEqual((m.fat.opened, m.fat.closed), (1, 1))

    def test_block_sizes_outside_what_the_loader_accepts_are_refused_before_they_are_read(self):
        for name, size in [('under header', 40), ('not a multiple of 4', 102), ('over buffer', 32756)]:
            with self.subTest(name):
                block = bytearray(store(0, 1)); struct.pack_into('<I', block, 8, size)
                m, _ = self.machine(archive([bytes(block)]))
                self.load(m)
                self.assertEqual(self.words(m)[0], BLOCK_SIZE)
                self.assertEqual(m.fat.reads, [16, 52])
                self.assertEqual((m.fat.opened, m.fat.closed), (1, 1))

    def test_a_read_error_part_way_resets_the_runtime_and_closes_the_file(self):
        for after in range(0, 4):
            with self.subTest(after=after):
                m, _ = self.machine(archive([store(0, 1), store(1, 2)]), fail_read_after=after)
                self.load(m)
                self.assertEqual(self.words(m), [READ_ERROR, 0, 0, 0])
                self.assertEqual((m.read(m.runtime + 96), m.read(m.runtime)), (0, 0))
                self.assertEqual((m.fat.opened, m.fat.closed), (1, 1))

    def test_pool_budget_overflow_rejects_the_block_that_does_not_fit(self):
        big = store(16000, 1)
        m, _ = self.machine(archive([big, big, big]))
        self.load(m)
        self.assertEqual(self.words(m)[:3], [OK, 2, 1])
        self.assertIn(self.words(m)[3], (contract_data()['error']['VARS_BUDGET'], contract_data()['error']['POOL_BUDGET']))

    def test_wrapper_keeps_registers_and_flags_runs_the_displaced_instruction_and_continues(self):
        for cpsr in (0xA0000013, 0x40000013, 0x60000013):
            with self.subTest(cpsr=hex(cpsr)):
                m, _ = self.machine(archive([store(0, 7)]))
                regs = [0x12340000 + i for i in range(13)]
                for i, value in enumerate(regs): m.uc.reg_write(UC_ARM_REG_R0 + i, value)
                sp = m.stack + 0xF0000
                m.uc.reg_write(UC_ARM_REG_SP, sp)
                m.uc.reg_write(UC_ARM_REG_LR, 0x12345678)
                m.uc.reg_write(UC_ARM_REG_CPSR, cpsr)
                m.uc.mem_map(0xC0038000, 0x1000)
                m.uc.emu_start(m.symbols["script_card_hook"], 0xC0038D6C, count=20000000)  # the wrapper also boots the built-in app now: about 5.5 million instructions
                self.assertEqual(m.uc.reg_read(UC_ARM_REG_PC), 0xC0038D6C)
                self.assertEqual(m.uc.reg_read(UC_ARM_REG_CPSR), cpsr)
                self.assertEqual(m.uc.reg_read(UC_ARM_REG_SP), sp)
                self.assertEqual(m.uc.reg_read(UC_ARM_REG_LR), 0x12345678)
                self.assertEqual([m.uc.reg_read(UC_ARM_REG_R0 + i) for i in range(1, 13)], regs[1:])
                self.assertEqual(m.uc.reg_read(UC_ARM_REG_R0), sp + 4)
                self.assertEqual(self.words(m)[:2], [OK, 1])

    def booted(self, data, **fat):
        """The machine with the menu armed and Blechy loaded, as the card hook wrapper leaves it before the loader runs."""
        from tools.patch.script_hooks import MENU_STATE
        m, built = self.machine(data, **fat)
        m.uc.mem_write(MENU_STATE, bytes(0x200))
        for offset in (0, 16, 20, 24, 28): m.write(MENU_STATE + offset, 1)
        m.write(m.runtime + 96, 0xffffffff)
        self.assertEqual(m.call('blechy_boot', m.runtime)[0], 1)
        return m, built

    def test_the_card_loads_behind_the_built_in_app_and_without_a_file_he_stays_armed(self):
        m, _ = self.booted(archive([store(0, 7)]))
        him = m.read(m.runtime)
        self.load(m)
        self.assertEqual(self.words(m), [OK, 1, 0, 0])
        self.assertEqual(m.read(m.runtime), him, 'the list still starts with him')
        plugin = m.read(him)
        self.assertEqual((m.variables(plugin), m.read(plugin + 12), m.read(m.runtime + 96)), ([7], 2, 1))
        none, _ = self.booted(None)
        self.load(none)
        self.assertEqual(self.words(none), [NO_FILE, 0, 0, 0])
        self.assertEqual((none.read(none.read(none.runtime) + 12), none.read(none.runtime + 96)), (2, 1), 'no card file: he is armed on his own')
        empty, _ = self.booted(archive([]))
        self.load(empty)
        self.assertEqual((self.words(empty), empty.read(empty.runtime + 96)), ([OK, 0, 0, 0], 1), 'an empty collection leaves him armed')

    def test_a_damaged_file_throws_away_the_plugins_but_not_him(self):
        good = archive([store(0, 1), store(1, 2)])
        wrong_crc = bytearray(good); wrong_crc[12] ^= 1
        for name, data, status in [('crc', bytes(wrong_crc), BAD_CHECKSUM), ('magic', archive([store(0, 1)], magic=b'GSAX'), BAD_HEADER), ('truncated', good[:-8], READ_ERROR)]:
            with self.subTest(name):
                m, _ = self.booted(data)
                self.load(m)
                self.assertEqual(self.words(m)[0], status)
                him = m.read(m.runtime)
                self.assertNotIn(him, (0, 0xffffffff))
                self.assertEqual((m.read(him), m.read(m.runtime + 4), m.read(him + 12), m.read(m.runtime + 96)), (0, him, 2, 1), 'the runtime starts over with him alone')
                self.assertEqual((m.fat.opened, m.fat.closed), (1, 1))

    def test_the_path_is_the_contract_path_and_the_scratch_area_sits_between_pool_and_buffer(self):
        c = contract_data()
        m, built = self.machine(None)
        self.assertEqual(built.layout['poolEnd'], 0xC01F7000)
        source = (ROOT / 'tools/patch/script_card.s').read_text()
        import re
        path = re.search(r'\.asciz "([^"]+)"', source).group(1)
        self.assertEqual(path.encode(), PATH)
        self.assertLess(0xC01F7000 + 64 + 0x280, 0xC01F8000)

if __name__ == '__main__':
    unittest.main()
