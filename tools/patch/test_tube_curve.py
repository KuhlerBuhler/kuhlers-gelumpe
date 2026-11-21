"""Tube curve: the blocks the runtime sends and the patch check it reads agree with tools/dsp/tube_model.py and the patch
files (data/patches/tube-curve*.json); no firmware required."""
import json
import pathlib
import re
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools/patch'), str(ROOT / 'tools/dsp')]
import tube_curve
import tube_model
from tools.patch.script_hooks import runtime_profile

PATCHES = {'hacktribe': 'tube-curve.json', 'stock': 'tube-curve.json', 'synth': 'tube-curve-synth.json'}


def table(label):
    """The words of the table `label` in script_menu.s, one list per .word line."""
    text = (ROOT / 'tools/patch/script_menu.s').read_text()
    body = text.split('\n%s:\n' % label, 1)[1]
    rows = []
    for line in body.splitlines():
        if not line.strip().startswith('.word'):
            break
        rows.append([int(w, 16) for w in re.findall(r'0x[0-9A-Fa-f]+', line.split(';')[0])])
    return rows


def sent(step, asym):
    """The 10 words tube_tick sends for TUBE DRIVE `step` (0: OFF) and TUBE ASYM `asym`, computed as the ARM does."""
    if step == 0:
        return bytes(40)
    row = table('tube_rows')[step - 1]
    k = table('tube_asym')[0][asym]
    gp = (((row[1] >> 16) * k) >> 15) << 16
    return struct.pack('<10I', gp, *row)


class TubeCurve(unittest.TestCase):
    def test_blocks_are_the_model(self):
        """tube_rows and tube_asym hold the model's rows and factors, and what the ARM sends is block()."""
        rows = table('tube_rows')
        self.assertEqual(len(rows), len(tube_model.STEPS))
        for step, row in enumerate(rows, 1):
            self.assertEqual(row, [w & 0xFFFFFFFF for w in tube_model.row(step)], step)
        self.assertEqual(table('tube_asym'), [list(tube_model.ASYM_K)])
        for step in range(len(tube_model.STEPS) + 1):
            for asym in range(tube_model.ASYM_STEPS):
                self.assertEqual(sent(step, asym), tube_model.block(step, asym), (step, asym))

    def test_mark_is_the_patched_caller(self):
        """TUBE_MARK is the RAM address of the caller's P0.L immediate the patch changes, TUBE_MARK_ON its new value."""
        for build, name in PATCHES.items():
            patch = json.loads((ROOT / 'data/patches' / name).read_text())
            self.assertIn(build, patch['builds'])
            target = next(t for t in tube_curve.TARGETS.values() if t['id'] == patch['id'])
            caller = patch['changes'][0]
            actions = runtime_profile(build).actions
            self.assertEqual(actions['TUBE_MARK'], 0xC0000000 + caller['file'] - 0x100 + 2, build)
            self.assertEqual(actions['TUBE_MARK_ON'], target['at'] & 0xFFFF, build)
            self.assertEqual(bytes.fromhex(caller['bytes'])[2:], actions['TUBE_MARK_ON'].to_bytes(2, 'little'), build)

    def test_routine_is_the_patch(self):
        for name in set(PATCHES.values()):
            patch = json.loads((ROOT / 'data/patches' / name).read_text())
            t = next(t for t in tube_curve.TARGETS.values() if t['id'] == patch['id'])
            head, tail = tube_curve.routine(t['at'], t['clipper'], t['tail'])
            self.assertEqual(patch['changes'][1]['bytes'], head.hex(), name)
            self.assertEqual(patch['changes'][2]['bytes'], tail.hex(), name)


if __name__ == '__main__':
    unittest.main()
