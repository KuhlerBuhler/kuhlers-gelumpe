import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { REQUIRED, SELF, mergeProblems, runAutomerge } from "../tools/automerge.mjs";

const pr = (extra = {}) => ({ number: 12, baseRefName: "develop", headRefName: "feature/test", headRefOid: "abc123",
  isDraft: false, isCrossRepository: false, labels: [{ name: "automerge" }], ...extra });
const run = (id, name, extra = {}) => ({ id, name, workflow_id: name, event: "pull_request", check_suite_id: id * 10,
  status: "completed", conclusion: "success", ...extra });
const check = (id, name, extra = {}) => ({ id, name, status: "completed", conclusion: "success", check_suite: { id }, ...extra });
const green = () => ({ runs: [run(1, "Test"), run(2, "Verify patches"), run(3, "Korg data guard")],
  checks: REQUIRED.map((name, i) => check(i + 1, name)) });

test("only a labelled, non-draft pull request from this repository into develop may merge", () => {
  assert.deepEqual(mergeProblems(pr(), green()), []);
  for (const extra of [{ baseRefName: "main" }, { isDraft: true }, { isCrossRepository: true }, { labels: [] }]) {
    assert.ok(mergeProblems(pr(extra), green()).length, JSON.stringify(extra));
  }
});

test("every required check must succeed, including the aggregate firmware check", () => {
  assert.deepEqual(REQUIRED, ["unit", "browser", "guard", "patches"]);
  for (const name of REQUIRED) {
    const state = green();
    assert.ok(mergeProblems(pr(), { ...state, checks: state.checks.filter(c => c.name !== name) }).length);
    for (const conclusion of ["failure", "skipped", "neutral", "cancelled"]) {
      assert.ok(mergeProblems(pr(), { ...state, checks: state.checks.map(c => c.name === name ? { ...c, conclusion } : c) }).length);
    }
  }
});

test("pending workflows, pending checks, failed optional checks and newer failed reruns block the merge", () => {
  const state = green();
  assert.ok(mergeProblems(pr(), { ...state, runs: [...state.runs, run(9, "Build apps", { status: "queued", conclusion: null })] }).length);
  assert.ok(mergeProblems(pr(), { ...state, checks: [...state.checks, check(9, "native", { status: "in_progress", conclusion: null })] }).length);
  assert.ok(mergeProblems(pr(), { ...state, checks: [...state.checks, check(9, "native", { conclusion: "failure" })] }).length);
  assert.ok(mergeProblems(pr(), { ...state, checks: [...state.checks, check(20, "patches", { conclusion: "failure" })] }).length);
  assert.deepEqual(mergeProblems(pr(), { ...state, checks: [...state.checks, check(9, "native", { conclusion: "failure" }), check(10, "native")] }), []);
});

test("its own running or older failed decision does not hold up a later decision", () => {
  const state = green();
  state.runs.push(run(9, SELF, { status: "in_progress", conclusion: null }), run(8, SELF, { conclusion: "failure" }));
  state.checks.push(check(20, "automerge", { status: "in_progress", conclusion: null, check_suite: { id: 90 } }),
    check(21, "automerge", { conclusion: "failure", check_suite: { id: 80 } }));
  assert.deepEqual(mergeProblems(pr(), state), []);
});

test("superseded matrix names do not block a newer complete run, while unknown external checks still count", () => {
  const state = green();
  state.runs.push(run(8, "Verify patches"));
  state.checks.push(check(9, "red (1/4)", { conclusion: "cancelled", check_suite: { id: 20 } }),
    check(10, "red (1/2)", { check_suite: { id: 80 } }));
  assert.deepEqual(mergeProblems(pr(), state), []);
  assert.ok(mergeProblems(pr(), { ...state, checks: [...state.checks,
    check(11, "external", { conclusion: "failure", check_suite: { id: 999 } })] }).length);
  assert.ok(mergeProblems(pr(), { ...state, runs: [...state.runs,
    run(12, "Verify patches", { status: "queued", conclusion: null })] }).length);
});

function harness({ current = pr(), state = green(), dryRun = false, prs = [pr()], reject = [] } = {}) {
  const calls = [];
  const gh = (...args) => {
    calls.push(args);
    if (args[0] === "pr" && args[1] === "list") return JSON.stringify(prs);
    if (args[0] === "pr" && args[1] === "view") return JSON.stringify(current);
    if (args[0] === "api") {
      assert.ok(args.includes("--paginate") && args.includes("--slurp"));
      return JSON.stringify(args.at(-1).includes("actions/runs") ? [{ workflow_runs: state.runs }]
        : [{ check_runs: state.checks.slice(0, 2) }, { check_runs: state.checks.slice(2) }]);
    }
    if (args[0] === "pr" && args[1] === "merge") {
      if (reject.includes(Number(args[2]))) throw new Error("pull request cannot be cleanly merged");
      return "";
    }
    throw new Error(`unexpected call ${args}`);
  };
  runAutomerge({ repo: "owner/repo", gh, dryRun, log: () => {} });
  return calls.filter(args => args[0] === "pr" && args[1] === "merge");
}

test("merges only the freshly rechecked head with --match-head-commit", () => {
  const merges = harness();
  assert.equal(merges.length, 1);
  assert.deepEqual(merges[0], ["pr", "merge", "12", "-R", "owner/repo", "--merge", "--admin", "--match-head-commit", "abc123"]);
});

test("an old completion event cannot merge a new head or a PR whose label disappeared", () => {
  assert.deepEqual(harness({ current: pr({ headRefOid: "new-head" }) }), []);
  assert.deepEqual(harness({ current: pr({ labels: [] }) }), []);
  assert.deepEqual(harness({ current: pr({ isDraft: true }) }), []);
  assert.deepEqual(harness({ dryRun: true }), []);
  assert.deepEqual(harness({ state: { ...green(), checks: [] } }), []);
});

test("a conflicting ready pull request does not prevent an independent ready one from merging", () => {
  const merges = harness({ prs: [pr(), pr({ number: 13 })], reject: [12] });
  assert.deepEqual(merges.map(args => args[2]), ["12", "13"]);
});

test("the workflow wakes on completed checks, reads trusted code and never polls", () => {
  const yml = readFileSync(new URL("../.github/workflows/automerge.yml", import.meta.url), "utf8");
  assert.match(yml, /^  workflow_run:/m);
  assert.match(yml, /types: \[completed\]/);
  for (const name of ["Test", "Verify patches", "Korg data guard", "Update pull requests", "Build apps",
    "Container image", "Release", "Discord release", "Sync develop"]) assert.ok(yml.includes(name));
  assert.match(yml, /^  check_run:\n    types: \[completed\]/m);
  // runs that cannot touch a pull request into develop start nothing
  assert.match(yml, /types: \[completed\]\n {4}branches-ignore: \[main, develop, "release\/\*\*", "v\[0-9\]\*"\]/);
  assert.match(yml, /github\.event_name == 'workflow_run' && contains\(github\.event\.workflow_run\.pull_requests\.\*\.base\.ref, 'develop'\)/);
  assert.match(yml, /ref: develop\b/);
  assert.match(yml, /node tools\/automerge\.mjs/);
  assert.match(yml, /GH_TOKEN: \$\{\{ steps\.app\.outputs\.token \}\}/);
  assert.match(yml, /create-github-app-token@v2/);
  assert.doesNotMatch(yml, /sleep 60|while :|timeout-minutes: 150/);
});
