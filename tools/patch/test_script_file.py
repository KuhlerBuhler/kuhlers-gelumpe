"""korg.file.frame on the device: the glue reads a frame of a picture file over a fake FatFs, without firmware bytes."""
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
if UNICORN_AVAILABLE:
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import *

FS_LSEEK = 0xC009E404
GIF = 'Gif/'

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

class FakeCard:
    """FatFs open (read only), read, seek and close over a dict of paths below SD:KORG/blechtribe/."""
    def __init__(self, machine, files):
        self.files, self.handles, self.opened = dict(files), {}, []
        uc = machine.uc
        uc.mem_map(0xC009D000, 0x2000)
        for address in (FS_OPEN, FS_READ, FS_CLOSE, FS_LSEEK):
            uc.mem_write(address, struct.pack('<I', 0xE12FFF1E))
        uc.hook_add(UC_HOOK_CODE, self.call, begin=0xC009D000, end=0xC009F000)

    def call(self, uc, address, size, _):
        r = lambda n: uc.reg_read(UC_ARM_REG_R0 + n)
        result = 0
        if address == FS_OPEN:
            path = bytes(uc.mem_read(r(1), 80)).split(b'\0')[0].decode()
            name = path[len('SD:KORG/blechtribe/'):] if path.startswith('SD:KORG/blechtribe/') else None
            self.opened.append(name)
            if name in self.files and r(2) == 1: self.handles[r(0)] = [name, 0]
            else: result = 4
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

if __name__ == '__main__':
    unittest.main()
