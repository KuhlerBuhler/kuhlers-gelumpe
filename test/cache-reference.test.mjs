import { test } from "node:test";
import assert from "node:assert/strict";
import { compareShards, tapSummary, compareSmoke } from "../tools/ci/cache-reference.mjs";

function shard(cached = false) {
  const tasks = [0, 1].map(index => ({ index, task: ["own_cases", "cases_task", [index]], result: [{ id: `own_${index}`, ok: true }] }));
  return { format: "gelumpe-verification-shard", version: 1, input: "a", output: "b", set: "own", source: "fixed",
    report: { format: "gelumpe-check-shard", version: 1, identity: "f".repeat(64), passed: true,
      shard: { index: 1, count: 4 }, tasks,
      metrics: [{ kind: "pool", tasks: 2, workers: cached ? 0 : 4, cpus: 4, cache_hits: cached ? 2 : 0 },
        ...tasks.map(({ task }) => ({ kind: "task", task, cached, seconds: cached ? 0 : 1 }))] } };
}

test("cold and reused results remain identical while their cache metrics differ", () => {
  const summary = compareShards(shard(), shard(true));
  assert.equal(summary.tasks, 2);
  assert.equal(summary.cold.cacheHits, 0);
  assert.equal(summary.warm.cacheHits, 2);
  assert.equal(summary.warm.workers, 0);
});

test("a changed input, source, assignment, or result refuses the measurement", () => {
  for (const change of [s => s.input = "other", s => s.source = "other",
    s => s.report.shard.index = 2, s => s.report.tasks[0].result[0].ok = false,
    s => s.report.tasks.reverse(), s => s.report.passed = false, s => s.report.version = 2, s => s.report.identity = "invalid"]) {
    const warm = shard(true); change(warm);
    assert.throws(() => compareShards(shard(), warm));
  }
});

test("non-cold reference and unused warm cache are not a completed comparison", () => {
  assert.throws(() => compareShards(shard(true), shard(true)), /cold/);
  assert.throws(() => compareShards(shard(), shard()), /warm/);
});

test("missing, duplicated or conflicting task metrics cannot prove reuse", () => {
  for (const change of [s => s.report.metrics.pop(), s => s.report.metrics[0].cache_hits = 1,
    s => s.report.metrics[2].task = s.report.metrics[1].task,
    s => s.report.metrics[1].cached = "true"]) {
    const warm = shard(true); change(warm);
    assert.throws(() => compareShards(shard(), warm));
  }
});

const tap = `TAP version 13\n# Subtest: own sample\nok 1 - own sample\n  ---\n  duration_ms: 2\n  ...\n1..2\n# tests 2\n# pass 1\n# fail 0\n# cancelled 0\n# skipped 1\n`;
test("smoke comparison ignores duration but retains executed test names and skips", () => {
  const summary = compareSmoke(tap, tap.replace("duration_ms: 2", "duration_ms: 9"));
  assert.equal(summary.tests, 2);
  assert.equal(summary.pass, 1);
  assert.throws(() => compareSmoke(tap, tap.replaceAll("own sample", "other sample")));
});

test("failed, cancelled, all-skipped or incomplete TAP is refused", () => {
  for (const text of ["", tap.replace("# fail 0", "# fail 1"),
    tap.replace("# cancelled 0", "# cancelled 1"), tap.replace("# pass 1", "# pass 0"),
    tap.replace("# tests 2", "# tests 3"), tap.replace("# skipped 1\n", "")]) {
    assert.throws(() => tapSummary(text));
  }
});

test("partial warm reuse is measured honestly when an uncached task has equal results", () => {
  const warm = shard(true);
  warm.report.metrics[0].cache_hits = 1;
  warm.report.metrics[0].workers = 1;
  warm.report.metrics[2].cached = false;
  warm.report.metrics[2].seconds = 1;
  const result = compareShards(shard(), warm);
  assert.equal(result.warm.cacheHits, 1);
  assert.equal(result.warm.executed, 1);
});
