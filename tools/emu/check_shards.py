# SPDX-License-Identifier: GPL-2.0-only
"""Transport independent check tasks and require every partition before combining them."""

import hashlib
import heapq
import json
import subprocess

FORMAT = "gelumpe-check-shard"
VERSION = 1


def indices(total, index, count, weights=None):
    if type(index) is not int or type(count) is not int or not 1 <= count <= 64 or not 1 <= index <= count:
        raise ValueError("a shard is I/N with 1 <= I <= N <= 64")
    if weights is None:
        return list(range(index - 1, total, count))
    if (not isinstance(weights, (tuple, list)) or len(weights) != total
            or any(type(value) is not int or value <= 0 for value in weights)):
        raise ValueError("a partition needs one positive integer weight per task")
    groups = [[] for _ in range(count)]
    pool = [(0, 0, i) for i in range(count)]
    for task in sorted(range(total), key=lambda i: (-weights[i], i)):
        load, size, part = heapq.heappop(pool)
        groups[part].append(task)
        heapq.heappush(pool, (load + weights[task], size + 1, part))
    return groups[index - 1]


def _json(value):
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise ValueError("task results must contain JSON values, never firmware or RAM bytes") from error


def identity(data, tasks, configuration, source):
    inputs = {name: hashlib.sha256(value).hexdigest() if isinstance(value, (bytes, bytearray, memoryview)) else value
              for name, value in data.items()}
    text = json.dumps([VERSION, inputs, tasks, configuration, source], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def source_identity(root):
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    digest = hashlib.sha256(revision.encode())
    for name in sorted(n for n in names if n):
        path = root / name
        digest.update(name.encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest() if path.is_file() else b"missing")
    # New source files in a working checkout have no entry in the Git index yet.
    for folder in (root / "tools/emu", root / "tools/patch"):
        for path in sorted(folder.glob("*.py")):
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _encode(task, result):
    if task[:2] != ("bootmap", "scenario_task"):
        return _json(result)
    result = dict(result)
    mask = result.pop("image_read")
    if not isinstance(mask, (bytes, bytearray)) or any(b not in (0, 1) for b in mask):
        raise ValueError("a boot read mask contains only zero and one")
    ranges, i = [], mask.find(1)
    while i >= 0:
        j = mask.find(0, i)
        j = len(mask) if j < 0 else j
        ranges.append([i, j])
        i = mask.find(1, j)
    result["blocks"] = sorted([at, size] for at, size in result["blocks"].items())
    result.update(read_size=len(mask), read_ranges=ranges)
    return _json(result)


def _decode(task, result, read_size=None):
    if task[:2] != ("bootmap", "scenario_task"):
        return result
    if not isinstance(result, dict):
        raise ValueError("a boot result must be an object")
    result = dict(result)
    size = result.pop("read_size", None)
    ranges = result.pop("read_ranges", None)
    if type(size) is not int or not 0 <= size <= 16 * 1024 * 1024 or read_size is not None and size != read_size:
        raise ValueError("invalid boot mask size")
    if not isinstance(ranges, list):
        raise ValueError("a boot result needs read ranges")
    mask, end = bytearray(size), 0
    for pair in ranges:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("invalid boot read range")
        lo, hi = pair
        if type(lo) is not int or type(hi) is not int or not end <= lo < hi <= size:
            raise ValueError("invalid boot read range")
        mask[lo:hi] = b"\1" * (hi - lo)
        end = hi
    blocks = result.get("blocks")
    if not isinstance(blocks, list) or any(not isinstance(p, list) or len(p) != 2
                                         or type(p[0]) is not int or type(p[1]) is not int or p[1] < 0 for p in blocks):
        raise ValueError("invalid boot code blocks")
    if len({p[0] for p in blocks}) != len(blocks):
        raise ValueError("duplicate boot code block")
    result.update(blocks=dict(blocks), image_read=bytes(mask))
    return result


def _passed(task, result):
    if task[0] in ("bootmap", "power_off_cases"):
        if not isinstance(result, dict) or not isinstance(result.get("asserts"), list):
            raise ValueError("a device task needs its assertion results")
        return not result["asserts"]
    entries = [result] if task[1] == "boot_case_task" else result
    if not isinstance(entries, list) or any(not isinstance(e, dict) or not isinstance(e.get("id"), str)
                                           or type(e.get("ok")) is not bool for e in entries):
        raise ValueError("a case task needs check entries with id and boolean ok")
    return all(e["ok"] for e in entries)


def report(fingerprint, tasks, index, count, results, *, weights=None):
    assigned = indices(len(tasks), index, count, weights=weights)
    if len(results) != len(assigned):
        raise ValueError("a shard needs exactly its assigned results")
    passed = all(_passed(tasks[i], r) for i, r in zip(assigned, results))
    return {"format": FORMAT, "version": VERSION, "identity": fingerprint, "shard": {"index": index, "count": count},
            "tasks": [{"index": i, "task": _json(tasks[i]), "result": _encode(tasks[i], r)} for i, r in zip(assigned, results)],
            "passed": passed}


def join(fingerprint, tasks, reports, read_size=None, *, weights=None):
    if not reports:
        raise ValueError("no shard results")
    out, seen, count = [None] * len(tasks), set(), None
    for part in reports:
        if not isinstance(part, dict) or part.get("format") != FORMAT or type(part.get("version")) is not int or part["version"] != VERSION:
            raise ValueError("invalid shard format or version")
        if part.get("identity") != fingerprint:
            raise ValueError("shard inputs, source or task plan differ")
        if part.get("passed") is not True:
            raise ValueError("a shard contains failed checks")
        shard = part.get("shard")
        if not isinstance(shard, dict):
            raise ValueError("missing shard partition")
        index, total = shard.get("index"), shard.get("count")
        assigned = indices(len(tasks), index, total, weights=weights)
        if count is None:
            count = total
        if total != count or index in seen:
            raise ValueError("inconsistent or duplicate shard partition")
        seen.add(index)
        rows = part.get("tasks")
        if not isinstance(rows, list) or len(rows) != len(assigned):
            raise ValueError("missing or extra task results")
        found = set()
        for row in rows:
            if not isinstance(row, dict) or type(row.get("index")) is not int:
                raise ValueError("invalid task index")
            i = row["index"]
            if i not in assigned or i in found or row.get("task") != _json(tasks[i]):
                raise ValueError("duplicate, foreign or misdescribed task")
            found.add(i)
            value = _decode(tasks[i], row.get("result"), read_size)
            if not _passed(tasks[i], value):
                raise ValueError("a shard contains failed checks")
            out[i] = value
    if seen != set(range(1, count + 1)) or any(value is None for value in out):
        raise ValueError("incomplete shard results")
    return out
