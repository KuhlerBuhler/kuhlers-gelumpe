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
"""

import importlib
import multiprocessing
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import lifetime

shared = {}


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


def _init(data, owner):
    global shared
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


def _call(module, name, args):
    try:
        return getattr(importlib.import_module(module), name)(*args)
    except Exception as error:
        if name in ENTRY_LISTS:
            return [crashed(module, name, args, error)]
        if name in ENTRY_ONE:
            return crashed(module, name, args, error)
        raise


def run_tasks(tasks, data, jobs=None, on_done=None):
    """Results of [(module, function name, args)] in task order. `on_done(index, result)` is called in the order the tasks finish. Exceptions of a task are raised here, except in the cases of the patches (ENTRY_LISTS), which become a failed entry."""
    global shared
    n = workers(len(tasks)) if jobs is None else max(1, min(jobs, len(tasks)))
    if n == 1:
        before, shared = shared, data
        try:
            out = []
            for i, t in enumerate(tasks):
                out.append(_call(*t))
                if on_done:
                    on_done(i, out[-1])
            return out
        finally:
            shared = before
    # spawn: the workers start clean, with no Unicorn state of this process copied into them
    try:
        with ProcessPoolExecutor(n, mp_context=multiprocessing.get_context("spawn"), initializer=_init, initargs=(data, os.getpid())) as pool:
            futures = [pool.submit(_call, *t) for t in tasks]
            if on_done:
                index = {f: i for i, f in enumerate(futures)}
                for f in as_completed(futures):
                    on_done(index[f], f.result())
            return [f.result() for f in futures]
    except BrokenProcessPool:
        # Workers that cannot start (a frozen build without worker support) end the pool at once: do it in this process.
        return run_tasks(tasks, data, 1, on_done)
