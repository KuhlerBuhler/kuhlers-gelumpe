# SPDX-License-Identifier: GPL-2.0-only
"""Boot the firmware once, start from the snapshot every time after.

A boot to the main screen costs about two seconds of CPU, and the checks (check.py,
mfx_cases.py, splash_cases.py, the tests) boot the same firmware with the same flash and
the same held keys again and again. `booted` runs the boot once per (firmware, flash,
held keys, device time) and keeps `Machine.snapshot()` of it, in memory for this process and
in a file for the next one. A machine made from a snapshot goes on bit for bit as the one
that was booted (test_snapshot.py compares the whole RAM, the CPU and the model's state).

The files live in $GELUMPE_CACHE_DIR/boot (default ~/.cache/gelumpe/boot). They hold the
firmware's RAM, so they belong to the user's machine like the firmware itself: never in the
repository, never shared. A file is named by a hash of everything it depends on, including the
source of the emulator, so a change to the model makes the old files unreachable.
GELUMPE_CACHE=off turns the files and the memory off.
"""

import hashlib
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAMP = "source-hash.txt"
_memory = {}
_source = None


def enabled():
    return os.environ.get("GELUMPE_CACHE", "").lower() != "off"


def cache_dir(*parts):
    base = os.environ.get("GELUMPE_CACHE_DIR") or Path.home() / ".cache" / "gelumpe"
    return Path(base).joinpath(*parts)


def source_hash(*folders):
    """Hash of the Python source of the emulator (and of the given sibling folders of tools/): a change
    to the model makes every file derived from it unreachable."""
    global _source
    if getattr(sys, "frozen", False):
        # Frozen (the app's sidecar), the modules sit in PyInstaller's archive and HERE holds no .py file:
        # build-sidecar.mjs stamps the hash of the source of tools/emu and tools/patch into the bundle.
        if _source is None:
            _source = (None, (HERE / STAMP).read_text().strip())
        return _source[1]
    names = [HERE] + [HERE.parent / f for f in folders]
    key = tuple(map(str, names))
    if _source is None or _source[0] != key:
        h = hashlib.sha256()
        h.update(sys.version.split()[0].encode())
        for folder in names:
            for path in sorted(folder.glob("*.py")):
                h.update(path.name.encode())
                h.update(path.read_bytes())
        _source = (key, h.hexdigest())
    return _source[1]


def digest(*parts):
    h = hashlib.sha256()
    for part in parts:
        data = part if isinstance(part, (bytes, bytearray, memoryview)) else repr(part).encode()
        h.update(len(data).to_bytes(8, "little"))
        h.update(data)
    return h.hexdigest()


def read(kind, key):
    if not enabled():
        return None
    if (kind, key) in _memory:
        return _memory[(kind, key)]
    path = cache_dir(kind, key)
    try:
        data = path.read_bytes()
    except OSError:
        return None
    _memory[(kind, key)] = data
    return data


def write(kind, key, data):
    """Store bytes; a file appears whole or not at all, so processes that run side by side cannot read a half one."""
    if not enabled():
        return
    _memory[(kind, key)] = data
    try:
        folder = cache_dir(kind)
        folder.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".tmp-")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, folder / key)
    except OSError:
        pass                    # a cache that cannot be written is no cache; the run goes on without it


class _once:
    """While one process makes the file for `key`, the others that want it wait for it instead of making it too
    (workers that start the same boot at the same time). No lock where fcntl is missing or the folder cannot be written."""

    def __init__(self, kind, key):
        self.path = cache_dir(kind, key + ".lock")
        self.file = None

    def __enter__(self):
        if not enabled():
            return self
        try:
            import fcntl
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.file = open(self.path, "w")
            fcntl.flock(self.file, fcntl.LOCK_EX)
        except (ImportError, OSError):
            self.file = None
        return self

    def __exit__(self, *exc):
        if self.file is not None:
            self.file.close()


def booted(payload, flash=None, held=0, seconds=5.0, cls=None, observer=None, hold_power=False):
    """(machine, observer) after `seconds` of device time from power-on with the buttons `held` pressed
    (and the power button, with `hold_power`).

    `cls` is the Machine class (default machine.Machine). `observer(machine)`, if given, makes an object that
    watches the machine from power-on, for example by wrapping a method; it is made before the boot and
    again after a restore, and its attributes (picklable) are kept with the snapshot and put back, so it has seen
    what a real boot would have shown it."""
    import pickle
    import machine as emu
    cls = cls or emu.Machine
    flash_part = hashlib.sha256(flash).hexdigest() if flash else "blank"
    key = digest("boot-v1", source_hash(), cls.__module__, cls.__qualname__, observer and observer.__qualname__,
                 hashlib.sha256(payload).hexdigest(), flash_part, held, hold_power, repr(float(seconds)))
    blob = read("boot", key)
    if blob is None:
        with _once("boot", key):
            blob = read("boot", key)          # another process may have made it while this one waited
            if blob is None:
                return _boot(key, payload, flash, held, seconds, cls, observer, hold_power)
    snap, kept = pickle.loads(blob)
    m = cls.from_snapshot(snap, payload, flash)
    obj = observer(m) if observer else None
    if obj is not None:
        obj.__dict__.update(kept)
    return m, obj


def _boot(key, payload, flash, held, seconds, cls, observer, hold_power):
    import pickle
    import machine as emu
    m = cls(payload, flash)
    obj = observer(m) if observer else None
    m.held = held
    if hold_power:
        m.inputs[emu.pin(7, 15)] = 0
    m.run_until(seconds)
    m.finish_boot()                     # Korg's own build may still be loading its user data (Machine.loading)
    if enabled() and not m.asserts and m.mmc.card is None:
        kept = dict(obj.__dict__) if obj is not None else {}
        write("boot", key, pickle.dumps((m.snapshot(), kept), pickle.HIGHEST_PROTOCOL))
    return m, obj


def cached_result(kind, parts, compute):
    """compute() -> a JSON-able result (a check that came to its end, whether it passed or not), for the
    inputs `parts` (bytes or reprs). It is kept per inputs and emulator source, so the same files give the
    same answer without booting again; a run that raises is not kept. GELUMPE_CACHE=off runs everything."""
    import json
    key = digest("result-v1", kind, source_hash("patch"), *parts)
    hit = read("result", key)
    if hit is not None:
        return json.loads(hit)
    result = compute()
    write("result", key, json.dumps(result, ensure_ascii=False).encode())
    return result
