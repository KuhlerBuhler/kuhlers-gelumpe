# SPDX-License-Identifier: GPL-2.0-only
"""Progress of a check run: the tracker's snapshots, run_tasks' completion callback, check.py's stderr lines."""

import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parallel  # noqa: E402
import progress  # noqa: E402

TASKS = [("menu_cases", "cases_task", ()), ("dice_cases", "cases_task", (0,)), ("dice_cases", "cases_task", (1,)), ("bootmap", "scenario_task", ("a",))]


class TrackerTest(unittest.TestCase):
    def setUp(self):
        self.seen = []
        self.tracker = progress.Tracker(TASKS, 2, self.seen.append)

    def groups(self):
        return {g["id"]: g for g in self.seen[-1]["groups"]}

    def test_the_first_snapshot_knows_the_total_and_the_groups_before_anything_ran(self):
        first = self.seen[0]
        self.assertEqual((first["total"], first["done"]), (4, 0))
        self.assertEqual([(g["name"], g["total"]) for g in first["groups"]], [("Menü", 1), ("Würfeln", 2), ("Start", 1)])
        self.assertEqual([g["state"] for g in first["groups"]], ["running", "running", "waiting"], "the first two tasks are in flight")

    def test_a_finished_task_counts_its_entries_and_moves_the_running_window(self):
        self.tracker.done(0, [{"id": "a", "ok": True}, {"id": "b", "ok": True}])
        g = self.groups()
        self.assertEqual((g["menu_cases"]["state"], g["menu_cases"]["ok"], g["menu_cases"]["fail"]), ("done", 2, 0))
        self.assertEqual(g["dice_cases"]["state"], "running")
        self.assertEqual(self.seen[-1]["done"], 1)

    def test_a_group_with_a_failed_entry_ends_failed_once_all_its_tasks_are_in(self):
        self.tracker.done(1, [{"id": "a", "ok": False}, {"id": "b", "ok": True}])
        self.assertEqual(self.groups()["dice_cases"]["state"], "running", "one task of two is still out")
        self.tracker.done(2, [{"id": "c", "ok": True}])
        g = self.groups()["dice_cases"]
        self.assertEqual((g["state"], g["ok"], g["fail"]), ("failed", 2, 1))
        self.assertEqual(self.seen[-1]["fail"], 1)

    def test_a_boot_report_counts_as_one_and_asserts_make_it_fail(self):
        self.assertEqual(progress.counts({"asserts": []}), (1, 0))
        self.assertEqual(progress.counts({"asserts": ["x"]}), (0, 1))
        self.assertEqual(progress.counts({"id": "x", "ok": True}), (1, 0))


def square(n):
    return n * n


class RunTasksCallbackTest(unittest.TestCase):
    def test_on_done_hears_every_task_once_and_the_results_stay_in_task_order(self):
        tasks = [("math", "factorial", (n,)) for n in (3, 4, 5)]
        heard = []
        for jobs in (1, 2):
            heard.clear()
            out = parallel.run_tasks(tasks, {}, jobs, lambda i, r: heard.append((i, r)))
            self.assertEqual(out, [6, 24, 120])
            self.assertEqual(sorted(heard), [(0, 6), (1, 24), (2, 120)])

    def test_default_jobs_leave_one_core_free(self):
        import os
        cores = os.cpu_count() or 1
        self.assertLessEqual(parallel.default_jobs(), max(1, cores - 1))


class StderrLineTest(unittest.TestCase):
    def test_a_snapshot_is_one_json_line_on_stderr_and_nothing_on_stdout(self):
        err, out = io.StringIO(), io.StringIO()
        with redirect_stderr(err):
            progress.to_stderr({"total": 1, "done": 0, "groups": []})
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), {"progress": {"total": 1, "done": 0, "groups": []}})
        self.assertEqual(out.getvalue(), "")


class CheckEmitsTest(unittest.TestCase):
    def test_check_reports_every_task_it_runs_and_keeps_its_result(self):
        import check
        import bootcache
        import parallel as p
        ran = []
        original = (p.run_tasks, bootcache.cached_result)
        try:
            bootcache.cached_result = lambda kind, key, fn: fn()
            p.run_tasks = lambda tasks, data, jobs=None, on_done=None, cache=None, on_queue=None: [on_done(i, {"asserts": []}) or {"asserts": [], "blocks": {}, "image_read": b"", "events_ms": {}, "panel": {}, "dsp_uploads_ms": []} for i, _ in enumerate(tasks)]
            snapshots = []
            try:
                check.check(bytes(0x200100), bytes(0x200100), progress=snapshots.append)
            except Exception:
                pass          # the stand-in reports are too thin for the verdicts; the progress is what counts here
            ran = snapshots
        finally:
            p.run_tasks, bootcache.cached_result = original
        self.assertGreater(len(ran), 1)
        self.assertEqual(ran[0]["done"], 0)
        self.assertEqual(ran[-1]["done"], ran[-1]["total"])
        self.assertEqual({g["id"] for g in ran[0]["groups"]}, {"bootmap"})


if __name__ == "__main__":
    unittest.main()
