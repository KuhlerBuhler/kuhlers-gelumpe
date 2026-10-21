# SPDX-License-Identifier: GPL-2.0-only
"""Measure native command work; USB controller and storage latency are not modeled."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools/patch'))
from tools.patch import sysex_fixture as fixture

PROTOCOL = {'ports': [1, 2], 'sizes': list(fixture.SIZES), 'functions': list(range(0x60, 0x68)),
            'scope': 'native-command-ABI'}


def profile(folder, build, source=None):
    folder = Path(folder)
    b = fixture.generator(source)
    firmware = (folder / f'{build}.VSB').read_bytes()
    if build == 'synth':
        b.use_build(build, folder / 'stock-original.VSB', (folder / 'synth-original.VSB').read_bytes())
    at, code, _symbols = b.build_code()
    offset = at - 0xc0000000 + 0x100
    if firmware[offset:offset + len(code)] != code:
        raise ValueError(f'{build}: measured SysEx code differs from checked firmware')
    offset = b.TABLE_AT - 0xc0000000 + 0x100
    regions, windows = struct.unpack_from('<II', firmware, offset)
    size = (2 + regions * 3 + windows * 5) * 4
    if not 8 <= size <= b.TABLE_END - b.TABLE_AT:
        raise ValueError('invalid protection table size')
    table = firmware[offset:offset + size]
    repeats = [fixture.exercise(fixture.NativeSysex(b, build, table)) for _ in range(3)]
    if any(row != repeats[0] for row in repeats):
        raise ValueError('native transfer work or results differ between repeats')
    method = hashlib.sha256((Path(fixture.__file__).read_text() + inspect.getsource(profile)
                             + json.dumps(PROTOCOL, sort_keys=True)).encode()).hexdigest()
    return {**repeats[0], 'method': method, 'protocol': PROTOCOL,
            'firmwareSha256': hashlib.sha256(firmware).hexdigest(),
            'codeSha256': hashlib.sha256(code).hexdigest(), 'maxBlock': b.MAX_BLOCK,
            'bufferStart': b.BUF, 'bufferEnd': b.BUF_END, 'fileArea': [b.FILE_AREA, b.FILE_AREA_END],
            'repeats': repeats}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--generator', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    data = {}
    for build in ('hacktribe', 'stock', 'synth'):
        data[build] = profile(args.folder, build, args.generator)
        args.out.write_text(json.dumps(data, indent=2) + '\n')
        print(f'{build}: {data[build]["cases"]} commands, {data[build]["instructions"]} instructions', file=sys.stderr, flush=True)
