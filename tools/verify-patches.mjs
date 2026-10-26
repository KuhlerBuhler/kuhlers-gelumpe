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
 *
 *   --merge             keep the entries of other inputs in the file, replace only those of the files checked now
 *   --results FILE...   take the entries from verified.json files of earlier runs instead of checking (the workflow
 *                       .github/workflows/verify-patches.yml joins its three jobs this way)
 *
 * A pair that is already in the file with the same set and checks keeps its old date, so a run that changes nothing
 * leaves the file byte for byte as it was.
 */
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatches } from "../src/patch.mjs";
import { buildOf, hardwareOf, sha256 } from "../src/firmware.mjs";
import { loadBlechSet, samplerHead, withHead, BLECH_SET_URL, BLECH_SYNTH_SET_URL, VERIFIED_URL } from "../src/patcher.mjs";
import { pythonEnv } from "./emu/python-env.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const FORMAT = "gelumpe-verified";

const sameCheck = (a, b) => a.input === b.input && a.output === b.output && a.set === b.set && a.checks === b.checks
  && (a.hardware ?? null) === (b.hardware ?? null);
// The same input can stand twice: once checked on the red's flash, once on the blue's (hardware: "blue")
const slot = r => `${r.input}/${r.hardware ?? ""}`;

/**
 * The results to write: `fresh` and, with `merge`, the entries of `old` for other inputs. One entry per input and hardware,
 * sorted by input; a fresh entry that repeats an old one keeps the old date.
 */
export function joinResults(old, fresh, { merge = false } = {}) {
  const byInput = new Map(merge ? old.map(r => [slot(r), r]) : []);
  for (const r of fresh) {
    const was = old.find(o => sameCheck(o, r));
    byInput.set(slot(r), was ? { ...r, date: was.date } : r);
  }
  return [...byInput.values()].sort((a, b) => slot(a).localeCompare(slot(b)));
}

export const verifiedText = results => `${JSON.stringify({ format: FORMAT, version: 1, results }, null, 1)}\n`;

/** The results of a verified.json; throws when it is not one. */
export function readResults(text, name = "verified.json") {
  const data = JSON.parse(text);
  if (data?.format !== FORMAT || data.version !== 1 || !Array.isArray(data.results)) throw new Error(`${name}: not a ${FORMAT} file`);
  return data.results;
}

async function check(files) {
  const { python, command } = pythonEnv();
  const readJson = url => JSON.parse(readFileSync(join(root, url), "utf8"));
  const span = ([at, n]) => `0x${at.toString(16)}:${n}`;
  const work = mkdtempSync(join(tmpdir(), "gelumpe-verify-"));
  const results = [];
  let failed = 0;
  try {
    for (const file of files) {
      const dropped = readFileSync(resolve(file));
      const build = buildOf(dropped);
      // Hacktribe for the blue: the page patches it with the Sampler head and checks it on the blue's flash
      const blue = build === "hacktribe" && hardwareOf(dropped) === "blue";
      const input = blue ? samplerHead(dropped) : dropped;
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
      const hardware = blue ? ["--hardware", "blue"] : [];
      const args = [join(root, "tools/emu/check.py"), "--base", base, "--patched", patched, ...hardware,
        ...res.allow.flatMap(s => ["--allow", span(s)]), ...res.allowCode.flatMap(s => ["--allow-code", span(s)])];
      console.log(`${file}: ${build}${blue ? " for the blue" : ""}, checking ...`);
      const run = spawnSync(...command(python, args), { encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "inherit"] });
      let report = null;
      try { report = JSON.parse(run.stdout); } catch { /* reported below */ }
      if (!report?.ok) {
        const bad = report?.checks.filter(c => !c.ok).map(c => `${c.id} (${JSON.stringify(c.detail)})`) ?? [`check.py ended with ${run.status}`];
        console.error(`${file}: not passed: ${bad.join(", ")}`);
        failed++;
        continue;
      }
      const entry = { input: await sha256(input), output: await sha256(res.bytes), set: set.id, ...(blue ? { hardware: "blue" } : {}), checks: report.checks.length, date: new Date().toISOString().slice(0, 10) };
      console.log(`${file}: ${entry.checks} checks passed, ${entry.input.slice(0, 8)} -> ${entry.output.slice(0, 8)}`);
      results.push(entry);
      // Korg's red file with hacktribe-2.patch for the blue is the same copy with the blue head; the emulator runs only what
      // follows the head, and the header check compares the heads of input and result, so this check stands for it too
      if (blue) results.push({ ...entry, input: await sha256(dropped), output: await sha256(withHead(res.bytes, "blue")) });
    }
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
  return { results, failed };
}

async function main(argv) {
  const merge = argv.includes("--merge");
  const fromResults = argv.includes("--results");
  const files = argv.filter(a => a !== "--merge" && a !== "--results");
  if (!files.length) {
    console.error("usage: verify-patches.mjs [--merge] SYSTEM.VSB [SYSTEM.VSB ...]\n       verify-patches.mjs [--merge] --results verified.json [verified.json ...]");
    process.exit(2);
  }
  const { results, failed } = fromResults
    ? { results: files.flatMap(f => readResults(readFileSync(resolve(f), "utf8"), f)), failed: 0 }
    : await check(files);
  if (failed) {
    console.error(`${failed} file(s) did not pass, ${VERIFIED_URL} left as it was.`);
    process.exit(1);
  }
  const path = join(root, VERIFIED_URL);
  const old = existsSync(path) ? readResults(readFileSync(path, "utf8"), VERIFIED_URL) : [];
  const joined = joinResults(old, results, { merge });
  writeFileSync(path, verifiedText(joined));
  console.log(`${VERIFIED_URL}: ${joined.length} copies`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await main(process.argv.slice(2));
