"""korg.file.frame, count, name and picture on the device: the glue reads picture files over a fake FatFs."""
import json
import pathlib
import struct
import subprocess
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import UNICORN_AVAILABLE
from tools.patch.test_script_card import archive, FS_OPEN, FS_READ, FS_CLOSE
from tools.patch import test_script_hooks as hooks_tests
from tools.patch.script_hooks import MEDIA_END, MEDIA_LIST, MENU_STATE
if UNICORN_AVAILABLE:
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import *

FS_LSEEK = 0xC009E404
FS_OPENDIR, FS_READDIR, FS_CLOSEDIR = 0xC009E660, 0xC009E740, 0xC009E728
GIF = 'Gif/'
MEDIA = 'Media/'

NODE = """
import { readFileSync } from "node:fs";
import { compile } from "./src/script/compiler.mjs";
import { markProbed } from "./src/script/blob.mjs";
import { packGif, readGifFrame } from "./src/script/gif.mjs";
const input = JSON.parse(readFileSync(0, "utf8"));
const out = {};
if (input.compile) { const r = compile(input.compile, { name: "gif" }); if (!r.ok) throw new Error(JSON.stringify(r.errors)); out.block = Buffer.from(markProbed(r.blob)).toString("hex"); }
if (input.pack) out.file = Buffer.from(packGif(input.pack.map(([delay, seed]) => ({ delay, bytes: Uint8Array.from({ length: 1024 }, (_, i) => (i * seed + seed) & 255) })))).toString("hex");
if (input.read) { const [hex, index] = input.read; const slots = new Int32Array(1024).fill(-7); out.result = readGifFrame(hex == null ? undefined : Uint8Array.from(Buffer.from(hex, "hex")), index, slots); out.slots = Array.from(slots); }
process.stdout.write(JSON.stringify(out));
"""

def node(**request):
    return json.loads(subprocess.check_output(['node','--input-type=module','-e',NODE],input=json.dumps(request).encode(),cwd=ROOT))

PLAYER = '''const pic = new Array(1024);
let file = 0;
let index = 0;
let got = 99;
korg.onEvent("buttonPress", (key) => { got = korg.file.frame(pic, file, index); });
'''

def short_names(names):
    """An 8.3 alias per long name, as a FAT writer makes them: the first six letters, ~ and a number, three of the ending."""
    out, taken = {}, set()
    for name in names:
        base, _, ext = name.rpartition('.') if '.' in name.lstrip('.') else (name, '', '')
        stem = ''.join(c for c in base.upper() if c.isascii() and c.isalnum())[:6] or 'X'
        n = 1
        while f'{stem}~{n}.{ext.upper()[:3]}' in taken: n += 1
        out[name] = f'{stem}~{n}.{ext.upper()[:3]}' if ext else f'{stem}~{n}'
        taken.add(out[name])
    return out

class FakeCard:
    """FatFs open (read only), read, seek and close over a dict of paths below SD:KORG/blechtribe/, and the folder walk of
    KORG/blechtribe/Media in the order of the dict: every file there by its long name (Latin-1, as a single byte code page would
    give it) and its 8.3 alias, a file of a sub folder as that folder (attribute 0x10), `hidden` with attribute 2. A file of
    Media/ opens by its alias or its long name."""
    def __init__(self, machine, files, hidden=()):
        self.files, self.handles, self.opened, self.dirs = dict(files), {}, [], {}
        self.hidden = set(hidden)
        uc = machine.uc
        uc.mem_map(0xC009D000, 0x2000)
        for address in (FS_OPEN, FS_READ, FS_CLOSE, FS_LSEEK, FS_OPENDIR, FS_READDIR, FS_CLOSEDIR):
            uc.mem_write(address, struct.pack('<I', 0xE12FFF1E))
        uc.hook_add(UC_HOOK_CODE, self.call, begin=0xC009D000, end=0xC009F000)

    def media(self):
        """[(long name, alias, attribute)] of the folder Media in card order, None without the folder."""
        entries, seen = [], set()
        for path in self.files:
            if not path.startswith(MEDIA): continue
            rest = path[len(MEDIA):]
            if not rest: continue
            name, sub = rest.split('/', 1)[0], '/' in rest
            if name in seen: continue
            seen.add(name)
            entries.append((name, 0x10 if sub else 2 if path in self.hidden else 0x20))
        if not entries and not any(p.rstrip('/') == MEDIA.rstrip('/') for p in self.files): return None
        aliases = short_names([n for n, _ in entries])
        return [(n, aliases[n], a) for n, a in entries]

    def call(self, uc, address, size, _):
        r = lambda n: uc.reg_read(UC_ARM_REG_R0 + n)
        result = 0
        if address == FS_OPEN:
            path = bytes(uc.mem_read(r(1), 80)).split(b'\0')[0].decode()
            name = path[len('SD:KORG/blechtribe/'):] if path.startswith('SD:KORG/blechtribe/') else None
            if name and name.startswith(MEDIA):
                byalias = {MEDIA + alias: MEDIA + long for long, alias, _ in self.media() or []}
                name = byalias.get(name, name)
            self.opened.append(name)
            if name in self.files and r(2) == 1: self.handles[r(0)] = [name, 0]
            else: result = 4
        elif address == FS_OPENDIR:
            path = bytes(uc.mem_read(r(1), 80)).split(b'\0')[0].decode()
            entries = self.media() if path == 'SD:KORG/blechtribe/Media' else None
            if entries is None: result = 5
            else: self.dirs[r(0)] = [entries, 0]
        elif address == FS_READDIR:
            entries, at = self.dirs[r(0)]
            info = r(1)
            lfn, lfsize = struct.unpack('<II', uc.mem_read(info + 0x18, 8))
            if at == len(entries):
                uc.mem_write(info + 9, b'\0')
            else:
                long, alias, attr = entries[at]
                self.dirs[r(0)][1] += 1
                uc.mem_write(info + 8, bytes([attr]) + alias.encode().ljust(13, b'\0'))
                raw = long.encode('latin-1')
                uc.mem_write(lfn, raw + b'\0' if len(raw) < lfsize else b'\0')
        elif address == FS_CLOSEDIR:
            self.dirs.pop(r(0), None)
        elif address == FS_READ:
            name, pos = self.handles[r(0)]
            chunk = self.files[name][pos:pos + r(2)]
            uc.mem_write(r(1), chunk)
            uc.mem_write(r(3), struct.pack('<I', len(chunk)))
            self.handles[r(0)][1] += len(chunk)
        elif address == FS_LSEEK:
            name, _ = self.handles[r(0)]
            if r(1) > len(self.files[name]): result = 2
            else: self.handles[r(0)][1] = r(1)
        elif address == FS_CLOSE:
            self.handles.pop(r(0), None)
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native file tests')
class NativeFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.block = bytes.fromhex(node(compile=PLAYER)['block'])
        cls.gif = bytes.fromhex(node(pack=[[40, 3], [0, 5], [65535, 11]])['file'])

    def machine(self, files):
        m, built = hooks_tests.HookTests().machine()
        m.write(m.runtime + 96, 0xffffffff)
        m.fat = FakeCard(m, {'Plugin/e2sPlugin.all': archive([self.block]), **files})
        m.uc.mem_write(0xC01F7000, b'\xff' * 0x1000)
        m.uc.mem_write(0xC01F8000, b'\xff' * 0x8000)
        m.write(built.symbols['script_api_table'] + built.symbols['API_KORG_FILE_FRAME'] * built.symbols['SCRIPT_API_ENTRY_SIZE'] + 12,
                built.symbols['script_file_frame_glue'])
        m.call('script_card_load', m.runtime)
        m.call('script_frame_run', m.runtime)
        m.entry = m.read(m.runtime)
        self.assertNotEqual(m.entry, 0, 'the player loaded')
        return m

    def ask(self, m, file, index):
        """Set file and index (slots 1024 and 1025, behind the array), press a key, run a frame -> the result and the 1024 slots."""
        vars_at = m.read(m.entry + 8)
        m.write(vars_at + 1024 * 4, file)
        m.write(vars_at + 1025 * 4, index)
        for down in (3, 4):
            m.uc.mem_write(m.input + 0x4000, struct.pack('<4i', down, 3, 0, 0))
            m.call('script_ring_post', m.runtime, m.input + 0x4000)
        m.call('script_frame_run', m.runtime)
        variables = m.variables(m.entry)
        return variables[1026], variables[:1024]

    def test_frames_come_back_exactly_as_the_browser_reads_them(self):
        m = self.machine({GIF + 'GIF07.E2G': self.gif})
        for index in (2, 0, 1, 3):
            got, slots = self.ask(m, 7, index)
            want = node(read=[self.gif.hex(), index])
            self.assertEqual(got, want['result'], f'frame {index}')
            if want['result'] > 0: self.assertEqual(slots, want['slots'], f'frame {index}')
        self.assertEqual(m.fat.opened[-1], GIF + 'GIF07.E2G')
        self.assertEqual(m.fat.handles, {}, 'every open file is closed again')

    def test_missing_short_and_foreign_files_give_minus_one(self):
        cut = self.gif[:8 + 1028 + 500]
        m = self.machine({GIF + 'GIF00.E2G': b'GSCR' + self.gif[4:], GIF + 'GIF12.E2G': cut})
        for file, index in ((5, 0), (0, 0), (12, 1)):
            got, slots = self.ask(m, file, index)
            self.assertEqual(got, -1, f'file {file}')
        self.assertEqual(m.fat.opened[-3:], [GIF + 'GIF05.E2G', GIF + 'GIF00.E2G', GIF + 'GIF12.E2G'])
        self.assertEqual(m.fat.handles, {})

    def test_nothing_is_read_outside_the_main_screen(self):
        m = self.machine({GIF + 'GIF07.E2G': self.gif})
        manager = m.read(0xC03404C0)
        m.write(manager + 0x2c, 3)
        got, slots = self.ask(m, 7, 0)
        self.assertEqual((got, m.fat.opened.count(GIF + 'GIF07.E2G')), (-1, 0))

MEDIA_NODE = """
import { readFileSync } from "node:fs";
import { compile } from "./src/script/compiler.mjs";
import { markProbed } from "./src/script/blob.mjs";
import { encodeBmp } from "./src/splash-bmp.mjs";
import { encodeAnimation } from "./src/loading-anim.mjs";
import { listMedia, mediaNameBytes, readMediaPicture } from "./src/script/media.mjs";
const input = JSON.parse(readFileSync(0, "utf8"));
const out = {};
const hex = b => Buffer.from(b).toString("hex");
if (input.compile) { const r = compile(input.compile, { name: "media" }); if (!r.ok) throw new Error(JSON.stringify(r.errors)); out.block = hex(markProbed(r.blob)); }
if (input.fixtures) {
  const N = 128 * 64;
  const px = new Uint8Array(N); px[0] = 1; px[N - 1] = 1; px[5 * 128 + 9] = 1; for (let x = 20; x < 90; x++) px[40 * 128 + x] = 1;
  const marker = encodeBmp(px);
  const top = marker.slice(); new DataView(top.buffer).setInt32(22, -64, true);
  for (let r = 0; r < 64; r++) top.set(marker.subarray(62 + (63 - r) * 16, 62 + (64 - r) * 16), 62 + r * 16);
  const swapped = marker.slice(); swapped.set([0, 0, 0, 0, 0xff, 0xff, 0xff, 0], 54);
  const deep = marker.slice(); new DataView(deep.buffer).setUint16(28, 24, true);
  const half = marker.slice(); new DataView(half.buffer).setInt32(22, 32, true);
  const wrap = marker.slice(); new DataView(wrap.buffer).setUint32(14, 0xfffffff0, true);
  const low = marker.slice(); new DataView(low.buffer).setUint32(10, 40, true);
  const planes = marker.slice(); planes[27] = 7;
  const pic = seed => Uint8Array.from({ length: 1024 }, (_, i) => ((i * seed) >> 3) & 255);
  const small = () => encodeAnimation({ progress: [pic(1), pic(2), pic(3)], loop: [pic(5), pic(7)], loopFrom: 60 }).bytes;
  const u16 = (b, at) => b[at] | (b[at + 1] << 8);
  const run = small(); const list = u16(run, u16(run, 10) + 2); const head = 1023 | (1 << 10); run[list + 2] = head & 255; run[list + 3] = head >> 8;
  const table = small(); const size = u16(table, 12); table[10] = size & 255; table[11] = size >> 8;
  const blechy = new Uint8Array(readFileSync("assets/blechy/loading.blla"));
  out.files = [
    ["marker.bmp", marker], ["top-down.bmp", top], ["swapped.bmp", swapped], ["deep.BMP", deep], ["half.bmp", half],
    ["cut.bmp", marker.subarray(0, 600)], ["info-wrap.bmp", wrap], ["offset-low.bmp", low], ["planes.bmp", planes],
    ["Caf\u00e9 \u00e0 la carte, long name.bmp", marker], ["a-start-image-of-27-letters.bmp", top], ["notes.txt", marker],
    ["loading.blla", blechy], ["small.blla", small()], ["run.blla", run], ["table.blla", table],
    ["cut.blla", small().subarray(0, 900)], ["UPPER.BLLA", small()], ["marker.bmp.blla", marker],
  ].map(([name, bytes]) => [name, hex(bytes)]);
}
if (input.list) {
  const card = new Map(input.list.map(([path, h]) => ["KORG/blechtribe/" + path, Uint8Array.from(Buffer.from(h, "hex"))]));
  out.lists = [0, 1].map(kind => listMedia(card, kind).map(e => ({ path: e.path.slice("KORG/blechtribe/".length), name: Array.from(mediaNameBytes(e.name)) })));
}
if (input.read) out.reads = input.read.map(([h, kind, frame, reversed]) => {
  const slots = new Int32Array(1024).fill(-7);
  const result = readMediaPicture(h == null ? undefined : Uint8Array.from(Buffer.from(h, "hex")), kind, frame, slots, reversed);
  return { result, slots: Array.from(slots) };
});
process.stdout.write(JSON.stringify(out));
"""

def media_node(**request):
    return json.loads(subprocess.check_output(['node','--input-type=module','-e',MEDIA_NODE],input=json.dumps(request).encode(),cwd=ROOT))

VIEWER = '''const pic = new Array(1024);
const nm = new Array(20);
let op = 0;
let kind = 0;
let index = 0;
let frame = 0;
let got = 99;
korg.onEvent("buttonPress", (key) => {
  if (op == 0) { got = korg.file.count(kind); }
  if (op == 1) { got = korg.file.name(nm, kind, index); }
  if (op == 2) { got = korg.file.picture(pic, kind, index, frame); }
});
'''
OP, KIND, INDEX, FRAME, GOT = 1044, 1045, 1046, 1047, 1048

@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native file tests')
class NativeMediaTests(unittest.TestCase):
    """korg.file.count, name and picture (script_media.s) against src/script/media.mjs."""
    @classmethod
    def setUpClass(cls):
        got = media_node(compile=VIEWER, fixtures=True)
        cls.block = bytes.fromhex(got['block'])
        cls.files = [(MEDIA + name, bytes.fromhex(h)) for name, h in got['files']]

    def machine(self, files, hidden=()):
        m, built = hooks_tests.HookTests().machine()
        m.write(m.runtime + 96, 0xffffffff)
        m.fat = FakeCard(m, {'Plugin/e2sPlugin.all': archive([self.block]), **dict(files)}, hidden)
        m.uc.mem_write(0xC01F7000, b'\xff' * 0x1000)
        m.uc.mem_write(0xC01F8000, b'\xff' * 0x8000)
        m.uc.mem_write(MEDIA_LIST, b'\xff' * (MEDIA_END - MEDIA_LIST))    # FF as in the image: nothing listed, nothing checked
        for name in ('COUNT', 'NAME', 'PICTURE'):
            m.write(built.symbols['script_api_table'] + built.symbols[f'API_KORG_FILE_{name}'] * built.symbols['SCRIPT_API_ENTRY_SIZE'] + 12,
                    built.symbols[f'script_file_{name.lower()}_glue'])
        m.call('script_card_load', m.runtime)
        m.call('script_frame_run', m.runtime)
        m.entry = m.read(m.runtime)
        self.assertNotEqual(m.entry, 0, 'the viewer loaded')
        return m

    def ask(self, m, op, kind=0, index=0, frame=0):
        """Run one call in a key press -> its result and the variables."""
        vars_at = m.read(m.entry + 8)
        for slot, value in ((OP, op), (KIND, kind), (INDEX, index), (FRAME, frame)): m.write(vars_at + slot * 4, value)
        for down in (3, 4):
            m.uc.mem_write(m.input + 0x4000, struct.pack('<4i', down, 3, 0, 0))
            m.call('script_ring_post', m.runtime, m.input + 0x4000)
        m.call('script_frame_run', m.runtime)
        variables = m.variables(m.entry)
        self.assertNotEqual(variables[GOT], 99, 'the handler ran')
        return variables[GOT], variables

    def test_lists_and_names_are_those_of_the_reference(self):
        m = self.machine(self.files + [(MEDIA + 'Sub/inner.bmp', b'x'), (MEDIA + '.dot.bmp', b'x')])
        want = media_node(list=[(path, data.hex()) for path, data in self.files + [(MEDIA + 'Sub/inner.bmp', b'x'), (MEDIA + '.dot.bmp', b'x')]])['lists']
        for kind in (0, 1):
            got, _ = self.ask(m, 0, kind)
            self.assertEqual(got, len(want[kind]), f'kind {kind}')
            for index, entry in enumerate(want[kind]):
                got, v = self.ask(m, 1, kind, index)
                name = entry['name']
                self.assertEqual(got, len(name), entry['path'])
                self.assertEqual(v[1024:1024 + len(name) + 1], name + [0], entry['path'])
            self.assertEqual(self.ask(m, 1, kind, len(want[kind]))[0], 0, 'past the list')
        self.assertEqual(m.fat.dirs, {}, 'the folder is closed again')
        self.assertEqual(m.fat.handles, {})

    def test_pictures_are_those_of_the_reference_in_any_order(self):
        """With the BLECH menu armed and DISPLAY INVERT ON (the display reversed) every bit comes turned, with it OFF or the menu
        not armed (EXIT held at power-on: the controller is never told 0xA7) not, as readMediaPicture's `reversed`."""
        listed = media_node(list=[(path, data.hex()) for path, data in self.files])['lists']
        data = dict(self.files)
        queries = []
        for kind in (0, 1):
            for index, entry in enumerate(listed[kind]):
                frames = [0, 1] if kind == 0 else [0, 1, 2, 4, 3, 1, 5, 0, 100, 99, 50, 101, 60, 200, 2]
                queries += [(kind, index, entry['path'], frame) for frame in frames]
        for armed, invert in ((1, 1), (1, 0), (0, 1)):
            m = self.machine(self.files)
            m.uc.mem_write(MENU_STATE, bytes(0x200))      # an armed menu with FF in its other words runs off in the frame
            m.write(MENU_STATE, armed)
            m.write(MENU_STATE + 0x1B8, invert)
            for kind in (0, 1):
                self.assertEqual(self.ask(m, 0, kind)[0], len(listed[kind]))
            reversed_ = armed == 1 and invert == 1
            want = media_node(read=[(data[path].hex(), kind, frame, reversed_) for kind, index, path, frame in queries])['reads']
            slots = None
            for (kind, index, path, frame), expect in zip(queries, want):
                got, v = self.ask(m, 2, kind, index, frame)
                self.assertEqual(got, expect['result'], f'{path} picture {frame}, menu {armed} invert {invert}')
                if expect['result'] > 0: slots = expect['slots']
                if slots is not None: self.assertEqual(v[:1024], slots, f'{path} picture {frame}, menu {armed} invert {invert}')
            self.assertEqual(m.fat.handles, {}, 'every open file is closed again')

    def test_nothing_listed_a_file_gone_or_no_folder(self):
        m = self.machine(self.files)
        self.assertEqual(self.ask(m, 1, 0, 0)[0], 0, 'FF at power-on lists nothing')
        self.assertEqual(self.ask(m, 2, 1, 0, 0)[0], -1)
        self.assertEqual(m.fat.opened.count(None) + sum(1 for p in m.fat.opened if p and p.startswith(MEDIA)), 0, 'no file opened')
        listed = media_node(list=[(path, data.hex()) for path, data in self.files])['lists']
        self.assertEqual(self.ask(m, 0, 1)[0], len(listed[1]))
        self.assertEqual(listed[1][0]['path'], MEDIA + 'loading.blla')
        self.assertGreater(self.ask(m, 2, 1, 0, 3)[0], 4)
        del m.fat.files[MEDIA + 'loading.blla']
        self.assertEqual(self.ask(m, 2, 1, 0, 4)[0], -1, 'the file went after the count')
        empty = self.machine([('Other/a.bmp', b'x')])
        self.assertEqual(self.ask(empty, 0, 0)[0], 0, 'no Media folder')
        self.assertEqual(self.ask(empty, 2, 0, 0, 0)[0], -1)

    def test_at_most_64_files_of_a_kind(self):
        many = [(MEDIA + f'p{i}.bmp', self.files[0][1]) for i in range(70)]
        m = self.machine(many)
        self.assertEqual(self.ask(m, 0, 0)[0], 64)
        got, v = self.ask(m, 1, 0, 63)
        self.assertEqual((got, v[1024:1028]), (3, [ord('p'), ord('6'), ord('3'), 0]))
        self.assertEqual(self.ask(m, 2, 0, 63, 0)[0], 1)
        self.assertEqual(m.fat.opened[-1], MEDIA + 'p63.bmp')

    def test_a_hidden_file_is_left_out_as_in_the_menu(self):
        m = self.machine(self.files[:2], hidden={self.files[0][0]})
        self.assertEqual(self.ask(m, 0, 0)[0], 1)
        self.assertEqual(self.ask(m, 1, 0, 0)[1][1024:1033], [ord(c) for c in 'top-down'] + [0])

    def test_nothing_is_read_outside_the_main_screen(self):
        m = self.machine(self.files)
        listed = media_node(list=[(path, data.hex()) for path, data in self.files])['lists']
        self.assertEqual(self.ask(m, 0, 0)[0], len(listed[0]))
        manager = m.read(0xC03404C0)
        m.write(manager + 0x2c, 3)
        opened = len(m.fat.opened)
        self.assertEqual(self.ask(m, 0, 0)[0], -1)
        self.assertEqual(self.ask(m, 2, 0, 0, 0)[0], -1)
        self.assertEqual(len(m.fat.opened), opened)
        self.assertEqual(self.ask(m, 1, 0, 0)[0], len(listed[0][0]['name']), 'the list stays')

if __name__ == '__main__':
    unittest.main()
