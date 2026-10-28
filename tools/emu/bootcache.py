# SPDX-License-Identifier: GPL-2.0-only
"""Boot the firmware once, start from the snapshot every time after.

A boot to the main screen costs about two seconds of CPU, and the checks (check.py,
mfx_cases.py, splash_cases.py, the tests) boot the same firmware with the same flash and
the same held keys again and again. `booted` runs the boot once per (firmware, flash,
held keys, device time) and keeps `Machine.snapshot()` of it, in memory for this process and
in a file for the next one. A machine made from a snapshot goes on bit for bit as the one
that was booted (test_snapshot.py compares the whole RAM, the CPU and the model's state).

`power_on` does the same for any machine that has not run yet, a card in the slot included: the cases
build a device, put a card in, set what they need and run it (splash_cases.Dev.run). The first such run of
one kind is kept, every later one starts from it.

The files live in $GELUMPE_CACHE_DIR/boot and /power-on (default ~/.cache/gelumpe). They hold the
firmware's RAM, so they belong to the user's machine like the firmware itself: never in the
repository, never shared. A file is named by a hash of everything it depends on, including the
source of the model (the machine's module and what it imports, `model_hash`; not the cases), so a
change to the model makes the old files unreachable. GELUMPE_CACHE=off turns the files and the memory off.
"""

import ast
import hashlib
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
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


def _module_file(name):
    """The file of a module of this repository (tools/emu/x, tools/patch/x on the path the cases set, tools.patch.y),
    or None for any other module."""
    parts = name.split(".")
    for folder in (HERE / Path(*parts[:-1]), HERE.parent / "patch" / Path(*parts[:-1]), HERE.parent.parent / Path(*parts[:-1])):
        for f in (folder / f"{parts[-1]}.py", folder / parts[-1] / "__init__.py"):
            if f.is_file():
                return f.resolve()
    return None


def _imports(path):
    """Names of the modules a source file imports, anywhere in it (also inside functions)."""
    names = set()
    for node in ast.walk(ast.parse(path.read_bytes(), str(path))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


_models = {}


def model_hash(*modules):
    """Hash of the source of the given modules and of every module of this repository they import, directly or
    not: what a machine of a class from them does. A case module that only drives the machine is not part of it,
    so a new case does not make the kept boots unreachable."""
    if modules not in _models:
        seen, todo = set(), [f for f in map(_module_file, ("bootcache", "machine", *modules)) if f]
        while todo:
            f = todo.pop()
            if f in seen:
                continue
            seen.add(f)
            todo.extend(g for g in map(_module_file, _imports(f)) if g and g not in seen)
        h = hashlib.sha256()
        h.update(sys.version.split()[0].encode())
        h.update(repr(_unicorn_version()).encode())
        for f in sorted(seen):
            h.update(f.name.encode())
            h.update(f.read_bytes())
        _models[modules] = h.hexdigest(), frozenset(seen)
    return _models[modules][0]


PLAIN = (int, float, str, bytes, bool, type(None), tuple, frozenset)
_in_model = {}


def model_now(*modules):
    """What the source does not show: the plain values of the model's modules and the members of their classes as
    they are in this process. A case may set machine.SLICE or put another function on a class before it boots."""
    model_hash(*modules)
    files = _models[modules][1]
    parts = []
    for module in list(sys.modules.values()):
        f = getattr(module, "__file__", None)
        if f and (f, files) not in _in_model:
            _in_model[(f, files)] = Path(f).resolve() in files
        if not f or not _in_model[(f, files)]:
            continue
        for k, v in sorted(vars(module).items()):
            if type(v) is bytes:
                parts.append((module.__name__, k, hashlib.sha256(v).digest()))
            elif type(v) in PLAIN:
                parts.append((module.__name__, k, repr(v)))
            elif isinstance(v, type) and v.__module__ == module.__name__:
                for name, member in sorted(vars(v).items()):
                    parts.append((module.__name__, k, name, repr(member) if type(member) in PLAIN else
                                  f"{getattr(member, '__module__', '')}.{getattr(member, '__qualname__', type(member).__name__)}"))
    return digest(*parts)


def _unicorn_version():
    try:
        from importlib.metadata import version
        return version("unicorn")
    except Exception:
        return None


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
    model = (cls.__module__, *([observer.__module__] if observer else []))
    key = digest("boot-v2", model_hash(*model), model_now(*model), cls.__module__, cls.__qualname__, observer and observer.__qualname__,
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


def _power_on_key(m, how):
    """The key of a run of `m` from power-on, or None when it cannot be kept: `m` has run already, a hook or a wrapped
    method watches it (a restore would skip what they see), or its card is not an image in memory."""
    import pickle
    import types
    import machine as emu
    if not enabled() or m.time_ns or m.insns or m.uc._callbacks:
        return None
    if any(isinstance(v, (types.FunctionType, types.MethodType)) for k, v in m.__dict__.items() if k not in emu.SNAP_SKIP):
        return None
    card = m.mmc.card
    if card is not None and not emu.card_in_memory(card):
        return None
    image = card.medium.data if card is not None else None
    if card is not None:
        card.medium.data = b""
    try:
        state = {k: v for k, v in m.__dict__.items() if k not in emu.SNAP_SKIP and k != "flash"}
        state["flash"] = {k: v for k, v in m.flash.__dict__.items() if k != "mem"}
        model = pickle.dumps(state, pickle.HIGHEST_PROTOCOL)
    finally:
        if card is not None:
            card.medium.data = image
    cls = type(m)
    # The registers one by one: the saved context of the library holds pointers of this process
    A = m.A
    regs = [m.uc.reg_read(r) for r in [A.UC_ARM_REG_R0 + i for i in range(13)] + [A.UC_ARM_REG_SP, A.UC_ARM_REG_LR, A.UC_ARM_REG_PC,
                                                                                  A.UC_ARM_REG_CPSR, A.UC_ARM_REG_SPSR]]
    return digest("power-on-v1", model_hash(cls.__module__), model_now(cls.__module__), cls.__module__, cls.__qualname__, how, tuple(m.uc.ctl_get_exits()),
                  regs, model, _ram(m), hashlib.sha256(m.flash.mem).digest(),
                  hashlib.sha256(image).digest() if image is not None else b"")


def _ram(m):
    """What the RAM holds before the first run. Mostly just what the machine was made with (the payload at 0xC0000000,
    its first page at 0, zeros elsewhere): then the payload's hash stands for it, found by comparing, which is quicker
    than hashing 128 MiB. RAM that someone wrote to before the run is hashed whole."""
    import machine as emu
    image = bytes(m.uc.mem_read(0xC0000000, m.image_size))
    plain = hashlib.sha256(image).digest() == m.image_sha and bytes(m.uc.mem_read(0, 0x1000)) == image[:0x1000]
    for base, size in emu.SNAP_REGIONS:
        start = m.image_size if base == 0xC0000000 else 0x1000 if base == 0 else 0
        for chunk in range(start, size, emu.SNAP_CHUNK):
            if not plain:
                break
            n = min(emu.SNAP_CHUNK, size - chunk)
            plain = m.uc.mem_read(base + chunk, n) == emu.ZERO_CHUNK[:n]
    if plain:
        return b"payload " + m.image_sha
    ram = hashlib.sha256()
    for base, size in emu.SNAP_REGIONS:
        for chunk in range(0, size, emu.SNAP_CHUNK):
            ram.update(m.uc.mem_read(base + chunk, min(emu.SNAP_CHUNK, size - chunk)))
    return ram.digest()


def power_on(m, seconds):
    """Run `m`, a machine that has not run yet, `seconds` of device time past the loading screens of Korg's builds
    (Machine.finish_boot): the same as `m.finish_boot(); m.run_until(seconds)`. When a machine in the same state, with
    the same card, ran that before, `m` is put into the state it ended in instead (Machine.restore, the card included);
    the machine, its flash and its card stay the objects the caller holds."""
    def run():
        m.finish_boot()
        m.run_until(m.time_ns / 1e9 + seconds)
    key = _power_on_key(m, repr(float(seconds)))
    if key is None:
        return run()
    blob = read("power-on", key)
    if blob is None:
        with _once("power-on", key):
            blob = read("power-on", key)          # another process may have made it while this one waited
            if blob is None:
                card = m.mmc.card
                base = bytes(card.medium.data) if card is not None else None
                run()
                if not m.asserts:
                    write("power-on", key, m.snapshot(card_base=base))
                return
    m.restore(blob)


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
