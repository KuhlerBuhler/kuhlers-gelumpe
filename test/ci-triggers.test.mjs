import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("workflow-only changes run the tests that validate firmware execution and merge rules", () => {
  const workflow = readFileSync(new URL("../.github/workflows/test.yml", import.meta.url), "utf8");
  const suites = workflow.match(/            suites:\n([\s\S]*?)            native:/)[1];
  const paths = [...suites.matchAll(/- '([^']+)'/g)].map(m => m[1]);
  for (const file of [".github/workflows/firmware-check.yml", ".github/workflows/verify-patches.yml",
    ".github/workflows/release.yml", ".github/workflows/automerge.yml", ".github/workflows/release-merge.yml"]) {
    assert.ok(paths.includes(file), `${file} must run its workflow regression tests`);
  }
  assert.ok(paths.includes(".github/actions/**"), "composite action changes must run the full tests");
});
