"""Build the red/Hacktribe DSP recording tap from own Blackfin source.

The user's VSB is only read to locate and authenticate the replaced ranges.
The manifest contains own code and hashes. GNU Blackfin binutils assemble the
new code in a temporary directory outside the repository.
"""
import argparse
from functools import reduce
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from tools.dsp import dsp_extract
from .ramdecl import area

CODE = 0x01F12000
STATE = CODE + 0x100
CAPTURE = STATE + 8
ENABLE = STATE + 12
MAGIC_ADDRESS = STATE + 16
MAGIC = 0x4345524E
PROGRAM_SIZE = 0x114
AFTER_INPUT = CODE
AFTER_GAIN = CODE + 0x80
FINAL_HEADER = 0xC013C0A0
APPEND = FINAL_HEADER + 16
RESERVE_END = 0xC013C200
LENGTH_WORD = 0xC0011AB0
HEAP_TABLE = 0x01F02438
HOOK_HASHES = {
    0xFFA018DC: 'b2f2913f334c2d9ad238f3f9f58ea2379d99365228120290727692921a2532da',
    0xFFA0193E: 'e6d7929a5d53d39578f86435ce9614d7afc01e4b90c4fef103b3251cccbb33a4',
}


def boot_header(flags, target, count=0, argument=0):
    header = bytearray(struct.pack('<IIII', 0xAD000000 | flags, target, count, argument))
    header[2] = reduce(int.__xor__, header, 0)
    return bytes(header)


def assemble_program(assembler, objcopy):
    with tempfile.TemporaryDirectory(prefix='native-recording-bfin-') as directory:
        work = Path(directory)

        def assemble(text, name):
            src, obj, binary = (work / (name + suffix) for suffix in ('.s', '.o', '.bin'))
            src.write_text(text)
            try:
                subprocess.run([assembler, str(src), '-o', str(obj)], check=True, capture_output=True)
                subprocess.run([objcopy, '-O', 'binary', '-j', '.text', str(obj), str(binary)], check=True, capture_output=True)
            except subprocess.CalledProcessError as error:
                raise ValueError(error.stderr.decode(errors='replace')) from error
            return binary.read_bytes()

        code = assemble(Path(__file__).with_suffix('.s').read_text(), 'recording')
        if len(code) != PROGRAM_SIZE or struct.unpack_from('<I', code, MAGIC_ADDRESS - CODE)[0] != MAGIC:
            raise ValueError('the recording program must end with its four state words')
        hooks = []
        for address, destination in [(0xFFA018DC, AFTER_INPUT), (0xFFA0193E, AFTER_GAIN)]:
            hook = assemble(f'.text\nP1.H = {destination >> 16:#x}; P1.L = {destination & 65535:#x}; JUMP (P1);\n', f'hook_{address:x}')
            # GNU pads a Blackfin text section to four bytes.
            if len(hook) == 12 and hook[10:] == b'\0\0':
                hook = hook[:10]
            if len(hook) != 10:
                raise ValueError('the DSP redirect must replace exactly 10 bytes')
            hooks.append((address, hook))
        return {'code': code, 'hooks': hooks}


def file_offset(address):
    return address - 0xC0000000 + 0x100


def build_patch(vsb, program):
    if len(vsb) != 0x200100:
        raise ValueError('a sampler VSB has 0x200100 bytes')
    blocks = list(dsp_extract.parse(vsb))
    if blocks[-1][1] != file_offset(FINAL_HEADER):
        raise ValueError('the DSP boot stream has a different final header')
    for _, _, flags, target, count, _, _ in blocks:
        if not flags & dsp_extract.F_IGNORE and target < CODE + PROGRAM_SIZE and CODE < target + count:
            raise ValueError('a DSP boot block already uses the recording program area')
    for index in range(16):
        offset = dsp_extract.vsb_offset(vsb, HEAP_TABLE + index * 12)
        if offset is None:
            raise ValueError('the DSP heap table is missing')
        base, length, ident = struct.unpack_from('<III', vsb, offset)
        if (base, length, ident) == (0, 0, 0):
            break
        # Include the terminal byte under either allocator length convention.
        if base < CODE + PROGRAM_SIZE and CODE < base + length + 1:
            raise ValueError('a DSP allocator heap overlaps the recording program area')
    else:
        raise ValueError('the DSP heap table has no terminator')
    end_header = boot_header(0x8001, 0xFFA00000)
    start = file_offset(FINAL_HEADER)
    if vsb[start:start + 16] != end_header:
        raise ValueError('the final DSP header is not the sampler entry point')
    payload = program['code']
    if len(payload) != PROGRAM_SIZE:
        raise ValueError('unexpected recording program size')
    tail = boot_header(1, CODE, len(payload)) + payload + end_header
    growth = len(tail) - 16
    if APPEND + growth > RESERVE_END:
        raise ValueError('the DSP boot append overlaps the preset table reserve')
    if vsb[start + 16:start + len(tail)] != b'\xFF' * growth:
        raise ValueError('the DSP boot append area is occupied')
    length_at = file_offset(LENGTH_WORD)
    old_length = struct.unpack_from('<I', vsb, length_at)[0]
    if old_length != dsp_extract.STREAM_LEN:
        raise ValueError('unexpected DSP upload length')
    changes = []

    def change(offset, data, note):
        changes.append({'file': offset, 'bytes': data.hex(),
                        'expect': hashlib.sha256(vsb[offset:offset + len(data)]).hexdigest(), 'note': note})

    hooks = program['hooks']
    if len(hooks) != 2 or {address for address, _ in hooks} != set(HOOK_HASHES):
        raise ValueError('the recording program needs both DSP redirects')
    for address, data in hooks:
        offset = dsp_extract.vsb_offset(vsb, address)
        if offset is None or len(data) != 10 or hashlib.sha256(vsb[offset:offset + 10]).hexdigest() != HOOK_HASHES[address]:
            raise ValueError(f'the DSP instructions at {address:#x} do not match firmware 2.02')
        change(offset, data, f'DSP {address:#x}: recording tap redirect')
    change(start, tail[:16], 'load descriptor for the own recording DSP block')
    change(start + 16, tail[16:], 'own recording DSP code, zeroed control words, marker and final boot header')
    change(length_at, struct.pack('<I', old_length + growth), 'include the recording block in the DSP upload length')
    return {'format': 'gelumpe-patch', 'version': 1, 'id': 'native-recording-dsp',
            'name': 'Aufnahme-Abgriff nach THRU ohne Metronom', 'builds': ['hacktribe', 'stock'],
            'changes': changes, 'startPhase': [],
            'sources': {f'tools/patch/recording_dsp{suffix}': hashlib.sha256(Path(__file__).with_suffix(suffix).read_bytes()).hexdigest()
                        for suffix in ('.py', '.s')},
            'ram': [],
            'dspMemory': [area(CODE, PROGRAM_SIZE, 'recording code, four control words and a program marker in DSP SDRAM',
                               'tools/patch/recording_dsp.py:CODE')]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vsb', type=Path, required=True)
    ap.add_argument('--as', dest='assembler', default=os.environ.get('BFIN_AS', 'bfin-elf-as'))
    ap.add_argument('--objcopy', default=os.environ.get('BFIN_OBJCOPY', 'bfin-elf-objcopy'))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.write_text(json.dumps(build_patch(args.vsb.read_bytes(), assemble_program(args.assembler, args.objcopy)), indent=1) + '\n')


if __name__ == '__main__':
    main()
