import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import { firmwareMatrix } from "../tools/ci/firmware-matrix.mjs";
import { workflowPaths } from "../tools/ci/verify-scope.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const read = path => readFileSync(`${root}${path}`, "utf8");

test("only feature PRs into develop or release branches select cached case checks", () => {
  const workflow = read(".github/workflows/verify-patches.yml");
  const [, condition, body] = workflow.match(/- id: scope\n\s+if: ([^\n]+)\n([\s\S]*?)(?=\n      -)/);
  for (const [event_name, base_ref, expected] of [
    ["pull_request", "develop", true],
    ["pull_request", "release/1.4.5", true],
    ["pull_request", "release/2.0.0", true],
    ["pull_request", "main", false],
    ["pull_request", "release-candidate", false],
    ["pull_request", "feature/release/1.4.5", false],
    ["pull_request", "other", false],
    ["push", "release/1.4.5", false],
    ["workflow_dispatch", "release/1.4.5", false],
  ]) {
    assert.equal(runInNewContext(condition, {
      github: { event_name, base_ref },
      startsWith: (value, prefix) => value.toLowerCase().startsWith(prefix.toLowerCase()),
    }), expected, `${event_name} into ${base_ref}`);
  }
  assert.match(body, /node tools\/ci\/verify-scope\.mjs/);
  assert.match(body, /echo "full=false"/);
  assert.match(body, /echo "cases=\$cases"/);
  assert.match(workflow, /full: \$\{\{ steps\.scope\.outputs\.full \|\| steps\.push\.outputs\.full \|\| 'true' \}\}/);
  assert.match(workflow, /full: \$\{\{ needs\.ref\.outputs\.full == 'true' \}\}/);
  assert.match(read(".github/workflows/release.yml"), /full: true/);
  assert.match(read(".github/workflows/firmware-check.yml"), /name: Develop task results\n\s+if: \$\{\{ !inputs\.full \}\}\n\s+uses: actions\/cache\/restore@v4/);
});

test("the firmware matrix retains four hardware variants for each shard", () => {
  const { firmwares, parts } = firmwareMatrix(4);
  assert.deepEqual(parts, [1, 2, 3, 4]);
  assert.deepEqual(firmwares.map(f => f.name), ["hacktribe", "red", "blue", "hacktribe-blue"]);
  for (const f of firmwares) {
    assert.match(f.sha256, /^[a-f0-9]{64}$/);
    assert.match(f.secret, /^E2_VSB_(?:URL|STOCK_URL|SYNTH_URL)$/);
  }
  assert.equal(firmwares[3].secret, firmwares[0].secret);
  assert.match(firmwares[3].blue_head, /^[a-f0-9]{64}$/);
  assert.deepEqual(firmwareMatrix(2).parts, [1, 2]);
  for (const n of [0, -1, 1.5, 65, "4", undefined]) assert.throws(() => firmwareMatrix(n));
});

test("a rerun with fewer parts selects only its own count and hardware artifacts", () => {
  const four = firmwareMatrix(4), two = firmwareMatrix(2);
  const artifactNames = matrix => matrix.firmwares.flatMap(f => matrix.parts.map(i => `${f.artifact}-${i}`));
  const stored = [...artifactNames(four), ...artifactNames(two)];
  for (const f of two.firmwares) {
    const selected = stored.filter(name => name.startsWith(`${f.artifact}-`));
    assert.deepEqual(selected, [1, 2].map(i => `${f.artifact}-${i}`));
    assert.match(f.artifact, new RegExp(`^firmware-shard-${f.name}--2$`));
  }
});

test("start and editor checks occupy independent jobs with the original hardware and case coverage", () => {
  const kinds = options => firmwareMatrix(4, options).smokes.map(f => [f.name, f.kind]);
  const starts = [["hacktribe", "start"], ["red", "start"], ["blue", "start"]];
  const full = [...starts, ["hacktribe", "editor"], ["red", "editor"], ["blue", "editor"]];
  assert.deepEqual(kinds(), full);
  assert.deepEqual(kinds({ full: false, cases: "" }), starts);
  assert.deepEqual(kinds({ full: false, cases: "remote_cases,menu_cases" }), starts);
  assert.deepEqual(kinds({ full: false, cases: "remote_cases,fx_card_cases" }), full);
  assert.deepEqual(kinds({ full: false, cases: "all" }), full);
  assert.deepEqual(kinds({ full: true, cases: "" }), full);
  assert.deepEqual(kinds({ full: false, cases: "not_fx_card_cases" }), starts);
});

test("shared verification sources are part of the firmware scope", () => {
  const runs = workflowPaths();
  for (const path of [".github/workflows/firmware-check.yml", ".github/actions/firmware-input/action.yml", "tools/ci/firmware-matrix.mjs"]) assert.ok(runs(path), path);
});

test("every firmware job uses the same pinned hosted runner", () => {
  const jobs = read(".github/workflows/firmware-check.yml").split("\njobs:\n")[1];
  const jobNames = [...jobs.matchAll(/^  ([a-z-]+):$/gm)].map(m => m[1]);
  const runners = [...jobs.matchAll(/^    runs-on: (.+)$/gm)].map(m => m[1]);
  assert.ok(jobNames.length > 0);
  assert.equal(runners.length, jobNames.length);
  assert.deepEqual([...new Set(runners)], ["ubuntu-24.04"]);
});

test("the shared environment pins Python and reports its complete build identity", () => {
  const setup = read(".github/actions/firmware-input/action.yml");
  assert.match(setup, /python-version: "3\.12\.16"/);
  assert.match(setup, /tools\/emu\/\.venv\/bin\/python -c "import sys; print\(sys\.version\)"/);
});

test("PR and publication use one shared firmware execution with mandatory joins and smoke tests", () => {
  const shared = read(".github/workflows/firmware-check.yml");
  for (const caller of ["verify-patches.yml", "release.yml"]) assert.match(read(`.github/workflows/${caller}`), /uses: \.\/\.github\/workflows\/firmware-check\.yml/);
  assert.match(shared, /--shard/);
  assert.match(shared, /--join-shards/);
  assert.match(shared, /test\/emulator-fxcard\.test\.mjs/);
  assert.match(shared, /test\/emulator-start-phase\.test\.mjs/);
  assert.match(shared, /needs: \[plan, shard\]/);
  assert.match(shared, /needs: \[join, smoke\]/);
  assert.match(shared, /GELUMPE_JOBS: "4"/);
  assert.match(shared, /if: matrix\.firmware\.kind == 'editor'/);
  assert.match(shared, /if: matrix\.firmware\.kind == 'start'/);
  assert.match(shared, /name: \$\{\{ matrix\.firmware\.artifact \}\}-\$\{\{ matrix\.part \}\}/);
  assert.match(shared, /pattern: \$\{\{ matrix\.firmware\.artifact \}\}-\*/);
  assert.match(shared, /group: .*matrix\.firmware\.kind/);
  assert.equal([...shared.matchAll(/GELUMPE_NODE_RESULTS: \$\{\{ !inputs\.full && 'strict' \|\| '' \}\}/g)].length, 2);
  assert.doesNotMatch(shared, /path:.*(?:SYSTEM\.VSB|\/boot|\/power-on)/);
});
