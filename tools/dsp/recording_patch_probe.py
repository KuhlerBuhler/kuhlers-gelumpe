#!/usr/bin/env python3
"""Compare the recording DSP tap with the original mix, using external regions."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.patch import recording_dsp
from native_recording_probe import call, load, store, run_probe, RESULT

CASES = [
    ('silence', 0, 0, 0, 0, 0),
    ('master', 0x10000000, 0x20000000, 0, 0, 0),
    ('input', 0, 0, 0x10000000, 0x20000000, 0),
    ('click', 0, 0, 0, 0, 0x7FFF0000),
    ('master_input_click', 0x10000000, 0x20000000, 0x08000000, 0x04000000, 0x7FFF0000),
    ('saturation_click', 0x70000000, 0x60000000, 0x60000000, 0x50000000, 0x7FFF0000),
    ('negative_input', 0xA0000000, 0x20000000, 0xC0000000, 0xF0000000, 0),
    ('negative_click', 0x80000000, 0x90000000, 0xF0000000, 0xE0000000, 0x7FFF0000),
    ('right_only', 0, 0x60000000, 0, 0, 0),
    ('opposite_channels', 0x60000000, 0xA0000000, 0, 0, 0),
]


def measure(args, program=None, enabled=0, mute_click=False):
    synth = args.build == 'synth'
    mix, stop = (0xFFA01818, 0xFFA018C4) if synth else (0xFFA0189A, 0xFFA01948)
    input_base, state_base = (0xFF802808, 0xFF90309C) if synth else (0xFF802870, 0xFF9030A4)
    asm = []
    for index, (_, master_l, master_r, left, right, click) in enumerate(CASES):
        state = {
            0x8C: 0x7FFF0000, 0x90: 0, 0x94: 0x40000000, 0x98: 0,
            0x9C: left, 0xA0: right, 0xA4: 34 << 16,
            0xA8: 0 if mute_click else 0x20000000, 0xAC: 0x40000000, 0xB0: 0,
            0xB4: click, 0xB8: 0, 0xBC: 0x7FFF0000,
            0xC0: 0, 0xC4: 0x40000000, 0xC8: 0,
        }
        asm += [store(state_base + offset, value) for offset, value in state.items()]
        asm += [store(recording_dsp.ENABLE, enabled), store(recording_dsp.CAPTURE, 0),
                store(input_base, left), store(input_base + 4, right),
                load('P4', input_base), load('P5', state_base),
                load('R0', master_l), load('R1', master_r), call(mix),
                load('P2', RESULT + 64 + index * 12), '[P2++] = R0; [P2++] = R1;',
                load('P1', recording_dsp.CAPTURE), 'R0 = [P1]; [P2] = R0;']
    extra = [(recording_dsp.CODE, program['code'])] if program else []
    patches = program['hooks'] if program else []
    words = run_probe(args, '\n'.join(asm), [stop], len(CASES) * 12,
                      patches=patches, extra_segments=extra)
    return [tuple(words[index * 3:index * 3 + 3]) for index in range(len(CASES))]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('regions', type=Path)
    ap.add_argument('--as', dest='assembler', required=True)
    ap.add_argument('--objcopy', required=True)
    ap.add_argument('--run', required=True)
    ap.add_argument('--build', choices=('hacktribe', 'stock', 'synth'), default='hacktribe')
    args = ap.parse_args()
    program = recording_dsp.assemble_program(args.assembler, args.objcopy, args.build)
    original = measure(args)
    no_click = measure(args, mute_click=True)
    off = measure(args, program, enabled=0)
    on = measure(args, program, enabled=1)
    for index, (name, *_) in enumerate(CASES):
        assert off[index][:2] == original[index][:2], ('disabled output', name, off[index], original[index])
        assert on[index][:2] == original[index][:2], ('enabled output', name, on[index], original[index])
        assert off[index][2] == 0, ('disabled tap changed', name)
        left, right = no_click[index][:2]
        signed = lambda value: value if value < 0x80000000 else value - 0x100000000
        expected = (((signed(left) >> 1) + (signed(right) >> 1)) & 0xFFFFFFFF
                    if args.build == 'synth' else (left & 0xFFFF0000) | (right >> 16))
        assert on[index][2] == expected, ('tap differs from click-free output', name, hex(on[index][2]), hex(expected))
    assert original[3][:2] != no_click[3][:2], 'click fixture is audible'
    assert original[4][:2] != no_click[4][:2], 'mixed fixture contains a click'
    print(json.dumps({'cases': len(CASES), 'patched_output_bit_exact': True,
                      'disabled_tap_unchanged': True, 'capture_equals_output_without_click': True,
                      'input_and_saturation_covered': True, 'hardware_tested': False}, indent=2))


if __name__ == '__main__':
    main()
