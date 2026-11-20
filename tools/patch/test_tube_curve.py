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


def table():
    """The words of tube_blocks in script_menu.s, one row per TUBE DRIVE step (0: OFF)."""
    text = (ROOT / 'tools/patch/script_menu.s').read_text()
    body = text.split('\ntube_blocks:\n', 1)[1]
    rows = []
    for line in body.splitlines():
        if not line.strip().startswith('.word'):
            break
        rows.append([int(w, 16) for w in re.findall(r'0x[0-9A-Fa-f]+', line.split(';')[0])])
    return rows


class TubeCurve(unittest.TestCase):
    def test_blocks_are_the_model(self):
        rows = table()
        self.assertEqual(len(rows), len(tube_model.STEPS) + 1)
        for step, row in enumerate(rows):
            self.assertEqual(struct.pack('<8I', *row), tube_model.block(step), step)

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
            self.assertEqual(patch['changes'][1]['bytes'], tube_curve.routine(t['at'], t['clipper']).hex(), name)


if __name__ == '__main__':
    unittest.main()
