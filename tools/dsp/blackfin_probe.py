#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded private-firmware diagnostics. Functional init is not a full DSP boot."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'emu'))
from blackfin_backend import BlackfinBackend, BlackfinPort, BackendError, boot_blocks
from dsp_extract import STREAM_RAM, STREAM_LEN, file_offset

RETURN = 0x03000000
INIT_CALLS = ((0x01F10878, 0x8000), (0xFFA095F0, 0x3B), (0x01F0EC38, 0),
              (0x01F108C8, 0), (0x00000164, 0xFF900CCC), (0x01F0C8D4, 0))


def functional_init(worker, stream):
    with BlackfinBackend(worker, timeout=15) as backend:
        for flags, address, size, argument, data in boot_blocks(stream):
            if flags & (0x800 | 0x1000):
                continue
            for offset in range(0, size, 1 << 20):
                count = min(size-offset, 1 << 20)
                chunk = (struct.pack('<I', argument)*((count+3)//4))[:count] if flags & 0x100 else data[offset:offset+count]
                backend.write(address+offset, chunk)
        before = backend.read(0xFF9031D8, 4)
        for register, value in ((14, 0xFF9045F4), (15, 0xFF904600), (46, 0xFF904600), (48, 0x32)):
            backend.set_register(register, value)
        rows = []
        for function, argument in INIT_CALLS:
            backend.set_register(0, argument)
            backend.set_register(37, RETURN)
            backend.set_register(53, function)
            row = dict(function=hex(function), **backend.run(1000000, until=RETURN))
            rows.append(row)
            if not row['reached']:
                raise BackendError(f'DSP initialization function did not return: {row}')
        response = backend.read(0xFF9031D8, 4)
        if before == response or response == bytes(4):
            raise BackendError('DSP initialization functions did not produce the expected pointer')
        return dict(mode='functional-init', full_boot=False, hardware_timing=False,
                    functions=rows, before=before.hex(), response=response.hex(), response_address='0xff9031d8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vsb', required=True, type=Path)
    parser.add_argument('--worker', required=True, type=Path)
    parser.add_argument('--functional-init', action='store_true')
    parser.add_argument('--operating', action='store_true')
    args = parser.parse_args()
    if args.functional_init and args.operating:
        parser.error('functional init uses the virtual instruction runner')
    vsb = args.vsb.read_bytes()
    stream = vsb[file_offset(STREAM_RAM):file_offset(STREAM_RAM)+STREAM_LEN]
    try:
        if args.functional_init:
            report = functional_init(args.worker, stream)
        else:
            with BlackfinPort(args.worker, operating=args.operating, timeout=15) as port:
                port.boot(stream)
                port.wait_ready()
                report = dict(mode='reset-entry', full_boot=False, initialization=port.boot_report,
                              note='Initialization response alone does not prove full DSP operation')
        print(json.dumps(dict(ok=True, **report), indent=2))
        return 0
    except (BackendError, ValueError) as error:
        print(json.dumps(dict(ok=False, error=str(error), full_boot=False), indent=2))
        return 1


if __name__ == '__main__':
    sys.exit(main())
