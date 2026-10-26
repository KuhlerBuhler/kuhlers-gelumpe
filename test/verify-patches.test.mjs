import { test } from "node:test";
import assert from "node:assert/strict";
import { joinResults, readResults, verifiedText } from "../tools/verify-patches.mjs";

const entry = (input, output, date = "2026-10-01") => ({ input, output, set: "blech", checks: 500, date });

test("without --merge the file holds only the files checked now", () => {
  const old = [entry("aa", "11"), entry("bb", "22")];
  assert.deepEqual(joinResults(old, [entry("cc", "33", "2026-10-26")]), [entry("cc", "33", "2026-10-26")]);
});

test("--merge keeps the other inputs and replaces the one checked now", () => {
  const old = [entry("cc", "33"), entry("aa", "11")];
  const fresh = [entry("aa", "12", "2026-10-26")];
  assert.deepEqual(joinResults(old, fresh, { merge: true }), [entry("aa", "12", "2026-10-26"), entry("cc", "33")]);
});

test("a pair that passed before keeps its date, so a run without changes leaves the file as it was", () => {
  const old = [entry("aa", "11"), entry("bb", "22")];
  const fresh = [entry("bb", "22", "2026-10-26"), entry("aa", "11", "2026-10-26")];
  assert.equal(verifiedText(joinResults(old, fresh)), verifiedText(old));
  assert.equal(joinResults(old, [{ ...entry("aa", "11", "2026-10-26"), checks: 501 }])[0].date, "2026-10-26");
});

test("the written file reads back, anything else is refused", () => {
  const results = [entry("aa", "11")];
  assert.deepEqual(readResults(verifiedText(results)), results);
  assert.throws(() => readResults(JSON.stringify({ format: "other", version: 1, results })), /not a gelumpe-verified file/);
});
