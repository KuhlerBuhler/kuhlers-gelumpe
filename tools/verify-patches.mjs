#!/usr/bin/env node
/**
 * Check the BLECH copies the patcher makes from known SYSTEM.VSB files once, here, and write their hashes to
 * data/patches/verified.json. The patcher skips the emulator check for exactly these copies (src/patcher.mjs,
 * verifiedReport): same input, same result, same boots. On a slow PC the check takes more than an hour.
 *
 *   npm run verify:patches -- ~/rot/SYSTEM.VSB ~/blau/SYSTEM.VSB ~/hacktribe/SYSTEM.VSB
 *
 * Every file is patched exactly as the page does it (the set for its build, applyPatches) and checked with
 * tools/emu/check.py. Only copies that pass go in, and the list is replaced, so a run after a patch change
 * drops the old results. Only hashes go into the repository, never firmware.
 */
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatches } from "../src/patch.mjs";
import { buildOf, sha256 } from "../src/firmware.mjs";
import { loadBlechSet, BLECH_SET_URL, BLECH_SYNTH_SET_URL, VERIFIED_URL } from "../src/patcher.mjs";
import { pythonEnv } from "./emu/python-env.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const files = process.argv.slice(2);
if (!files.length) {
  console.error("usage: verify-patches.mjs SYSTEM.VSB [SYSTEM.VSB ...]");
  process.exit(2);
}
const { python, command } = pythonEnv();
const readJson = url => JSON.parse(readFileSync(join(root, url), "utf8"));
const span = ([at, n]) => `0x${at.toString(16)}:${n}`;
const work = mkdtempSync(join(tmpdir(), "gelumpe-verify-"));
const results = [];
let failed = 0;

try {
  for (const file of files) {
    const input = readFileSync(resolve(file));
    const build = buildOf(input);
    const set = await loadBlechSet(readJson, build === "synth" ? BLECH_SYNTH_SET_URL : BLECH_SET_URL);
    const res = await applyPatches(input, set.patches);
    if (!res.ok) {
      console.error(`${file}: ${res.reasons.join(" ")}`);
      failed++;
      continue;
    }
    const base = join(work, "base.vsb");
    const patched = join(work, "patched.vsb");
    writeFileSync(base, input);
    writeFileSync(patched, res.bytes);
    const args = [join(root, "tools/emu/check.py"), "--base", base, "--patched", patched,
      ...res.allow.flatMap(s => ["--allow", span(s)]), ...res.allowCode.flatMap(s => ["--allow-code", span(s)])];
    console.log(`${file}: ${build}, checking ...`);
    const run = spawnSync(...command(python, args), { encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "inherit"] });
    let report = null;
    try { report = JSON.parse(run.stdout); } catch { /* reported below */ }
    if (!report?.ok) {
      const bad = report?.checks.filter(c => !c.ok).map(c => c.id) ?? [`check.py ended with ${run.status}`];
      console.error(`${file}: not passed: ${bad.join(", ")}`);
      failed++;
      continue;
    }
    const entry = { input: await sha256(input), output: await sha256(res.bytes), set: set.id, checks: report.checks.length, date: new Date().toISOString().slice(0, 10) };
    console.log(`${file}: ${entry.checks} checks passed, ${entry.input.slice(0, 8)} -> ${entry.output.slice(0, 8)}`);
    results.push(entry);
  }
} finally {
  rmSync(work, { recursive: true, force: true });
}

if (failed) {
  console.error(`${failed} file(s) did not pass, ${VERIFIED_URL} left as it was.`);
  process.exit(1);
}
writeFileSync(join(root, VERIFIED_URL), `${JSON.stringify({ format: "gelumpe-verified", version: 1, results }, null, 1)}\n`);
console.log(`${VERIFIED_URL}: ${results.length} copies`);
