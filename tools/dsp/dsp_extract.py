#!/usr/bin/env python3
"""Extract the Blackfin DSP boot stream from an electribe sampler SYSTEM.VSB.

The stream is in the ADI BF52x boot format: 16-byte headers
(block code, target address, byte count, argument), the XOR of all 16 header
bytes is zero and the top byte of the block code is 0xAD.

Usage:
  dsp_extract.py SYSTEM.VSB OUTDIR

Writes into OUTDIR (keep it outside the repository, it is Korg code):
  blocks.txt   one line per block
  map.json     regions (target, size, file name)
  r_<addr>.bin one file per contiguous target region, fill blocks expanded
               unless they are larger than FILL_LIMIT (then recorded only)

Firmware 2.02 (stock and Hacktribe): stream at RAM 0xC00F9E10, 0x422A0 bytes.
"""
import json
import os
import struct
import sys

RAM_BASE = 0xC0000000
FILE_HEADER = 0x100
STREAM_RAM = 0xC00F9E10
STREAM_LEN = 0x422A0
FILL_LIMIT = 1 << 20

F_FILL, F_INIT, F_IGNORE, F_FIRST, F_FINAL = 0x0100, 0x0800, 0x1000, 0x4000, 0x8000


def file_offset(ram):
    return ram - RAM_BASE + FILE_HEADER


def parse(vsb, start=STREAM_RAM, length=STREAM_LEN):
    """Yield (index, file_offset, flags, target, count, arg, payload) per block."""
    pos = file_offset(start)
    end = pos + length
    index = 0
    while pos < end:
        head = vsb[pos:pos + 16]
        code, target, count, arg = struct.unpack('<IIII', head)
        xor = 0
        for byte in head:
            xor ^= byte
        if code >> 24 != 0xAD or xor != 0:
            raise ValueError(f'bad header at file 0x{pos:X} (block {index})')
        flags = code & 0xFFFF
        payload_len = 0 if flags & F_FILL else count
        payload = vsb[pos + 16:pos + 16 + payload_len]
        yield index, pos, flags, target, count, arg, payload
        pos += 16 + payload_len
        index += 1
        if flags & F_FINAL:
            break


def vsb_offset(vsb, dsp_addr):
    """File offset of the payload byte that lands at DSP address dsp_addr."""
    for _, pos, flags, target, count, _, payload in parse(vsb):
        if payload and not flags & F_IGNORE and target <= dsp_addr < target + count:
            return pos + 16 + (dsp_addr - target)
    return None


def extract(vsb, outdir):
    os.makedirs(outdir, exist_ok=True)
    mem = {}  # address -> byte, later blocks overwrite earlier ones (stage 1 is replaced)
    lines = []
    for index, pos, flags, target, count, arg, payload in parse(vsb):
        lines.append(f'{index:3d} file=0x{pos:06X} flags=0x{flags:04X} target=0x{target:08X} '
                     f'count=0x{count:X} arg=0x{arg:X}')
        if flags & (F_IGNORE | F_INIT) or count == 0:
            continue
        if flags & F_FILL:
            if count > FILL_LIMIT:
                lines[-1] += ' (fill, not expanded)'
                continue
            data = struct.pack('<I', arg) * (count // 4)
        else:
            data = payload
        for i, byte in enumerate(data):
            mem[target + i] = byte
    regions = []
    for addr in sorted(mem):
        if regions and regions[-1][0] + len(regions[-1][1]) == addr:
            regions[-1][1].append(mem[addr])
        else:
            regions.append([addr, bytearray([mem[addr]])])
    meta = []
    for target, data in sorted(regions):
        name = f'r_{target:08X}.bin'
        with open(os.path.join(outdir, name), 'wb') as handle:
            handle.write(data)
        meta.append({'target': target, 'size': len(data), 'file': name})
    with open(os.path.join(outdir, 'blocks.txt'), 'w') as handle:
        handle.write('\n'.join(lines) + '\n')
    with open(os.path.join(outdir, 'map.json'), 'w') as handle:
        json.dump(meta, handle, indent=1)
    return lines, meta


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    blob = open(sys.argv[1], 'rb').read()
    blocks, regs = extract(blob, sys.argv[2])
    print(f'{len(blocks)} blocks, {len(regs)} regions')
    for reg in regs:
        print(f"  0x{reg['target']:08X} +0x{reg['size']:X}")
