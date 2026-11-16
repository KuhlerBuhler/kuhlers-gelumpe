# SPDX-License-Identifier: GPL-2.0-only
import copy
import json
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

import shard_weights


class WeightProfileTest(unittest.TestCase):
    def event(self, seconds, task=None, cached=False):
        return {"kind": "task", "task": task or ["toy", "cases_task", [0]], "seconds": seconds, "cached": cached}

    def write_profile(self, profile):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "weights.json"
        path.write_text(json.dumps(profile))
        return path

    def test_generator_uses_uncached_median_and_is_independent_of_log_order(self):
        events = [self.event(1), self.event(9), self.event(2), self.event(0, cached=True), {"kind": "pool"}]
        profile = shard_weights.profile(events, "source")
        self.assertEqual(profile, shard_weights.profile(events[::-1], "source"))
        self.assertEqual(profile["tasks"], [{"task": ["toy", "cases_task", [0]], "milliseconds": 2000, "samples": 3}])

    def test_unknown_tasks_get_the_longest_known_estimate(self):
        profile = shard_weights.profile([self.event(1), self.event(8, ["other", "cases_task", []])], "source")
        path = self.write_profile(profile)
        tasks = [("toy", "cases_task", (0,)), ("new", "cases_task", ())]
        self.assertEqual(shard_weights.weights_for(tasks, path), [1000, 8000])
        self.assertEqual(shard_weights.weights_for([], path), [])

    def test_duplicate_malformed_and_empty_profiles_are_refused(self):
        original = shard_weights.profile([self.event(1)], "source")
        mutations = [lambda p: p.update(format="other"), lambda p: p.update(version=True),
                     lambda p: p.update(version=2), lambda p: p.update(tasks=[]),
                     lambda p: p["tasks"].append(copy.deepcopy(p["tasks"][0])),
                     lambda p: p["tasks"][0].update(task=["toy", "cases_task"])]
        for value in (0, -1, True, 1.5, 86_400_001):
            mutations.append(lambda p, value=value: p["tasks"][0].update(milliseconds=value))
        for mutate in mutations:
            profile = copy.deepcopy(original)
            mutate(profile)
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                shard_weights.weights_for([("toy", "cases_task", (0,))], self.write_profile(profile))

    def test_empty_or_invalid_measurements_cannot_generate_a_profile(self):
        for events in ([], [self.event(0, cached=True)], [self.event(-1)], [self.event(float("nan"))],
                       [self.event(True)], [self.event(1, ["toy", "cases_task"])]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                shard_weights.profile(events, "source")

    def test_missing_profile_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            shard_weights.weights_for([("toy", "cases_task", ())], Path("not-a-shard-profile.json"))

    def test_cli_reproduces_the_same_profile_from_metric_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            log = root / "stderr.log"
            events = [self.event(1), self.event(3), self.event(5), self.event(0, cached=True)]
            log.write_text("diagnostic\n" + "\n".join(json.dumps({"metrics": event}) for event in events))
            outputs = [root / "first.json", root / "second.json"]
            for path in outputs:
                result = subprocess.run([sys.executable, str(Path(shard_weights.__file__)), "--source", "source",
                                         "--output", str(path), str(log)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
            self.assertEqual(shard_weights.weights_for([("toy", "cases_task", (0,))], outputs[0]), [3000])


if __name__ == "__main__":
    unittest.main()
