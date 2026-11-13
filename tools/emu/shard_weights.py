# SPDX-License-Identifier: GPL-2.0-only
"""Reproducible millisecond estimates for deterministic task partitions."""

import argparse
import json
import math
from pathlib import Path
import statistics

FORMAT = "gelumpe-shard-weights"
VERSION = 1
PROFILE = Path(__file__).with_name("shard-weights.json")
MAX_MILLISECONDS = 86_400_000


def task_key(task):
    if (not isinstance(task, (tuple, list)) or len(task) != 3
            or any(not isinstance(value, str) or not value for value in task[:2])
            or not isinstance(task[2], (tuple, list))):
        raise ValueError("a task needs a module, function and argument list")
    try:
        return json.dumps(task, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("task arguments must be JSON values") from error


def profile(events, source):
    samples = {}
    for event in events:
        if event.get("kind") != "task" or event.get("cached") is True:
            continue
        if event.get("cached") is not False:
            raise ValueError("a task measurement must explicitly be uncached")
        seconds = event.get("seconds")
        if (type(seconds) not in (int, float) or not math.isfinite(seconds)
                or not 0 < seconds <= MAX_MILLISECONDS / 1000):
            raise ValueError("a task measurement needs a positive finite duration of at most one day")
        samples.setdefault(task_key(event.get("task")), []).append(seconds)
    if not samples:
        raise ValueError("no executed task measurements")
    return {"format": FORMAT, "version": VERSION, "source": source,
            "tasks": [{"task": json.loads(key), "milliseconds": max(1, round(statistics.median(values) * 1000)),
                       "samples": len(values)} for key, values in sorted(samples.items())]}


def weights_for(tasks, path=PROFILE):
    data = json.loads(Path(path).read_text())
    if (not isinstance(data, dict) or data.get("format") != FORMAT
            or type(data.get("version")) is not int or data["version"] != VERSION
            or not isinstance(data.get("tasks"), list) or not data["tasks"]):
        raise ValueError("not a supported shard weight profile")
    weights = {}
    for row in data["tasks"]:
        if not isinstance(row, dict):
            raise ValueError("a shard weight needs a task and milliseconds")
        key = task_key(row.get("task"))
        milliseconds = row.get("milliseconds")
        if type(milliseconds) is not int or not 0 < milliseconds <= MAX_MILLISECONDS or key in weights:
            raise ValueError("a shard weight must be unique and have positive integer milliseconds of at most one day")
        weights[key] = milliseconds
    unknown = max(weights.values())
    return [weights.get(task_key(task), unknown) for task in tasks]


def measurements(paths):
    for path in paths:
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and isinstance(event.get("metrics"), dict):
                yield event["metrics"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", type=Path, nargs="+")
    parser.add_argument("--source", required=True, help="revision of the measured test tasks")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = profile(measurements(args.logs), args.source)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(result['tasks'])} task estimates written to {args.output}")


if __name__ == "__main__":
    main()
