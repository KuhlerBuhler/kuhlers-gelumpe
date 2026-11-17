# SPDX-License-Identifier: GPL-3.0-or-later
"""Which Blackfin worker runs.

An explicit choice wins (an argument, else BFIN_WORKER). Without one the QEMU worker built by
tools/dsp/build_qemu.py runs, and the GNU worker from tools/dsp/build_blackfin.py only when no QEMU
build exists. Both are looked up under GELUMPE_DSP (default ~/gelumpe-dsp):

    GELUMPE_DSP/worker/qemu-bfin-worker   build_qemu.py GELUMPE_DSP/worker
    GELUMPE_DSP/gnu/blackfin-worker       build_blackfin.py GELUMPE_DSP/gnu
"""
import os
from pathlib import Path
import sys

QEMU = Path('worker/qemu-bfin-worker')
GNU = Path('gnu/blackfin-worker')
_warned = False


def home():
    return Path(os.environ.get('GELUMPE_DSP') or Path.home() / 'gelumpe-dsp')


def find(chosen=None):
    """Path of the worker to run, or None when none is chosen or built."""
    global _warned
    chosen = chosen or os.environ.get('BFIN_WORKER')
    if chosen:
        return str(chosen)
    qemu, gnu = home() / QEMU, home() / GNU
    if os.access(qemu, os.X_OK):
        return str(qemu)
    if os.access(gnu, os.X_OK):
        if not _warned:
            print(f'Blackfin: no QEMU worker at {qemu}, running the GNU worker {gnu} '
                  '(tools/dsp/build_qemu.py builds QEMU)', file=sys.stderr)
            _warned = True
        return str(gnu)
    return None
