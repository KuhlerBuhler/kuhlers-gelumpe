import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
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

const root = fileURLToPath(new URL("../", import.meta.url));

/** Files that only hold texts: a change to them changes no patched copy and no check result, so it starts no run. */
const TEXT_ONLY = ["src/text.mjs", "site/app/i18n-de.mjs"];

/** The repo files `file` loads, itself included, following relative imports. */
function imports(file, seen = new Set()) {
  if (seen.has(file)) return seen;
  seen.add(file);
  for (const m of readFileSync(file, "utf8").matchAll(/(?:from|import\()\s*["'](\.[^"']+)["']/g)) {
    const next = resolve(dirname(file), m[1]);
    if (existsSync(next)) imports(next, seen);
  }
  return seen;
}

test("the Verify patches workflow runs on a pull request that changes anything verify-patches.mjs loads", () => {
  const workflow = readFileSync(`${root}.github/workflows/verify-patches.yml`, "utf8");
  const block = workflow.match(/^ {4}paths:\n((?: {6}- .*\n)+)/m)[1];
  const globs = [...block.matchAll(/- "([^"]+)"/g)].map(m => m[1]);
  const re = g => new RegExp(`^${g.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*\*/g, "\0").replace(/\*/g, "[^/]*").replace(/\0/g, ".*")}$`);
  const take = globs.filter(g => !g.startsWith("!")).map(re);
  const drop = globs.filter(g => g.startsWith("!")).map(g => re(g.slice(1)));
  const runs = f => take.some(r => r.test(f)) && !drop.some(r => r.test(f));
  const loaded = [...imports(`${root}tools/verify-patches.mjs`)].map(f => relative(root, f));
  assert.ok(loaded.includes("src/patch.mjs"));
  assert.deepEqual(loaded.filter(f => !runs(f) && !TEXT_ONLY.includes(f)), []);
  for (const f of ["data/patches/blech.json", "tools/emu/check.py", "tools/patch/pad_colors.py", "data/synth-map/dice.json", "tools/ci/verify-scope.mjs"]) assert.ok(runs(f), f);
  assert.ok(!runs("data/patches/verified.json"), "its own commit must not start it again");
});
