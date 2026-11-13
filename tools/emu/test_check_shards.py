# SPDX-License-Identifier: GPL-2.0-only
"""Shard transport and completeness without firmware or Unicorn."""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_shards


class ShardTest(unittest.TestCase):
    def setUp(self):
        self.tasks = [("toy", "cases_task", (i,)) for i in range(7)]
        self.results = [[{"id": str(i), "ok": True, "detail": "checked"}] for i in range(7)]

    def parts(self, count=3):
        return [check_shards.report("identity", self.tasks, index, count,
                                    [self.results[i] for i in check_shards.indices(len(self.tasks), index, count)])
                for index in range(1, count + 1)]

    def test_partition_covers_each_task_once_and_is_stable(self):
        groups = [check_shards.indices(7, i, 3) for i in range(1, 4)]
        self.assertEqual(groups, [[0, 3, 6], [1, 4], [2, 5]])
        self.assertEqual(sorted(i for group in groups for i in group), list(range(7)))

    def test_invalid_partition_is_refused(self):
        for index, count in [(0, 3), (4, 3), (1, 0), (-1, 2), (True, 2), (1, 2.5), (1, 65), (1, 10**12)]:
            with self.subTest(index=index, count=count), self.assertRaises(ValueError):
                check_shards.indices(7, index, count)

    def test_weights_spread_expensive_tasks_and_start_them_first(self):
        weights = [100 if i % 4 == 0 else 1 for i in range(16)]
        groups = [check_shards.indices(16, i, 4, weights=weights) for i in range(1, 5)]
        self.assertEqual(sorted(i for group in groups for i in group), list(range(16)))
        self.assertEqual([sum(weights[i] for i in group) for group in groups], [103] * 4)
        for group in groups:
            self.assertEqual([weights[i] for i in group], sorted((weights[i] for i in group), reverse=True))
        self.assertEqual(groups, [check_shards.indices(16, i, 4, weights=weights) for i in range(1, 5)])

    def test_equal_weights_keep_stable_index_ties_and_allow_empty_parts(self):
        self.assertEqual([check_shards.indices(7, i, 3, weights=[1] * 7) for i in range(1, 4)],
                         [[0, 3, 6], [1, 4], [2, 5]])
        self.assertEqual(check_shards.indices(2, 4, 4, weights=[2, 1]), [])
        self.assertEqual(check_shards.indices(0, 1, 4, weights=[]), [])

    def test_invalid_weights_are_refused(self):
        for weights in ([1], [1] * 8, [1] * 6 + [0], [1] * 6 + [-1], [1] * 6 + [True],
                        [1] * 6 + [1.5], {i: 1 for i in range(7)}):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                check_shards.indices(7, 1, 3, weights=weights)

    def test_weighted_reports_restore_canonical_order_and_reject_other_assignments(self):
        weights = [100, 1, 1, 1, 100, 1, 1]
        parts = [check_shards.report("identity", self.tasks, i, 3,
                                    [self.results[k] for k in check_shards.indices(7, i, 3, weights=weights)],
                                    weights=weights) for i in range(1, 4)]
        self.assertEqual(check_shards.join("identity", self.tasks, parts[::-1], weights=weights), self.results)
        with self.assertRaises(ValueError):
            check_shards.join("identity", self.tasks, parts, weights=[1] * 7)

    def test_empty_part_is_explicit_and_completes(self):
        self.assertEqual(check_shards.join("identity", self.tasks, self.parts(9)), self.results)

    def test_failed_empty_part_is_refused(self):
        parts = self.parts(9)
        parts[-1]["passed"] = False
        with self.assertRaises(ValueError):
            check_shards.join("identity", self.tasks, parts)

    def test_json_round_trip_preserves_original_task_order(self):
        parts = json.loads(json.dumps(self.parts()))
        self.assertEqual(check_shards.join("identity", self.tasks, parts[::-1]), self.results)
        self.assertTrue(all(p["passed"] for p in parts))
        self.assertTrue(all("ok" not in p for p in parts))

    def test_missing_duplicate_and_empty_reports_are_refused(self):
        parts = self.parts()
        for bad in [[], parts[:-1], parts + [parts[0]], [parts[0], parts[0], parts[2]]]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                check_shards.join("identity", self.tasks, bad)

    def test_wrong_identity_schema_version_and_partition_are_refused(self):
        mutations = [lambda p: p.update(identity="different"), lambda p: p.update(format="other"),
                     lambda p: p.update(version=2), lambda p: p["shard"].update(count=4),
                     lambda p: p["shard"].update(index=0), lambda p: p["shard"].update(index=True),
                     lambda p: p.update(passed=False)]
        for mutate in mutations:
            parts = self.parts()
            mutate(parts[0])
            with self.subTest(parts=parts), self.assertRaises(ValueError):
                check_shards.join("identity", self.tasks, parts)

    def test_missing_duplicate_foreign_and_misdescribed_tasks_are_refused(self):
        mutations = [lambda p: p["tasks"].pop(), lambda p: p["tasks"].append(copy.deepcopy(p["tasks"][0])),
                     lambda p: p["tasks"][0].update(index=1),
                     lambda p: p["tasks"][0].update(index=True),
                     lambda p: p["tasks"][0].update(task=["other", "cases_task", [0]])]
        for mutate in mutations:
            parts = self.parts()
            mutate(parts[0])
            with self.subTest(parts=parts), self.assertRaises(ValueError):
                check_shards.join("identity", self.tasks, parts)

    def test_failed_assertion_cannot_be_hidden_by_passed_flag(self):
        parts = self.parts()
        parts[0]["tasks"][0]["result"][0]["ok"] = False
        with self.assertRaises(ValueError):
            check_shards.join("identity", self.tasks, parts)

    def test_failed_task_is_a_failed_partial(self):
        self.results[0][0]["ok"] = False
        self.assertFalse(self.parts()[0]["passed"])

    def test_malformed_results_are_refused(self):
        for result in [None, "passed", {"ok": True}, [{"id": "x", "ok": 1}], [{"ok": True}]]:
            parts = self.parts()
            parts[0]["tasks"][0]["result"] = result
            with self.subTest(result=result), self.assertRaises(ValueError):
                check_shards.join("identity", self.tasks, parts)

    def test_boot_mask_round_trip_transports_ranges_and_no_bytes(self):
        task = ("bootmap", "scenario_task", ("normal",))
        result = {"blocks": {0xC0000000: 4}, "image_read": bytes([0, 1, 1, 0, 1]),
                  "events_ms": [[1, "screen_1"]], "panel": {"mode": 0}, "asserts": [], "dsp_uploads_ms": [1]}
        part = check_shards.report("identity", [task], 1, 1, [result])
        encoded = part["tasks"][0]["result"]
        self.assertNotIn("image_read", encoded)
        self.assertEqual(encoded["read_ranges"], [[1, 3], [4, 5]])
        round_trip = check_shards.join("identity", [task], json.loads(json.dumps([part])))
        self.assertEqual(round_trip, [result])

    def test_boot_mask_must_contain_only_zero_and_one(self):
        task = ("bootmap", "scenario_task", ("normal",))
        result = {"blocks": {}, "image_read": b"firmware", "events_ms": [], "panel": {},
                  "asserts": [], "dsp_uploads_ms": []}
        with self.assertRaises(ValueError):
            check_shards.report("identity", [task], 1, 1, [result])

    def test_zero_length_unicorn_blocks_survive_the_transport(self):
        task = ("bootmap", "scenario_task", ("normal",))
        result = {"blocks": {0xC0000000: 0, 0xC0000004: 4}, "image_read": bytes(5),
                  "events_ms": [], "panel": {}, "asserts": [], "dsp_uploads_ms": []}
        part = check_shards.report("identity", [task], 1, 1, [result])
        self.assertEqual(check_shards.join("identity", [task], json.loads(json.dumps([part]))), [result])

    def test_unknown_binary_result_is_never_serialized(self):
        with self.assertRaises(ValueError):
            check_shards.report("identity", self.tasks, 1, 3, [[{"id": "x", "ok": True, "detail": b"RAM"}]] * 3)

    def test_power_off_failures_are_detected_before_join(self):
        task = ("power_off_cases", "run_task", ("mains",))
        part = check_shards.report("identity", [task], 1, 1, [{"name": "mains", "asserts": ["broken"]}])
        self.assertFalse(part["passed"])

    def test_identity_binds_source_inputs_configuration_and_plan(self):
        data, config = {"payload": b"first", "flash": None}, {"allow": [[1, 2]]}
        original = check_shards.identity(data, self.tasks, config, "source")
        self.assertEqual(original, check_shards.identity(data, self.tasks, config, "source"))
        alternatives = [({"payload": b"second", "flash": None}, self.tasks, config, "source"),
                        (data, self.tasks, {"allow": []}, "source"),
                        (data, self.tasks[:-1], config, "source"), (data, self.tasks, config, "other")]
        for args in alternatives:
            self.assertNotEqual(original, check_shards.identity(*args))

    def test_source_identity_binds_tracked_data_and_new_python_but_not_ignored_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "tools/emu").mkdir(parents=True)
            (root / "tools/patch").mkdir()
            data = root / "data/values.json"
            data.write_text('{"version": 1}')
            code = root / "tools/emu/new.py"
            code.write_text("VALUE = 1\n")

            def source(revision="head"):
                with patch.object(check_shards.subprocess, "check_output", side_effect=[revision, b"data/values.json\0"]):
                    return check_shards.source_identity(root)

            original = source()
            (root / "ignored.bin").write_bytes(b"synthetic")
            self.assertEqual(source(), original)
            self.assertNotEqual(source("other-head"), original)
            data.write_text('{"version": 2}')
            changed_data = source()
            self.assertNotEqual(changed_data, original)
            code.write_text("VALUE = 2\n")
            self.assertNotEqual(source(), changed_data)


try:
    import check
except ImportError:
    check = None


@unittest.skipIf(check is None, "Unicorn not installed")
class CheckIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.source = patch.object(check_shards, "source_identity", return_value="source")
        self.source.start()
        self.addCleanup(self.source.stop)

    def fake_run(self, tasks, *args, **kwargs):
        return [[{"id": "dsp:stand_in", "ok": True, "detail": ""}] if t[0] == "dsp_cases" else
                {"blocks": {}, "image_read": bytes(check.PAYLOAD), "events_ms": [[1, "screen_1"]],
                 "panel": {"mode": 0, "held": check.KILL_SWITCH}, "asserts": [], "dsp_uploads_ms": [1]} for t in tasks]

    def test_join_binds_weights_even_when_they_produce_the_same_assignments(self):
        image = bytes(check.HEADER + check.PAYLOAD)
        with patch("shard_weights.weights_for", side_effect=lambda tasks: [10] * len(tasks)), \
                patch.object(check.parallel, "run_tasks", self.fake_run):
            parts = [check.check(image, image, quick=True, shard=(i, 2)) for i in range(1, 3)]
        with patch("shard_weights.weights_for", side_effect=lambda tasks: [20] * len(tasks)), self.assertRaises(ValueError):
            check.check(image, image, quick=True, reports=parts)

    def test_unsharded_checks_do_not_read_the_partition_profile(self):
        image = bytes(check.HEADER + check.PAYLOAD)
        with patch.dict(os.environ, {"GELUMPE_CACHE": "off"}), \
                patch("shard_weights.weights_for", side_effect=AssertionError("unsharded profile read")), \
                patch.object(check.parallel, "run_tasks", self.fake_run):
            result = check.check(image, image, quick=True)
        self.assertIn("quick", [entry["id"] for entry in result["checks"]])

    def test_partial_metrics_describe_the_expected_partition_cost(self):
        image = bytes(check.HEADER + check.PAYLOAD)
        with patch("shard_weights.weights_for", side_effect=lambda tasks: [20] * len(tasks)), \
                patch.object(check.parallel, "run_tasks", self.fake_run):
            part = check.check(image, image, quick=True, shard=(1, 4))
        self.assertIn({"kind": "partition", "algorithm": "lpt-v1", "index": 1, "count": 4,
                       "tasks": len(part["tasks"]), "estimated_ms": 20 * len(part["tasks"])}, part["metrics"])

    def test_shards_and_unsharded_use_the_same_complete_evaluation(self):
        image = bytes(check.HEADER + check.PAYLOAD)
        with patch.dict(os.environ, {"GELUMPE_CACHE": "off"}), patch.object(check.parallel, "run_tasks", self.fake_run):
            ordinary = check.check(image, image, quick=True)
            parts = [check.check(image, image, quick=True, shard=(i, 4)) for i in range(1, 5)]
            merged = check.check(image, image, quick=True, reports=json.loads(json.dumps(parts)))
        self.assertEqual(merged, ordinary)
        self.assertEqual(sum(len(p["tasks"]) for p in parts), len(check.scenario_names(None)) + 1)     # + the DSP interface cases
        self.assertTrue(all(p["format"] == "gelumpe-check-shard" for p in parts))

    def test_join_never_runs_tasks(self):
        image = bytes(check.HEADER + check.PAYLOAD)
        with patch.dict(os.environ, {"GELUMPE_CACHE": "off"}), patch.object(check.parallel, "run_tasks", self.fake_run):
            parts = [check.check(image, image, quick=True, shard=(i, 2)) for i in range(1, 3)]
        with patch.object(check.parallel, "run_tasks", side_effect=AssertionError("join ran a task")):
            check.check(image, image, quick=True, reports=parts)

    def test_join_refuses_different_allowed_spans_and_inputs(self):
        image = bytes(check.HEADER + check.PAYLOAD)
        with patch.object(check.parallel, "run_tasks", self.fake_run):
            parts = [check.check(image, image, quick=True, shard=(i, 2)) for i in range(1, 3)]
        with self.assertRaises(ValueError):
            check.check(image, image, quick=True, allow=[(1, 2)], reports=parts)
        changed = bytearray(image)
        changed[-1] = 1
        with self.assertRaises(ValueError):
            check.check(image, changed, quick=True, reports=parts)

    def test_join_refuses_different_execution_environment(self):
        image = bytes(check.HEADER + check.PAYLOAD)
        with patch.dict(os.environ, {"E2_SHARD_TEST_CONFIG": "first"}), patch.object(check.parallel, "run_tasks", self.fake_run):
            parts = [check.check(image, image, quick=True, shard=(i, 2)) for i in range(1, 3)]
        with patch.dict(os.environ, {"E2_SHARD_TEST_CONFIG": "second"}), self.assertRaises(ValueError):
            check.check(image, image, quick=True, reports=parts)

    def test_join_refuses_different_unicorn_version(self):
        image = bytes(check.HEADER + check.PAYLOAD)
        with patch.object(check.taskcache, "_unicorn", return_value="first"), patch.object(check.parallel, "run_tasks", self.fake_run):
            parts = [check.check(image, image, quick=True, shard=(i, 2)) for i in range(1, 3)]
        with patch.object(check.taskcache, "_unicorn", return_value="second"), self.assertRaises(ValueError):
            check.check(image, image, quick=True, reports=parts)


if __name__ == "__main__":
    unittest.main()
