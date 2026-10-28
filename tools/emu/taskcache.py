# SPDX-License-Identifier: GPL-2.0-only
"""The result of one check task, kept with the files that task used.

A task of check.py (parallel.py) is one group of cases or one boot. Its result depends on the shared inputs (the
firmware, the flash, the base), on the task itself (module, function, arguments) and on the code and data it ran.
A key over all of tools/ would make every result stale on any change to any case file, so a merge of develop ran
everything again. Instead, the process that runs a task notes what it used: the source of every module it had
loaded when the task ended and every file it opened (an audit hook, sys.addaudithook). The result is kept with that
list and the hash of each file. A later run takes it only for the same inputs and only while every listed file still
has the same content: a change to pswitch_cases.py runs the pattern switch cases again and keeps the rest.

A changed firmware or flash is another input, so all of its tasks run. The list is exact when each task has a process
of its own (parallel.py does that while it keeps results); tasks that share a process list what all of them used, more
than each needs, which only means a task runs again more often than it would have to. Files of Python itself and of
its packages are not listed: the Python and Unicorn versions are part of the key instead. So are the variables E2_*
and GELUMPE_* of the environment that can change what a task does.

The files live in $GELUMPE_CACHE_DIR/task (bootcache.py). They hold results only, no firmware, but they are made from
it, so they stay on this machine like the boot snapshots. GELUMPE_CACHE=off runs every task.
"""

import hashlib
import os
import pickle
import sys
import sysconfig
from pathlib import Path

import bootcache

ROOT = Path(__file__).resolve().parents[2]
_opened = set()
_watching = False
_hashes = {}
# Variables that only steer how a run is done, not what a task finds
QUIET = frozenset(("GELUMPE_JOBS", "GELUMPE_PARENT_PID", "GELUMPE_CACHE_DIR", "GELUMPE_CACHE"))


def enabled():
    # A frozen build (the app's service) has no source files to list, so nothing would make its results stale
    return bootcache.enabled() and not getattr(sys, "frozen", False)


def watch():
    """Note every file this process opens from now on. An audit hook cannot be taken back; it costs one
    comparison per audited event, and the emulator's loop raises none that matter here."""
    global _watching
    if not _watching:
        _watching = True
        sys.addaudithook(_audit)


def _audit(event, args):
    if event == "open" and args and not isinstance(args[0], int):
        _opened.add(args[0])


def _outside():
    """Folders whose files are not listed: Python, its packages (the version is in the key) and the cache itself."""
    paths = {sys.prefix, sys.base_prefix, sys.exec_prefix, *sysconfig.get_paths().values(), str(bootcache.cache_dir())}
    return tuple(os.path.realpath(p) + os.sep for p in paths if p)


def _name(real):
    """A path as it goes into the list: relative to the repository, so the checkouts of one repository share their results."""
    try:
        return Path(real).relative_to(ROOT).as_posix()
    except ValueError:
        return real


def _path(name):
    return ROOT / name if not os.path.isabs(name) else Path(name)


def file_hash(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    memo = (str(path), st.st_mtime_ns, st.st_size)
    if memo not in _hashes:
        try:
            _hashes[memo] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            return None
    return _hashes[memo]


def used():
    """{file: sha256} of everything this process has loaded or opened so far, or None when a file it opened is
    gone (a file a task read and deleted cannot be checked later)."""
    outside = _outside()
    files = set()
    for module in list(sys.modules.values()):
        f = getattr(module, "__file__", None)
        if f and not f.startswith("<"):          # "<stdin>" and the like are no file
            files.add(os.path.realpath(f))
    for f in list(_opened):
        try:
            files.add(os.path.realpath(os.fsdecode(f)))
        except (TypeError, ValueError):
            continue
    deps = {}
    for real in files:
        # __pycache__: an import writes its .pyc through a temporary file that is renamed at once
        if real.startswith(outside) or f"{os.sep}__pycache__{os.sep}" in real or os.path.isdir(real):
            continue
        sha = file_hash(real)
        if sha is None:
            return None
        deps[_name(real)] = sha
    return deps


def _unicorn():
    try:
        from importlib.metadata import version
        return version("unicorn")
    except Exception:
        return None


def inputs(kind, data):
    """The part of the key that all tasks of one run share: `kind`, the shared data (parallel.shared), Python, Unicorn
    and the environment."""
    env = sorted((k, v) for k, v in os.environ.items() if k.startswith(("E2_", "GELUMPE_")) and k not in QUIET)
    parts = ["task-v1", kind, sys.version, _unicorn(), env]
    for name in sorted(data):
        value = data[name]
        parts += [name, hashlib.sha256(value).hexdigest() if isinstance(value, (bytes, bytearray, memoryview)) else repr(value)]
    return bootcache.digest(*parts)


def key(base, task):
    return bootcache.digest(base, *task)


def lookup(k):
    """(True, result) when a kept result for `k` holds, else (False, None)."""
    blob = bootcache.read("task", k)
    if blob is None:
        return False, None
    try:
        deps, result = pickle.loads(blob)
    except Exception:
        return False, None
    for name, sha in deps.items():
        if file_hash(_path(name)) != sha:
            return False, None
    return True, result


def durations():
    """Seconds each task took when it last ran, by task: parallel.run_tasks starts the longest first, so that the
    longest does not start last and keep everyone waiting."""
    import json
    blob = bootcache.read("task-time", "times")
    try:
        return json.loads(blob) if blob else {}
    except ValueError:
        return {}


def note_durations(seconds):
    import json
    if seconds:
        bootcache.write("task-time", "times", json.dumps({**durations(), **seconds}, sort_keys=True).encode())


def store(k, deps, result):
    if deps is not None:
        bootcache.write("task", k, pickle.dumps((deps, result), pickle.HIGHEST_PROTOCOL))
