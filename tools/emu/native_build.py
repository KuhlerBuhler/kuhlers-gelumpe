# SPDX-License-Identifier: GPL-3.0-or-later
"""Small C helpers (arm_tick.c, tools/dsp/blackfin_channel.c) built once per source and host into the temp
directory and loaded with ctypes. Callers keep a Python path for when no C compiler is there."""
import ctypes
import hashlib
import os
import platform
import subprocess
import tempfile
from pathlib import Path

_LOADED = {}


def library(source):
    """The built shared library for `source`, or None when it cannot be built."""
    source = Path(source)
    if source not in _LOADED:
        digest = hashlib.sha1(source.read_bytes() + platform.platform().encode()).hexdigest()[:12]
        target = Path(tempfile.gettempdir()) / f'gelumpe-{source.stem}-{digest}.so'
        loaded = None
        try:
            if not target.exists():
                partial = target.with_name(f'{target.name}.{os.getpid()}')
                subprocess.run([os.environ.get('CC', 'cc'), '-O2', '-shared', '-fPIC', '-o', str(partial), str(source)],
                               check=True, capture_output=True, timeout=120)
                os.replace(partial, target)
            loaded = ctypes.CDLL(str(target))
        except (OSError, subprocess.SubprocessError):
            loaded = None
        _LOADED[source] = loaded
    return _LOADED[source]
