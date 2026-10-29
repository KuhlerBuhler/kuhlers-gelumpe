"""loading_anim.py against files from the JS encoder (src/loading-anim.mjs); needs node."""
import json
import pathlib
import shutil
import struct
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/patch"))
import loading_anim  # noqa: E402

# Moving blocks as progress, a small spinner as loop; prints the file and the pictures as hex.
SCRIPT = """
import { encodeAnimation } from "./src/loading-anim.mjs";
const hex = b => Buffer.from(b).toString("hex");
const block = k => { const f = new Uint8Array(1024); for (let p = 0; p < 8; p++) f.fill(0x30 + k, p * 128 + (k * 24) % 112, p * 128 + (k * 24) % 112 + 16); return f; };
const spin = j => { const f = new Uint8Array(1024); f[1016 + j] = 0xff; return f; };
const frames = { progress: Array.from({ length: 9 }, (_, k) => block(k)), loop: [0, 1, 2].map(spin) };
const late = { ...frames, loop: [0, 1].map(j => { const f = block(6); f[1020 + j] = 0x77; return f; }), loopFrom: 75 };
console.log(JSON.stringify({ file: hex(encodeAnimation(frames).bytes), progress: frames.progress.map(hex), loop: frames.loop.map(hex),
                             late: hex(encodeAnimation(late).bytes), lateLoop: late.loop.map(hex) }));
"""


@unittest.skipUnless(shutil.which("node"), "node is needed for the encoder")
class LoadingAnim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", "--input-type=module", "-e", SCRIPT], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout
        cls.data = json.loads(out)
        cls.blob = bytes.fromhex(cls.data["file"])

    def test_decodes_every_picture(self):
        self.assertIsNone(loading_anim.validate(self.blob))
        progress, loop = loading_anim.decode(self.blob)
        self.assertEqual([p.hex() for p in progress], self.data["progress"])
        self.assertEqual([p.hex() for p in loop], self.data["loop"])

    def test_loop_from_a_percent(self):
        late = bytes.fromhex(self.data["late"])
        self.assertIsNone(loading_anim.validate(late))
        self.assertEqual(loading_anim.loop_from(late), 75)
        _, loop = loading_anim.decode(late)
        self.assertEqual([p.hex() for p in loop], self.data["lateLoop"])
        bad = bytearray(late)
        bad[5] = 101
        self.assertEqual(loading_anim.validate(bytes(bad)), "loop from 101 percent")

    def test_picture_by_index_and_loop(self):
        progress, loop = loading_anim.decode(self.blob)
        self.assertEqual(loading_anim.picture(self.blob, 4), progress[4])
        over = bytearray(progress[7])
        for i, (a, b) in enumerate(zip(progress[0], loop[2])):
            if a != b:
                over[i] = b
        self.assertEqual(loading_anim.picture(self.blob, 7, 2), bytes(over))
        self.assertEqual([loading_anim.progress_index(101, f) for f in (0, 999, 1000)], [0, 99, 100])

    def test_rejects_what_the_firmware_rejects(self):
        bad = bytearray(self.blob)
        bad[0] = 0x58
        self.assertEqual(loading_anim.validate(bytes(bad)), "wrong magic")
        bad = bytearray(self.blob)
        table = struct.unpack_from("<H", bad, 10)[0]
        first = struct.unpack_from("<H", bad, table)[0]
        struct.pack_into("<H", bad, first + 2, 1020 | 7 << 10)
        self.assertIn("past byte 1023", loading_anim.validate(bytes(bad)))
        self.assertEqual(loading_anim.validate(self.blob[:-3]), "the file is shorter than its size")
        cut = bytearray(self.blob[:-3])
        struct.pack_into("<I", cut, 12, len(cut))
        self.assertIn("outside the file", loading_anim.validate(bytes(cut)))
        big = bytearray(self.blob)
        struct.pack_into("<I", big, 12, loading_anim.MAX_BYTES + 1)
        self.assertIn("more than", loading_anim.validate(bytes(big)))


class DefaultBlechy(unittest.TestCase):
    """assets/blechy/loading.blla, the default animation, shows the same pictures as the composition of the parts
    (load_bar.compose_reference, checked against the renderer by tools/art/loading/firmware_assets.py)."""

    def test_every_percent_and_finale_picture(self):
        import load_bar as lb
        blob = (ROOT / "assets/blechy/loading.blla").read_bytes()
        self.assertIsNone(loading_anim.validate(blob))
        self.assertEqual(loading_anim.loop_from(blob), lb.FINALE_AT)
        n = struct.unpack_from("<H", blob, 6)[0]
        art = lb.parse_loading(lb.LOAD_ART.read_bytes())
        bad = []
        for permille in range(1001):
            pct, done = permille // 10, permille == 1000
            index = loading_anim.progress_index(n, permille)
            for tick in (range(lb.TICKS_N) if done or pct >= lb.FINALE_AT else (None,)):
                want = lb.compose_reference(art, lb.loading_key(pct, done, tick or 0))
                if loading_anim.picture(blob, index, tick) != want:
                    bad.append((permille, tick))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
