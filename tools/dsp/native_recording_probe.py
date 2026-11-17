#!/usr/bin/env python3
"""Probe native capture with a user's extracted red DSP regions in GNU bfin sim.

All ELF files, including firmware regions, stay in a temporary directory outside
of the repository. MDMA is represented by its source/destination descriptors;
this does not measure DMA timing, SD throughput or device scheduling.
"""
import argparse
import json
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent / 'sim'))
from mkelf import write as write_elf

MASTER = 0xFF802888
SOURCE = 0xFF9031DC
RING = 0x01C722A0
RING_SIZE = 0x4B00
RESULT = 0x03100000


def load(reg, value):
    return f'{reg}.H = 0x{value >> 16:04x}; {reg}.L = 0x{value & 65535:04x};'


def store(address, value):
    return load('P1', address) + load('R2', value) + '[P1] = R2;'


def call(address):
    return load('P1', address) + 'CALL (P1);'


def output(size):
    return '\n'.join([
        load('P4', RESULT), 'R0 = 1 (X); [P4 + 32] = R0;',
        load('R0', RESULT + 64), '[P4 + 36] = R0;',
        load('R0', size), '[P4 + 40] = R0;',
        'R0 = P4; R0 += 32; P0 = 5 (X); EXCPT 0;',
        'R0 = 0 (X); [P4 + 32] = R0; R0 = P4; R0 += 32;',
        'P0 = 1 (X); EXCPT 0;',
    ])


def run_probe(args, asm, returns, size, patches=(), extra_segments=()):
    with tempfile.TemporaryDirectory(prefix='gelumpe-native-dsp-') as temp:
        work = Path(temp)
        (work / 'probe.s').write_text('.text\n.global _start\n_start:\n' +
            load('SP', 0x03F00000) + 'FP = SP;\n' + asm + '\n' + output(size) + '\n')
        subprocess.run([args.assembler, str(work / 'probe.s'), '-o', str(work / 'probe.o')], check=True)
        subprocess.run([args.objcopy, '-O', 'binary', '-j', '.text', str(work / 'probe.o'), str(work / 'probe.bin')], check=True)
        # Stop at instruction boundaries; preserve the executed firmware instructions.
        subprocess.run([args.assembler, '-o', str(work / 'ret.o')], input=b'.text\nRTS;\n', check=True)
        subprocess.run([args.objcopy, '-O', 'binary', '-j', '.text', str(work / 'ret.o'), str(work / 'ret.bin')], check=True)
        ret = (work / 'ret.bin').read_bytes()
        segments = []
        for entry in json.loads((args.regions / 'map.json').read_text()):
            data = bytearray((args.regions / entry['file']).read_bytes())
            for address, replacement in patches:
                offset = address - entry['target']
                if 0 <= offset and offset + len(replacement) <= len(data):
                    data[offset:offset + len(replacement)] = replacement
            for address in returns:
                offset = address - entry['target']
                if 0 <= offset < len(data):
                    data[offset:offset + len(ret)] = ret
            segments.append((entry['target'], bytes(data)))
        segments.extend(extra_segments)
        segments.append((0x03000000, (work / 'probe.bin').read_bytes()))
        write_elf(str(work / 'probe.elf'), segments, 0x03000000)
        cmd = [args.run, '--environment', 'virtual', '--model', 'bf527']
        for base, length in [(0, 0x4000000), (0xFF800000, 0x8000), (0xFF900000, 0x8000), (0xFFA00000, 0x14000), (0xFFC00000, 0x3FF000)]:
            cmd += ['--memory-region', f'{base:#x},{length:#x}']
        proc = subprocess.run(cmd + [str(work / 'probe.elf')], capture_output=True, timeout=30)
        if proc.returncode or len(proc.stdout) != size:
            raise RuntimeError(f'simulator exit {proc.returncode}, {len(proc.stdout)}/{size} bytes: {proc.stderr.decode(errors="replace")}')
        return struct.unpack('<' + 'I' * (size // 4), proc.stdout)


def capture(args):
    frames = 4803
    rng = random.Random(37)
    samples = [rng.getrandbits(32) for _ in range(frames)]
    asm = [store(0x03200004, 1),
           load('P4', 0x03200000), load('P0', 0xFF9031D8),
           load('P5', 0xFF802878),
           'R4 = 0 (X); R5 = R4;', call(0xFFA05620),
           load('P2', RESULT + 64), '[P2++] = R7;',
           load('P1', 0xFF9031D0), 'R0 = [P1]; [P2++] = R0;',
           load('P1', 0xFF9031D8), 'R0 = [P1]; [P2++] = R0;',
           load('P1', SOURCE), 'R0 = [P1]; [P2++] = R0;',
           store(0xFF9031D4, RING_SIZE), store(0xFF9031E0, 0x03210000),
           store(0xFF9031E4, 0x03210004)]
    for index, sample in enumerate(samples):
        source = MASTER if index % 2 == 0 else 0x03220000
        asm += [store(SOURCE, source), store(source, sample),
                load('P5', 0xFF9030A4), call(0xFFA017AA),
                load('P2', RESULT + 80 + index * 16)]
        for address in (0xFF80004C, 0x03210000, 0x03210004, 0xFF9031D8):
            asm += [load('P1', address), 'R0 = [P1]; [P2++] = R0;']
    words = run_probe(args, '\n'.join(asm), [0xFFA04F70, 0xFFA017EE], 16 + frames * 16)
    assert words[:4] == (1, 1, RING, 0xFF802878), words[:4]
    words = words[4:]
    ring = bytearray(RING_SIZE)
    for index, sample in enumerate(samples):
        staged, dma_source, destination, next_pointer = words[index * 4:index * 4 + 4]
        assert staged == sample, (index, hex(staged), hex(sample))
        assert dma_source == 0xFF80004C, hex(dma_source)
        assert destination == RING + index * 4 % RING_SIZE, hex(destination)
        assert next_pointer == RING + (index + 1) * 4 % RING_SIZE, hex(next_pointer)
        struct.pack_into('<I', ring, destination - RING, staged)
    assert struct.unpack_from('<I', ring)[0] == samples[4800]
    return {'frames': frames, 'source_changed_each_frame': True, 'ring_wrap': True,
            'bit_exact_staging_and_descriptors': True, 'physical_dma_tested': False}


def packing(args):
    pairs = [(0, 0), (0x12345678, 0xABCDEF01),
             (0x7FFFFFFF, 0x80000000), (0xFFFFFFFF, 0xFFFFFFFF)]
    asm = []
    for index, (left, right) in enumerate(pairs):
        asm += [load('R0', left), load('R1', right), load('P4', 0xFF802870),
                call(0xFFA01788), load('P2', RESULT + 64 + index * 8),
                'R0 = [P4 + 0x18]; [P2++] = R0;',
                'R0 = [P4 + 0x1C]; [P2] = R0;']
    words = run_probe(args, '\n'.join(asm), [0xFFA017AA], len(pairs) * 8)
    signed = lambda n: n if n < 0x80000000 else n - 0x100000000
    for index, (left, right) in enumerate(pairs):
        assert words[index * 2] == (left & 0xFFFF0000) | (right >> 16)
        assert words[index * 2 + 1] == ((signed(left) >> 1) + (signed(right) >> 1)) & 0xFFFFFFFF
    return {'stereo_pairs': len(pairs), 'packed_left_high_right_low': True,
            'mono_arithmetic_half_sum': True}


def output_stage(args, before_click=False):
    scenarios = [
        ('silent', 0, 0, 0, 0),
        ('audio_left', 0x10000000, 0, 0, 0),
        ('audio_right', 0, 0x20000000, 0, 0),
        ('click', 0, 0, 0x7FFF0000, 0x7FFF0000),
        ('audio_and_click', 0x10000000, 0x20000000, 0x7FFF0000, 0x7FFF0000),
        ('click_muted', 0, 0, 0x7FFF0000, 0),
    ]
    asm = []
    for index, (_, left, right, envelope, click_level) in enumerate(scenarios):
        state = {
            0x8C: 0x7FFF0000, 0x90: 0, 0x94: 0x40000000, 0x98: 0,
            0x9C: left, 0xA0: right, 0xA4: 34 << 16,
            0xA8: click_level, 0xAC: 0x40000000, 0xB0: 0,
            0xB4: envelope, 0xB8: 0, 0xBC: 0x7FFF0000,
            0xC0: 0, 0xC4: 0x40000000, 0xC8: 0,
        }
        asm += [store(0xFF9030A4 + offset, value) for offset, value in state.items()]
        asm += [store(0xFF802870, left), store(0xFF802874, right),
                load('P4', 0xFF802870), load('P5', 0xFF9030A4),
                'R0 = 0 (X); R1 = R0;', call(0xFFA0189A),
                load('P2', RESULT + 64 + index * 8), '[P2++] = R0; [P2] = R1;']
    words = run_probe(args, '\n'.join(asm), [0xFFA018E0 if before_click else 0xFFA0193E], len(scenarios) * 8)
    observed = {row[0]: list(words[i * 2:i * 2 + 2]) for i, row in enumerate(scenarios)}
    if before_click:
        assert observed['click'] == [0, 0], observed
        assert observed['audio_and_click'] == [observed['audio_left'][0], observed['audio_right'][1]], observed
        assert observed['audio_left'][0] and observed['audio_right'][1], observed
        return observed
    assert observed['silent'] == [0, 0], observed
    assert observed['audio_left'][0] != 0 and observed['audio_left'][1] == 0, observed
    assert observed['audio_right'][0] == 0 and observed['audio_right'][1] != 0, observed
    assert observed['click'][0] == observed['click'][1] != 0, observed
    assert observed['click_muted'] == [0, 0], observed
    assert observed['audio_and_click'] == [observed['audio_left'][0] + observed['click'][0],
                                          observed['audio_right'][1] + observed['click'][1]], observed
    return observed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('regions', type=Path)
    ap.add_argument('--as', dest='assembler', required=True)
    ap.add_argument('--objcopy', required=True)
    ap.add_argument('--run', required=True)
    args = ap.parse_args()
    print(json.dumps({'packing': packing(args), 'capture': capture(args), 'output_stage': output_stage(args), 'before_click': output_stage(args, before_click=True)}, indent=2))


if __name__ == '__main__':
    main()
