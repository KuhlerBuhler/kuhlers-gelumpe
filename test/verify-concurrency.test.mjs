import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const workflow = readFileSync(new URL("../.github/workflows/verify-patches.yml", import.meta.url), "utf8");
const context = (values = {}) => ({
  event_name: "pull_request", event: { pull_request: { number: 123 } },
  ref: "refs/pull/123/merge", run_id: 1000, run_attempt: 1, ...values,
});

function concurrency(github) {
  const block = workflow.match(/^concurrency:\n([\s\S]*?)(?=\n\S)/m)?.[1];
  assert.ok(block, "Verify patches needs workflow-level concurrency");
  const group = block.match(/  group: >-\n([\s\S]*?)\n  cancel-in-progress:/)?.[1];
  const cancel = block.match(/  cancel-in-progress: \$\{\{ ([^\n]+) \}\}/)?.[1];
  assert.ok(group && cancel, "workflow concurrency needs a group and cancellation condition");
  const evaluate = expression => runInNewContext(expression, {
    github,
    format: (template, ...values) => template.replace(/\{(\d+)\}/g, (_, index) => values[index]),
  });
  return {
    group: group.trim().replace(/\$\{\{([\s\S]*?)\}\}/g, (_, expression) => evaluate(expression)),
    cancel: evaluate(cancel),
  };
}

test("new automatic commits to the same PR replace the whole previous verification", () => {
  const first = concurrency(context());
  const next = concurrency(context({ run_id: 1001 }));
  assert.equal(first.group, next.group);
  assert.equal(next.cancel, true);
});

test("different PRs remain independent even when they use the same source branch", () => {
  const first = concurrency(context({ head_ref: "develop" }));
  const other = concurrency(context({ head_ref: "develop", event: { pull_request: { number: 124 } }, run_id: 1001 }));
  assert.notEqual(first.group, other.group);
});

test("pushes replace only earlier automatic pushes to the same branch", () => {
  const push = context({ event_name: "push", event: { pull_request: {} }, ref: "refs/heads/develop" });
  const first = concurrency(push);
  assert.equal(first.group, concurrency({ ...push, run_id: 1001 }).group);
  assert.equal(first.cancel, true);
  assert.notEqual(first.group, concurrency({ ...push, ref: "refs/heads/main" }).group);
});

test("a PR and a push from the same branch cannot cancel one another", () => {
  const pr = context({ ref: "refs/heads/develop", head_ref: "develop" });
  const push = { ...pr, event_name: "push", event: { pull_request: {} } };
  assert.notEqual(concurrency(pr).group, concurrency(push).group);
});

test("manual starts stay independent even for the same checked branch", () => {
  const manual = context({ event_name: "workflow_dispatch", event: { pull_request: {} }, ref: "refs/heads/develop" });
  const first = concurrency(manual);
  assert.equal(first.cancel, false);
  assert.notEqual(first.group, concurrency({ ...manual, run_id: 1001 }).group);
  assert.notEqual(first.group, concurrency(context()).group);
});

test("rerunning an old PR or push cannot replace the current automatic run", () => {
  for (const event_name of ["pull_request", "push"]) {
    const automatic = context({ event_name });
    const rerun = concurrency({ ...automatic, run_attempt: 2 });
    assert.equal(rerun.cancel, false);
    assert.notEqual(rerun.group, concurrency(automatic).group);
    assert.notEqual(rerun.group, concurrency({ ...automatic, run_attempt: 3 }).group);
    assert.notEqual(rerun.group, concurrency({ ...automatic, run_id: 1001, run_attempt: 2 }).group);
  }
});

test("manual reruns also stay independent and workflow groups do not collide", () => {
  const manual = context({ event_name: "workflow_dispatch", event: { pull_request: {} } });
  assert.notEqual(concurrency(manual).group, concurrency({ ...manual, run_attempt: 2 }).group);
  assert.match(concurrency(context()).group, /^verify-patches-/);
});

test("the shared firmware jobs leave cancellation to their caller workflows", () => {
  const shared = readFileSync(new URL("../.github/workflows/firmware-check.yml", import.meta.url), "utf8");
  const release = readFileSync(new URL("../.github/workflows/release.yml", import.meta.url), "utf8");
  assert.doesNotMatch(shared, /^\s+concurrency:/m, "nested groups must not cancel protected or unrelated caller runs");
  assert.match(workflow, /^concurrency:/m);
  assert.match(release, /^concurrency:\n  group: release\n  cancel-in-progress: false/m);
  assert.match(release, /uses: \.\/\.github\/workflows\/firmware-check\.yml/);
});
