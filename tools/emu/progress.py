# SPDX-License-Identifier: GPL-2.0-only
"""Progress of a check run (check.py): which groups of tasks there are, which run, which are done.

A group is the tasks of one case module, shown under one German name. The tracker is told when a task
finishes (parallel.run_tasks, on_done) and passes a snapshot to `emit` each time:

    {"total": 331, "done": 40, "ok": 40, "fail": 0,
     "groups": [{"id": "menu_cases", "name": "Menü", "total": 3, "done": 1, "state": "running", "ok": 12, "fail": 0}, ...]}

`total` and `done` count tasks (one boot or one case group each), `ok` and `fail` count the check entries
they returned, so ok + fail is not the same number as done. A task counts as running while it is among the first
`jobs` that have not finished: the pool hands tasks out in order.
"""

import json
import sys

NAMES = {
    "bootmap": "Start",
    "splash_cases": "Startbild",
    "mfx_cases": "MFX 2",
    "menu_cases": "Menü",
    "pswitch_cases": "Pattern-Schalter",
    "tap_motion_cases": "TAP Motion",
    "note_assist_cases": "Notenassistent",
    "dice_cases": "Würfeln",
    "ifx_idle_cases": "Ruhender IFX",
    "shortcut_cases": "EXIT-Shortcuts",
    "loadbar_cases": "Ladebalken",
    "sample_error_cases": "Sample-Fehler",
    "synth_filter_cases": "Synth-Filter",
    "sysex_cases": "SysEx",
    "power_off_cases": "Ausschalten",
    "preset_cases": "Presets",
}


def counts(result):
    """(ok, fail) of what a task returned: check entries, one entry, or a boot report (counts as one)."""
    if isinstance(result, list):
        entries = result
    elif isinstance(result, dict) and "ok" in result:
        entries = [result]
    elif isinstance(result, dict) and "asserts" in result:
        return (0, 1) if result["asserts"] else (1, 0)
    else:
        return 1, 0
    ok = sum(1 for e in entries if e.get("ok"))
    return ok, len(entries) - ok


class Tracker:
    def __init__(self, tasks, jobs, emit):
        self.modules = [t[0] for t in tasks]
        self.jobs = max(1, jobs)
        self.emit = emit
        self.finished = [False] * len(tasks)
        self.ok = {}
        self.fail = {}
        self.order = list(dict.fromkeys(self.modules))
        self.send()

    def done(self, index, result):
        if self.finished[index]:
            return                    # a pool that broke and was run again in one process reports a task twice
        self.finished[index] = True
        ok, fail = counts(result)
        module = self.modules[index]
        self.ok[module] = self.ok.get(module, 0) + ok
        self.fail[module] = self.fail.get(module, 0) + fail
        self.send()

    def snapshot(self):
        pending = [m for m, f in zip(self.modules, self.finished) if not f]
        running = set(pending[:self.jobs])
        groups = []
        for module in self.order:
            total = self.modules.count(module)
            done = sum(1 for m, f in zip(self.modules, self.finished) if m == module and f)
            fail = self.fail.get(module, 0)
            state = "done" if done == total else "running" if module in running else "waiting"
            if fail and done == total:
                state = "failed"
            groups.append({"id": module, "name": NAMES.get(module, module), "total": total, "done": done, "state": state,
                           "ok": self.ok.get(module, 0), "fail": fail})
        done = sum(self.finished)
        return {"total": len(self.finished), "done": done, "ok": sum(self.ok.values()), "fail": sum(self.fail.values()), "groups": groups}

    def send(self):
        self.emit(self.snapshot())


def to_stderr(snapshot):
    """One JSON line per snapshot on stderr; stdout stays the final result."""
    print(json.dumps({"progress": snapshot}, ensure_ascii=False), file=sys.stderr, flush=True)
