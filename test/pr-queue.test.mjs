import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { queue, rows } from "../tools/ci/pr-queue.mjs";

const row = (number, { head = `fix/pr-${number}`, behind = 1, draft = false, fork = false } = {}) =>
  [number, head, `sha${number}`, behind, draft, fork].join("\t");

test("a pull request is read from its row", () => {
  assert.deepEqual(rows(row(12, { behind: 3, draft: true })), [
    { number: 12, head: "fix/pr-12", sha: "sha12", behind: 3, draft: true, fork: false },
  ]);
});

test("the queue holds the pull requests that are behind, oldest first", () => {
  const list = rows([row(9, { behind: 2 }), row(4, { behind: 0 }), row(7, { behind: 1 })].join("\n"));
  assert.deepEqual(queue(list).map(r => r.number), [7, 9]);
  assert.deepEqual(queue(list).map(r => r.behind), [1, 2]);
});

test("drafts, forks, a head that is a base branch and up to date pull requests are not in it", () => {
  const list = rows([
    row(3, { draft: true }),
    row(5, { fork: true }),
    row(6, { head: "release/1.4.5" }),
    row(8, { head: "develop" }),
    row(2, { behind: 0 }),
    row(11),
  ].join("\n"));
  assert.deepEqual(queue(list).map(r => r.number), [11]);
  assert.deepEqual(queue(rows("")), []);
});

test("the workflow takes the list from this module and stops after one merge", () => {
  const yml = readFileSync(new URL("../.github/workflows/update-prs.yml", import.meta.url), "utf8");
  assert.match(yml, /node tools\/ci\/pr-queue\.mjs/);
  assert.match(yml, /\[ "\$ALL" = true \] \|\| break/);
});
