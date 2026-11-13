#!/usr/bin/env node
/**
 * Which pull requests "Update pull requests" merges main or a release branch into, and in which order. Merging the base
 * into a pull request starts its full CI, so the workflow takes one per run: it walks this list and stops at the first
 * that took the merge. The merge that lands then fires the workflow again and the next pull request follows, and the
 * pull request that lands was still tested against the base with every merge before it. Merging into every pull request
 * that is behind, after each merge, started all their checks at once (issue #459).
 *
 *   git ... | node tools/ci/pr-queue.mjs      prints number, head, sha and commits behind, tab separated, oldest first
 *
 * Input rows, tab separated: number, head, sha, commits behind, draft, fork. Not in the list: pull requests from a fork,
 * drafts, one whose head is itself a base branch, and one that is up to date with the base.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/** The heads that are a base branch themselves: the sync main -> develop pull request goes from one of them. */
const BASE_HEAD = /^(main|develop|release\/)/;

/** The fields of one input row. */
export function row(line) {
  const [number, head, sha, behind, draft, fork] = line.split("\t");
  return {
    number: Number(number),
    head,
    sha,
    behind: Number(behind),
    draft: draft === "true",
    fork: fork === "true",
  };
}

/** The input rows of the whole table. */
export function rows(text) {
  return text.split("\n").map(line => line.trimEnd()).filter(Boolean).map(row);
}

/** The pull requests to try, oldest first. Empty when every one of them is up to date. */
export function queue(list) {
  return list
    .filter(r => !r.fork && !r.draft && !BASE_HEAD.test(r.head) && r.behind > 0)
    .sort((a, b) => a.number - b.number);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  for (const r of queue(rows(readFileSync(0, "utf8")))) console.log([r.number, r.head, r.sha, r.behind].join("\t"));
}
