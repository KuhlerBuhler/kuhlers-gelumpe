# SPDX-License-Identifier: GPL-2.0-only
"""Independent emulator runs side by side.

The checks boot the firmware many times with different flash images and held keys, and
each boot is one thread of work. `run_tasks` hands such runs to a pool of worker processes
(Unicorn is not shared between them: each worker builds its own machines) and returns the
results in the order of the tasks. What every task needs and nobody changes, the firmware
and the flash, goes to each worker once as `shared`.

A task is (module, function, args): the function is looked up by name in the worker and
called with `args`; it finds `parallel.shared` there. GELUMPE_JOBS sets the number of
workers (default: one less than the cores, so the machine stays usable; 2 while the 1-minute load average is above the core count, 1 above twice
that); 1 runs everything in this process, in order. A worker ends with the process that started the pool
(lifetime.py), also when that one is killed.

With `cache`, a task whose inputs and used files are unchanged is not run again (taskcache.py); each task that does run
then gets a process of its own, so the list of what it used holds only what it used. While a task runs, the clock that
dates the files of a card image (fat32.clock) stands at one fixed time: the same case builds the same card on every run,
which a boot snapshot with a card in the slot needs (bootcache.py).
"""

import contextlib
import importlib
import math
import multiprocessing
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import lifetime

shared = {}
CARD_CLOCK = 1767225600.0           # 2026-01-01 00:00 UTC, the date on every file of a card a case builds


def default_jobs():
    """All cores but one, and fewer while the machine is already busy: other test runs and other tools start
    pools of their own, and a pool per run on top of that only makes every run slower."""
    cores = os.cpu_count() or 1
    jobs = max(1, cores - 1)
    try:
        load = os.getloadavg()[0]
    except (AttributeError, OSError):
        return jobs
    if load > 2 * cores:
        return 1
    if load > cores:
        return min(jobs, 2)
    return jobs


def workers(tasks):
    """How many processes `tasks` tasks get."""
    # GELUMPE_JOBS wins. The frozen service (the app's sidecar) calls multiprocessing.freeze_support() first thing
    # (server.py), so its spawned workers start; if they do not, run_tasks falls back to one process.
    wanted = int(os.environ.get("GELUMPE_JOBS") or 0) or default_jobs()
    return max(1, min(wanted, tasks))


def _init(data, owner, track=False):
    global shared
    if track:
        import taskcache
        taskcache.watch()
    shared = data
    # A worker whose pool owner was killed would finish its task and then wait for work that never comes.
    # The owner is passed in: a worker that starts after that has no parent left to ask.
    lifetime.exit_with_parent(owner)


# Tasks that return check.py entries: a list of them, or (boot_case_task) one. An exception inside such a case must not take the
# whole check down (the app shows only "Emulator konnte nicht starten"): it becomes a failed entry that says what went wrong.
ENTRY_LISTS = {"cases_task", "switch_cases_task", "settings_cases_task", "look_cases_task"}
ENTRY_ONE = {"boot_case_task"}


def crashed(module, name, args, error):
    import traceback
    frame = traceback.extract_tb(error.__traceback__)[-1]
    where = f"{Path(frame.filename).name}:{frame.lineno}"
    group = f" {args[0]}" if args else ""
    return {"id": f"{module.removesuffix('_cases')}:crashed", "ok": False,
            "detail": f"the cases of {module}{group} stopped with {type(error).__name__}: {error} (at {where}); the others ran"}


def _picklable(error):
    import pickle
    try:
        pickle.loads(pickle.dumps(error))
        return True
    except Exception:
        return False


def _run(module, name, args):
    """(result, finished): finished is False when an exception became a failed entry."""
    import fat32
    frozen_here = getattr(sys, "frozen", False) and multiprocessing.parent_process() is None
    clock = fat32.clock
    if not frozen_here:                  # the app's service dates the files of the user's card with this clock too
        fat32.clock = lambda: CARD_CLOCK
    try:
        return getattr(importlib.import_module(module), name)(*args), True
    except Exception as error:
        if name in ENTRY_LISTS:
            return [crashed(module, name, args, error)], False
        if name in ENTRY_ONE:
            return crashed(module, name, args, error), False
        if multiprocessing.parent_process() is not None and not _picklable(error):
            # Unicorn's UcError cannot be rebuilt from a pickle: the pool would only report a broken process
            raise RuntimeError(f"{type(error).__name__}: {error}") from error
        raise
    finally:
        fat32.clock = clock


def _call(module, name, args):
    return _run(module, name, args)[0]


def _tracked(module, name, args):
    """(result, what the process used, seconds) for taskcache.py; None for a task that stopped with an exception."""
    import time
    import taskcache
    start = time.perf_counter()
    result, finished = _run(module, name, args)
    return result, taskcache.used() if finished else None, time.perf_counter() - start


@contextlib.contextmanager
def _without_main(on):
    """spawn starts each worker by running the script that started this process again (check.py imports every case
    module), and the worker would list all of them as used. While `on`, the script is hidden from spawn: a worker
    loads only what its task imports. The tasks name their functions by module, so the workers do not need it."""
    main = sys.modules.get("__main__")
    hidden = {}
    if on and main is not None:
        for name in ("__file__", "__spec__"):
            if getattr(main, name, None) is not None:
                hidden[name] = getattr(main, name)
        if "__file__" in hidden:
            del main.__file__
        if "__spec__" in hidden:
            main.__spec__ = None
    try:
        yield
    finally:
        if main is not None:
            vars(main).update(hidden)


def run_tasks(tasks, data, jobs=None, on_done=None, cache=None, on_queue=None):
    """Results of [(module, function name, args)] in task order. `on_done(index, result)` is called in the order the tasks finish. Exceptions of a task are raised here, except in the cases of the patches (ENTRY_LISTS), which become a failed entry.

    `cache` (a name for the kind of run) keeps each finished result with the files its task used (taskcache.py) and
    takes a kept one instead of running the task again; the tasks that run start longest first, by the time they took
    last, and `on_queue(indices)` hears that order."""
    global shared
    import taskcache
    keep = cache is not None and taskcache.enabled()
    out = [None] * len(tasks)
    todo = list(range(len(tasks)))
    if keep:
        base = taskcache.inputs(cache, data)
        keys = [taskcache.key(base, t) for t in tasks]
        todo = []
        for i, k in enumerate(keys):
            hit, result = taskcache.lookup(k)
            if hit:
                out[i] = result
                if on_done:
                    on_done(i, result)
            else:
                todo.append(i)
        took = taskcache.durations()
        todo.sort(key=lambda i: -took.get(repr(tasks[i]), math.inf))     # never seen counts as long
        if on_queue:
            on_queue(todo)
        seconds = {}

    def finish(i, value):
        if keep:
            value, deps, seconds[repr(tasks[i])] = value
            taskcache.store(keys[i], deps, value)
        out[i] = value
        if on_done:
            on_done(i, value)

    run = _tracked if keep else _call
    n = workers(len(todo)) if jobs is None else max(1, min(jobs, len(todo)))
    if n == 1 or not todo:
        before, shared = shared, data
        if keep:
            taskcache.watch()
        try:
            for i in todo:
                finish(i, run(*tasks[i]))
            return out
        finally:
            shared = before
            if keep:
                taskcache.note_durations(seconds)
    # spawn: the workers start clean, with no Unicorn state of this process copied into them. A worker per task
    # while results are kept, so that what a task used is all its process loaded (Python 3.11 and newer).
    fresh = {"max_tasks_per_child": 1} if keep and sys.version_info >= (3, 11) else {}
    try:
        with _without_main(keep), ProcessPoolExecutor(n, mp_context=multiprocessing.get_context("spawn"), initializer=_init,
                                                      initargs=(data, os.getpid(), keep), **fresh) as pool:
            futures = {pool.submit(run, *tasks[i]): i for i in todo}
            try:
                for f in as_completed(futures):
                    finish(futures[f], f.result())
            finally:
                if keep:
                    taskcache.note_durations(seconds)
            return out
    except BrokenProcessPool:
        # Workers that cannot start (a frozen build without worker support) end the pool at once: do it in this process.
        rest = [i for i in todo if out[i] is None]
        left = run_tasks([tasks[i] for i in rest], data, 1, None, cache)
        for i, value in zip(rest, left):
            out[i] = value
            if on_done:
                on_done(i, value)
        return out
