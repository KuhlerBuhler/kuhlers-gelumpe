import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const workflow = read(".github/workflows/fork-check.yml");
const job = name => workflow.match(new RegExp(`\\n  ${name}:\\n([\\s\\S]*?)(?=\\n  [a-z-]+:\\n|$)`))[1];
const condition = name => `\n${job(name)}`.match(/\n    if: >-\n((?:      .*\n)+)|\n    if: (.*)\n/).slice(1).find(Boolean).replace(/\s+/g, " ").trim();
const event = (action, label, fork = true, labels = []) => ({
  github: {
    repository: "KuhlerBuhler/kuhlers-gelumpe",
    event: {
      action, label: { name: label },
      pull_request: { head: { repo: { full_name: fork ? "someone/kuhlers-gelumpe" : "KuhlerBuhler/kuhlers-gelumpe" } }, labels: labels.map(name => ({ name })) },
    },
  },
});
// GitHub's contains() on an array of label names, enough for these conditions
const evaluate = (expr, ctx) => runInNewContext(
  expr.replace(/contains\(github\.event\.pull_request\.labels\.\*\.name, '([^']+)'\)/g, "github.event.pull_request.labels.some(l => l.name === '$1')")
    .replace(/'/g, '"').replace(/ != /g, " !== ").replace(/ == /g, " === "),
  ctx);

test("only the label safe-to-test on a fork's pull request starts the check", () => {
  assert.match(workflow, /pull_request_target:\n\s+types: \[labeled, synchronize, reopened\]/);
  const start = condition("start");
  assert.equal(evaluate(start, event("labeled", "safe-to-test")), true);
  assert.equal(evaluate(start, event("labeled", "automerge")), false);
  assert.equal(evaluate(start, event("labeled", "safe-to-test", false)), false);
  assert.equal(evaluate(start, event("synchronize", undefined)), false);
});

test("a new push or a reopen removes the label", () => {
  const unlabel = condition("unlabel");
  assert.equal(evaluate(unlabel, event("synchronize", undefined, true, ["safe-to-test"])), true);
  assert.equal(evaluate(unlabel, event("reopened", undefined, true, ["safe-to-test"])), true);
  assert.equal(evaluate(unlabel, event("synchronize", undefined, true, [])), false);
  assert.equal(evaluate(unlabel, event("labeled", "safe-to-test", true, ["safe-to-test"])), false);
  assert.match(job("unlabel"), /issues\/\$PR\/labels\/safe-to-test/);
});

test("the trusted jobs never run the fork's code", () => {
  for (const name of ["unlabel", "start", "report"]) {
    const body = job(name);
    assert.doesNotMatch(body, /ref: \$\{\{ (?:github\.event\.pull_request\.head|needs\.start\.outputs\.sha)|pull\/\$PR\/head/, name);
    assert.doesNotMatch(body, /npm (?:ci|install|run)|python|\.venv/, name);
  }
  // the one checkout of the start job is the base branch, without a stored token
  assert.match(job("start"), /- uses: actions\/checkout@v7\n\s+with:\n\s+persist-credentials: false\n/);
});

test("the check gets the labelled head commit, the firmware downloads and no other secret, and writes no cache", () => {
  const verify = job("verify");
  assert.match(verify, /uses: \.\/\.github\/workflows\/firmware-check\.yml/);
  assert.match(verify, /ref: \$\{\{ needs\.start\.outputs\.sha \}\}/);
  assert.match(job("start"), /SHA: \$\{\{ github\.event\.pull_request\.head\.sha \}\}/);
  assert.match(job("start"), /\[ "\$head" != "\$SHA" \]/);
  assert.match(verify, /save-cache: false/);
  assert.doesNotMatch(workflow, /secrets: inherit/);
  assert.deepEqual([...verify.matchAll(/\$\{\{ secrets\.([A-Z0-9_]+) \}\}/g)].map(m => m[1]).sort(), ["E2_VSB_STOCK_URL", "E2_VSB_SYNTH_URL", "E2_VSB_URL"]);
  assert.doesNotMatch(workflow.replace(verify, ""), /secrets\./);
});

test("a change to .github/ or a label by someone without write access does not run", () => {
  const start = job("start");
  assert.match(start, /grep -q '\^\\\.github\/'/);
  assert.match(start, /collaborators\/\$SENDER\/permission/);
  assert.match(start, /admin\|maintain\|write\) ;;/);
});

test("the shared firmware check writes no cache for unmerged code", () => {
  const shared = read(".github/workflows/firmware-check.yml");
  assert.match(shared, /save-cache:\n\s+type: boolean\n\s+default: true/);
  assert.equal([...shared.matchAll(/save-cache: \$\{\{ inputs\.save-cache \}\}/g)].length, 4, "every firmware input");
  assert.match(shared, /if: \$\{\{ always\(\) && !inputs\.full && inputs\.save-cache \}\}\n\s+uses: actions\/cache\/save@v6/);
  assert.equal([...shared.matchAll(/save: \$\{\{ inputs\.save-cache \}\}/g)].length, 3, "every Blackfin worker");
  assert.match(read(".github/actions/dsp-worker/action.yml"), /inputs\.build == 'true' && inputs\.save == 'true'/);
  assert.match(read(".github/actions/firmware-input/action.yml"), /cache: \$\{\{ inputs\.save-cache == 'true' && 'npm' \|\| '' \}\}/);
});
