#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded DSP reset/RTOS diagnostics with a host-loaded boot stream."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'emu'))
from blackfin_backend import BlackfinPort, BackendError
from dsp_extract import STREAM_RAM, STREAM_LEN, file_offset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vsb', required=True, type=Path)
    parser.add_argument('--worker', required=True, type=Path)
    parser.add_argument('--virtual', action='store_true', help='instruction-only diagnostic without interrupt hardware')
    args = parser.parse_args()
    vsb = args.vsb.read_bytes()
    stream = vsb[file_offset(STREAM_RAM):file_offset(STREAM_RAM)+STREAM_LEN]
    try:
        with BlackfinPort(args.worker, operating=not args.virtual, timeout=15) as port:
            port.boot(stream)
            port.wait_ready()
            report = dict(mode='reset-entry', full_boot=False, initialization=port.boot_report,
                          note='An initialization response alone does not prove full DSP operation')
        print(json.dumps(dict(ok=True, **report), indent=2))
        return 0
    except (BackendError, ValueError) as error:
        print(json.dumps(dict(ok=False, error=str(error), full_boot=False), indent=2))
        return 1


if __name__ == '__main__':
    sys.exit(main())
