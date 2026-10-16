# SPDX-License-Identifier: GPL-2.0-only
"""Let a process end together with the one that started it.

A parent that is killed hard (SIGKILL, a crashed test runner, a timeout kill) cannot stop what it
started, and the children go on with parent 1: emulator services that hold a port and a temporary
card folder, pool workers that hold a CPU. So everything started for a test run, a window or a
pool watches its parent and leaves when the parent is gone.

`watch` calls a function from a thread once any of the given processes has ended (the service uses
it to stop through its own save path). `exit_with_parent` is for processes with nothing to save,
one-shot tools and pool workers: they end at once. A tool is told who its parent is through
GELUMPE_PARENT_PID, because it cannot know whether the process in between is a shell.
"""

import os
import sys
import threading
import time

ENV = "GELUMPE_PARENT_PID"
INTERVAL_S = 1.0
START_PARENT = os.getppid()       # the process that started this one, as seen at import


def alive(pid):
    """Whether process `pid` still runs. For the direct parent the question is whether this process was
    reparented, which cannot be fooled by a reused pid."""
    if sys.platform == "win32":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, pid)   # SYNCHRONIZE
        if not handle:
            return False
        gone = ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0
        ctypes.windll.kernel32.CloseHandle(handle)
        return not gone
    if pid == START_PARENT:
        return os.getppid() == pid
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        pass
    return True


def watch(pids, on_gone, interval=INTERVAL_S):
    """Call `on_gone()` once, from a daemon thread, when any process in `pids` has ended."""
    pids = [p for p in pids if p]
    if not pids:
        return None

    def loop():
        while all(alive(p) for p in pids):
            time.sleep(interval)
        on_gone()

    thread = threading.Thread(target=loop, daemon=True, name="parent-watch")
    thread.start()
    return thread


def leave():
    os._exit(1)       # nothing to save, and a thread cannot interrupt a worker deep in the CPU emulation any other way


def exit_with_parent(pid=None):
    """End this process as soon as `pid` is gone. Default: the process named by GELUMPE_PARENT_PID, if any."""
    if pid is None:
        text = os.environ.get(ENV, "")
        pid = int(text) if text.isdigit() else 0
    return watch([pid], leave)
