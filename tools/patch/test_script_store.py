"""Persistent script values: glue, store file read and write, over a fake FatFs without firmware bytes."""
import json
import pathlib
import struct
import subprocess
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import contract_data, UNICORN_AVAILABLE
from tools.patch import test_script_hooks as hooks_tests
from tools.patch.test_script_card import archive, FS_OPEN, FS_READ, FS_CLOSE
if UNICORN_AVAILABLE:
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import *

FS_WRITE = 0xC009DFB8
FOLDER = b'SD:KORG/blechtribe/Plugin/'
STORE_PENDING, STORE_FRAME, STORE_GENERATION, STORE_BYTES, STORE_ERRORS, STORE_WRITES = 184, 188, 192, 196, 200, 204
ENTRY_MASK, ENTRY_STORE = 224, 228

NODE = """
import { readFileSync } from "node:fs";
import { compile } from "./src/script/compiler.mjs";
import { markProbed } from "./src/script/blob.mjs";
import { buildStore, parseStore } from "./src/script/store.mjs";
const input = JSON.parse(readFileSync(0, "utf8"));
const out = {};
if (input.compile) out.blocks = input.compile.map(([name, source]) => { const r = compile(source, { name }); if (!r.ok) throw new Error(JSON.stringify(r.errors)); return Buffer.from(markProbed(r.blob)).toString("hex"); });
if (input.build) out.built = input.build.map(s => Buffer.from(buildStore(s)).toString("hex"));
if (input.parse) out.parsed = input.parse.map(h => { const p = parseStore(Uint8Array.from(Buffer.from(h, "hex"))); return p.ok ? { ok: true, generation: p.generation, records: p.records.map(r => ({ name: r.name, mask: r.mask, values: Array.from(r.values) })) } : p; });
process.stdout.write(JSON.stringify(out));
"""

def node(**request):
    return json.loads(subprocess.check_output(['node','--input-type=module','-e',NODE],input=json.dumps(request).encode(),cwd=ROOT))

KLICKER = (ROOT/'test/fixtures/scripts/klicker-store.js').read_text()

class FakeCard:
    """FatFs entry points over a dict of files. Mode 1 reads, 0x0A creates or replaces."""
    def __init__(self, machine, files):
        self.m, self.files, self.handles, self.fail_open_write = machine, dict(files), {}, False
        self.opened = []
        uc = machine.uc
        uc.mem_map(0xC009D000, 0x2000)
        for address in (FS_OPEN, FS_READ, FS_WRITE, FS_CLOSE):
            uc.mem_write(address, struct.pack('<I', 0xE12FFF1E))
        uc.hook_add(UC_HOOK_CODE, self.call, begin=0xC009D000, end=0xC009F000)

    def call(self, uc, address, size, _):
        r = lambda n: uc.reg_read(UC_ARM_REG_R0 + n)
        result = 0
        if address == FS_OPEN:
            path = bytes(uc.mem_read(r(1), 80)).split(b'\0')[0]
            name = path[len(FOLDER):].decode() if path.startswith(FOLDER) else None
            self.opened.append((name, r(2)))
            if name is None: result = 4
            elif r(2) == 1:
                if name in self.files: self.handles[r(0)] = [name, 0, 'r']
                else: result = 4
            elif r(2) == 0x0A:
                if self.fail_open_write: result = 9
                else:
                    self.files[name] = b''
                    self.handles[r(0)] = [name, 0, 'w']
            else: result = 7
        elif address == FS_READ:
            name, pos, _ = self.handles[r(0)]
            chunk = self.files[name][pos:pos + r(2)]
            uc.mem_write(r(1), chunk)
            uc.mem_write(r(3), struct.pack('<I', len(chunk)))
            self.handles[r(0)][1] += len(chunk)
        elif address == FS_WRITE:
            data = bytes(uc.mem_read(r(1), r(2)))
            self.files[self.handles[r(0)][0]] += data
            uc.mem_write(r(3), struct.pack('<I', len(data)))
        elif address == FS_CLOSE:
            self.handles.pop(r(0), None)
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native store tests')
class NativeStoreTests(unittest.TestCase):
    def machine(self, files, scripts=None, builtin=False):
        m, built = hooks_tests.HookTests().machine()
        m.write(m.runtime + 96, 0xffffffff)
        m.fat = FakeCard(m, files)
        table = built.symbols['script_api_table']
        size = built.symbols['SCRIPT_API_ENTRY_SIZE']
        for api, label in [('API_KORG_STORE_GET', 'get'), ('API_KORG_STORE_SET', 'set'), ('API_KORG_STORE_SAVE', 'save')]:
            m.write(table + built.symbols[api] * size + 12, built.symbols['script_store_' + label + '_glue'])
        m.uc.mem_write(0xC01F7000, b'\xff' * 0x1000)
        m.uc.mem_write(0xC01F8000, b'\xff' * 0x8000)
        if builtin:
            from tools.patch.script_hooks import MENU_STATE
            m.uc.mem_write(MENU_STATE, bytes(0x200))
            for offset in (0, 16, 20, 24, 28): m.write(MENU_STATE + offset, 1)
            self.assertEqual(m.call('blechy_boot', m.runtime)[0], 1)
        m.call('script_card_load', m.runtime)
        return m

    def frame(self, m, n=1):
        for _ in range(n): m.call('script_frame_run', m.runtime)

    def press(self, m, key=3):
        for down in (3, 4):
            m.uc.mem_write(m.input + 0x4000, struct.pack('<4i', down, key, 0, 0))
            m.call('script_ring_post', m.runtime, m.input + 0x4000)

    def entry(self, m, index=0):
        entry = m.read(m.runtime)
        for _ in range(index): entry = m.read(entry)
        return entry

    def store_of(self, m, entry):
        return m.read(entry + ENTRY_MASK), list(struct.unpack('<16i', m.uc.mem_read(entry + ENTRY_STORE, 64)))

    def counter_machine(self, files=None):
        blocks = node(compile=[['klicker', KLICKER]])['blocks']
        files = dict(files or {})
        files['e2sPlugin.all'] = archive([bytes.fromhex(blocks[0])])
        return self.machine(files)

    def test_get_returns_the_fallback_until_a_slot_is_set_and_slots_belong_to_their_script(self):
        a = 'let seen = korg.store.get(2, 55);\nlet after = 0;\nkorg.onEvent("buttonPress", (k) => { korg.store.set(2, 7); after = korg.store.get(2, 55); });'
        b = 'let mine = korg.store.get(2, -4);\nkorg.onEvent("buttonPress", (k) => { korg.store.set(5, 1); });'
        blocks = node(compile=[['one', a], ['two', b]])['blocks']
        m = self.machine({'e2sPlugin.all': archive([bytes.fromhex(h) for h in blocks])})
        one, two = self.entry(m), self.entry(m, 1)
        self.assertEqual(m.variables(one)[:2], [55, 0])
        self.assertEqual(m.variables(two)[0], -4)
        self.frame(m)
        self.press(m)
        self.frame(m)
        self.assertEqual(m.variables(one)[:2], [55, 7])
        self.assertEqual(self.store_of(m, one)[0], 1 << 2)
        self.assertEqual(self.store_of(m, two)[0], 1 << 5)
        self.assertEqual(self.store_of(m, two)[1][2], 0)

    def test_save_writes_the_image_into_the_alternating_files_exactly_as_the_browser_builds_it(self):
        m = self.counter_machine()
        self.frame(m)
        self.assertNotIn('store.a.bin', m.fat.files)
        self.press(m); self.frame(m)
        self.assertEqual(m.read(m.runtime + STORE_WRITES), 1)
        self.assertEqual(set(m.fat.files) - {'e2sPlugin.all'}, {'store.b.bin'})
        want = node(build=[dict(generation=1, records=[dict(name='klicker', mask=1, values=[1])])])['built'][0]
        self.assertEqual(m.fat.files['store.b.bin'].hex(), want)
        self.assertEqual(m.read(m.runtime + STORE_PENDING), 0)
        self.assertEqual(m.read(m.runtime + STORE_GENERATION), 1)
        self.press(m); self.frame(m, 49)
        self.assertEqual(m.read(m.runtime + STORE_WRITES), 1, 'the pause between two writes holds it back')
        self.assertEqual(m.read(m.runtime + STORE_PENDING), 1)
        self.frame(m, 2)
        self.assertEqual(m.read(m.runtime + STORE_WRITES), 2)
        self.assertIn('store.a.bin', m.fat.files)
        parsed = node(parse=[m.fat.files['store.a.bin'].hex()])['parsed'][0]
        self.assertEqual((parsed['generation'], parsed['records'][0]['name'], parsed['records'][0]['values'][0]), (2, 'klicker', 2))

    def test_the_count_comes_back_after_a_restart_from_the_newer_valid_file(self):
        first = self.counter_machine()
        self.frame(first)
        for _ in range(3):
            self.press(first); self.frame(first, 55)
        files = {k: v for k, v in first.fat.files.items()}
        self.assertEqual(first.read(first.runtime + STORE_WRITES), 3)
        second = self.machine(files)
        self.assertEqual(second.variables(self.entry(second))[0], 3)
        self.assertEqual(second.read(second.runtime + STORE_GENERATION), 3)
        broken = dict(files)
        newest = 'store.b.bin' if 3 & 1 else 'store.a.bin'
        broken[newest] = bytes([broken[newest][0] ^ 1]) + broken[newest][1:]
        third = self.machine(broken)
        self.assertEqual(third.variables(self.entry(third))[0], 2, 'a damaged newest file falls back to the older generation')
        for name in ('store.a.bin', 'store.b.bin'): broken[name] = broken[name][:20]
        fourth = self.machine(broken)
        self.assertEqual(fourth.variables(self.entry(fourth))[0], 0, 'without a valid file the defaults hold')
        self.assertEqual(self.store_of(fourth, self.entry(fourth))[0], 0)

    def test_other_scripts_records_survive_and_new_ones_are_appended(self):
        old = node(build=[dict(generation=9, records=[dict(name='abwesend', mask=3, values=[5, 6]), dict(name='klicker', mask=1, values=[40])])])['built'][0]
        m = self.counter_machine({'store.a.bin': bytes.fromhex(old)})
        self.assertEqual(m.variables(self.entry(m))[0], 40)
        self.assertEqual(m.read(m.runtime + STORE_GENERATION), 9)
        self.frame(m); self.press(m); self.frame(m)
        self.assertEqual(m.read(m.runtime + STORE_GENERATION), 10)
        parsed = node(parse=[m.fat.files['store.a.bin'].hex()])['parsed'][0]
        self.assertEqual(parsed['generation'], 10)
        self.assertEqual([(r['name'], r['mask'], r['values'][0]) for r in parsed['records']], [('abwesend', 3, 5), ('klicker', 1, 41)])

    def test_a_write_only_happens_with_the_main_screen_open_and_a_failure_is_counted_not_repeated(self):
        m = self.counter_machine()
        self.frame(m)
        manager = m.read(0xC03404C0)
        m.write(manager + 0x2c, 3)
        self.press(m); self.frame(m, 5)
        self.assertEqual((m.read(m.runtime + STORE_WRITES), m.read(m.runtime + STORE_PENDING)), (0, 1))
        m.write(manager + 0x2c, 1)
        m.fat.fail_open_write = True
        self.frame(m)
        self.assertEqual((m.read(m.runtime + STORE_WRITES), m.read(m.runtime + STORE_ERRORS), m.read(m.runtime + STORE_PENDING)), (0, 1, 0))
        self.frame(m, 60)
        self.assertEqual(m.read(m.runtime + STORE_ERRORS), 1)

    def test_the_built_in_app_gets_no_record_and_the_card_loads_behind_him(self):
        blocks = node(compile=[['klicker', KLICKER]])['blocks']
        m = self.machine({'e2sPlugin.all': archive([bytes.fromhex(blocks[0])])}, builtin=True)
        him = m.read(m.runtime)
        self.assertEqual(m.read(m.runtime + 164), 1, 'the card file loaded')
        self.assertEqual(m.read(m.runtime + 168), 1, 'one plugin of the card')
        plugin = m.read(him)
        self.assertEqual((m.read(him + 4) < m.arena, m.read(plugin + 4) > m.arena), (True, True), 'his block is outside the pool, the plugin is in it')
        self.assertEqual(m.read(plugin + 12), 2)
        self.frame(m)
        self.press(m); self.frame(m)
        parsed = node(parse=[m.fat.files['store.b.bin'].hex()])['parsed'][0]
        self.assertEqual([r['name'] for r in parsed['records']], ['klicker'], 'the store knows his plugin only')

    def test_a_slot_outside_the_range_is_an_argument_error(self):
        m = self.counter_machine()
        entry = self.entry(m)
        m.write(m.runtime + 88, entry)
        self.assertEqual(m.call('script_store_get_glue', 16, 5), (0, contract_data()['error']['API_ARG']))
        self.assertEqual(m.call('script_store_set_glue', 99, 5), (0, contract_data()['error']['API_ARG']))
        self.assertEqual(m.call('script_store_get_glue', 0, 5), (5, 0))

    def test_the_store_paths_are_the_contract_paths(self):
        import re
        source = (ROOT / 'tools/patch/script_store.s').read_text()
        paths = re.findall(r'\.asciz "([^"]+)"', source)
        self.assertEqual(paths, ['SD:KORG/blechtribe/Plugin/store.a.bin', 'SD:KORG/blechtribe/Plugin/store.b.bin'])

if __name__ == '__main__':
    unittest.main()
