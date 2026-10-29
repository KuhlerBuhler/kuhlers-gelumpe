import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { REQUIRED, SELF, approval, checkProblems, isRelease, mergeProblems } from "../tools/release-merge.mjs";

const HEAD = "b7dbfee";
const run = (id, name, status = "completed", conclusion = "success", extra = {}) =>
  ({ id, name, event: "pull_request", workflow_id: name, check_suite_id: id * 10, status, conclusion, ...extra });
const check = (id, name, status = "completed", conclusion = "success", suite = 1) =>
  ({ id, name, status, conclusion, check_suite: { id: suite } });
const green = () => ({
  runs: [run(1, "Test"), run(2, "Verify patches"), run(3, "Korg data guard", "completed", "success", { event: "pull_request_target" })],
  checks: [check(1, "unit"), check(2, "browser"), check(3, "guard"), check(4, "verify (red)"), check(5, "unit-docs", "completed", "skipped")],
});
const review = (id, login, state, commit_id = HEAD) => ({ id, user: { login }, state, commit_id });
const ready = (over = {}) => ({
  ...green(),
  reviews: [review(1, "KuhlerBuhler", "APPROVED")],
  permission: login => ({ KuhlerBuhler: "admin", pascalfritzsche: "write" })[login] ?? "read",
  current: commit => commit === HEAD,
  ...over,
});
const pr = { number: 258, baseRefName: "main", headRefName: "release/1.3.7", headRefOid: HEAD, isDraft: false, isCrossRepository: false };

test("only release/X.Y.Z -> main from this repository counts as a release pull request", () => {
  assert.ok(isRelease(pr));
  assert.ok(!isRelease({ ...pr, baseRefName: "develop" }));
  assert.ok(!isRelease({ ...pr, headRefName: "develop" }));
  assert.ok(!isRelease({ ...pr, headRefName: "release/next" }));
  assert.ok(!isRelease({ ...pr, isCrossRepository: true }));
});

test("approved and green: merged", () => {
  assert.deepEqual(mergeProblems(pr, ready()), []);
});

test("a check still running, e.g. Verify patches that may push a new verified.json: no merge", () => {
  const { runs, checks } = green();
  runs[1] = run(2, "Verify patches", "in_progress", null);
  checks[3] = check(4, "verify (red)", "in_progress", null);
  const problems = mergeProblems(pr, ready({ runs, checks }));
  assert.ok(problems.some(p => p.includes("Verify patches")));
  assert.ok(problems.some(p => p.includes("verify (red)")));
});

test("a workflow queued on the head before any of its checks exist: no merge", () => {
  const { runs, checks } = green();
  assert.deepEqual(checkProblems([...runs, run(9, "Build apps", "queued", null)], checks), ['workflow "Build apps" (pull_request) is queued']);
});

test("a failed or cancelled check: no merge; a passing re-run of it counts", () => {
  const { runs, checks } = green();
  assert.ok(checkProblems(runs, [...checks, check(6, "docker", "completed", "failure")]).length);
  assert.ok(checkProblems([...runs, run(7, "Build apps", "completed", "cancelled")], checks).length);
  assert.deepEqual(checkProblems(runs, [...checks, check(6, "docker", "completed", "failure"), check(8, "docker")]), []);
});

test("a required check that never ran or was skipped: no merge", () => {
  const { runs, checks } = green();
  assert.ok(checkProblems(runs, checks.filter(c => c.name !== "guard")).some(p => p.includes('"guard" has not run')));
  assert.ok(checkProblems(runs, checks.map(c => c.name === "unit" ? { ...c, conclusion: "skipped" } : c)).length);
  assert.deepEqual(REQUIRED, ["unit", "browser", "guard"]);
});

test("its own run on the head, still going, does not hold it up", () => {
  const { runs, checks } = green();
  assert.deepEqual(checkProblems([...runs, run(5, SELF, "in_progress", null)], [...checks, check(9, "merge", "in_progress", null, 50)]), []);
});

test("no approval, an approval by someone without write access, or a draft: no merge", () => {
  assert.ok(mergeProblems(pr, ready({ reviews: [] })).length);
  assert.ok(mergeProblems(pr, ready({ reviews: [review(1, "someone", "APPROVED")] })).length);
  assert.deepEqual(mergeProblems({ ...pr, isDraft: true }, ready()), ["it is a draft"]);
});

test("the approval holds over the verified.json commit, not over any other change", () => {
  const reviews = [review(1, "KuhlerBuhler", "APPROVED", "old")];
  assert.deepEqual(mergeProblems(pr, ready({ reviews, current: c => c === HEAD || c === "old" })), []);
  assert.ok(mergeProblems(pr, ready({ reviews })).length);
});

test("the last review of each person counts; changes requested by a writer block", () => {
  const p = ready().permission;
  const cur = c => c === HEAD;
  assert.deepEqual(approval([review(1, "KuhlerBuhler", "CHANGES_REQUESTED"), review(2, "KuhlerBuhler", "APPROVED")], p, cur), { approvers: ["KuhlerBuhler"], against: [] });
  assert.deepEqual(approval([review(1, "KuhlerBuhler", "APPROVED"), review(2, "KuhlerBuhler", "COMMENTED")], p, cur).approvers, ["KuhlerBuhler"]);
  assert.ok(mergeProblems(pr, ready({ reviews: [review(1, "KuhlerBuhler", "APPROVED"), review(2, "pascalfritzsche", "CHANGES_REQUESTED")] })).some(p => p.includes("pascalfritzsche")));
});

test("the workflow starts on every workflow that runs on a pull request and calls the script with SYNC_TOKEN", () => {
  const dir = new URL("../.github/workflows/", import.meta.url);
  const yml = readFileSync(new URL("release-merge.yml", dir), "utf8");
  assert.match(yml, new RegExp(`^name: ${SELF}$`, "m"));
  const listed = yml.match(/workflows: \[(.*)\]/)[1].split(",").map(s => s.trim());
  const onPr = readdirSync(dir).map(f => readFileSync(new URL(f, dir), "utf8"))
    .filter(t => /^ {2}(pull_request|pull_request_target):/m.test(t) || /branches: \[.*"release\/\*\*"/.test(t))
    .map(t => t.match(/^name: (.*)$/m)[1]).filter(n => n !== SELF);
  assert.deepEqual(onPr.filter(n => !listed.includes(n)), []);
  for (const n of listed) assert.ok(readdirSync(dir).some(f => readFileSync(new URL(f, dir), "utf8").includes(`name: ${n}\n`)), n);
  assert.match(yml, /GH_TOKEN: \$\{\{ secrets\.SYNC_TOKEN \}\}/);
  assert.match(yml, /node tools\/release-merge\.mjs/);
});
