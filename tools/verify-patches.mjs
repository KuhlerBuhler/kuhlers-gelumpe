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
 *   --cases LIST        check only, write nothing: the start scenarios and the cases of the named modules (check.py
 *                       --cases, comma-separated, empty = --quick, "all" = every case); the workflow's runs on pull
 *                       requests into develop. Entries in verified.json always mean the full check.
 *   --shard I/N --output FILE   run one task partition and write its result, without updating verified.json
 *   --join-shards DIR          validate and combine every partition against this input; --cases still writes nothing
 *
 * A pair that is already in the file with the same set and checks keeps its old date, so a run that changes nothing
 * leaves the file byte for byte as it was.
 */
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatches } from "../src/patch.mjs";
import { buildOf, hardwareOf, sha256 } from "../src/firmware.mjs";
import { loadBlechSet, samplerHead, withHead, BLECH_SET_URL, BLECH_SYNTH_SET_URL, VERIFIED_URL } from "../src/patcher.mjs";
import { pythonEnv } from "./emu/python-env.mjs";
import { loadGate } from "./load-gate.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
await loadGate();
const FORMAT = "gelumpe-verified";
const SHARD_FORMAT = "gelumpe-verification-shard";

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

export function parseOptions(argv) {
  const out = { files: [], cases: null, merge: false, fromResults: false, shard: null, output: null, joinShards: null };
  const options = { "--cases": "cases", "--shard": "shard", "--output": "output", "--join-shards": "joinShards" };
  const seen = new Set();
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith("--")) { out.files.push(arg); continue; }
    if (seen.has(arg)) throw new Error(`repeated option: ${arg}`);
    seen.add(arg);
    if (arg === "--merge") out.merge = true;
    else if (arg === "--results") out.fromResults = true;
    else if (options[arg]) {
      if (argv[i + 1] === undefined || argv[i + 1].startsWith("--")) throw new Error(`${arg} needs a value`);
      out[options[arg]] = argv[++i];
    } else throw new Error(`unknown option: ${arg}`);
  }
  if (!out.files.length) throw new Error("an input file is required");
  if (out.fromResults && (out.cases !== null || out.shard !== null || out.output !== null || out.joinShards !== null)) {
    throw new Error("--results takes complete verified.json files only");
  }
  if (out.shard !== null) {
    const match = /^(\d+)\/(\d+)$/.exec(out.shard);
    if (!match || +match[1] < 1 || +match[1] > +match[2] || +match[2] > 64) throw new Error("--shard needs I/N with 1 <= I <= N <= 64");
    if (!out.output || out.files.length !== 1 || out.joinShards !== null || out.merge) throw new Error("--shard needs one input and --output, without --join-shards or --merge");
  } else if (out.output !== null) throw new Error("--output requires --shard");
  if (out.joinShards !== null && (!out.joinShards || out.files.length !== 1)) throw new Error("--join-shards needs a directory and one input");
  return out;
}

function validateShard(report) {
  if (report?.format !== "gelumpe-check-shard" || report.version !== 1 || report.passed !== true
    || !/^[a-f0-9]{64}$/.test(report.identity) || !Array.isArray(report.tasks)
    || !Number.isSafeInteger(report.shard?.index) || !Number.isSafeInteger(report.shard?.count)
    || report.shard.index < 1 || report.shard.index > report.shard.count || report.shard.count > 64) {
    throw new Error("not a successful gelumpe-check-shard result");
  }
  return report;
}

export function shardText(report, metadata) {
  return `${JSON.stringify({ format: SHARD_FORMAT, version: 1, ...metadata, report: validateShard(report) })}\n`;
}

export function shardReport(text, expected) {
  const data = JSON.parse(text);
  if (data?.format !== SHARD_FORMAT || data.version !== 1) throw new Error("not a verification shard file");
  for (const key of ["input", "output", "set", "hardware", "source"]) {
    if ((data[key] ?? null) !== (expected[key] ?? null)) throw new Error(`shard ${key} does not match this check`);
  }
  return validateShard(data.report);
}

function shardFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? shardFiles(join(dir, e.name))
    : e.isFile() && e.name.endsWith(".json") ? [join(dir, e.name)] : []).sort();
}

async function check(files, cases = null, options = {}) {
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
      const metadata = { input: await sha256(input), output: await sha256(res.bytes), set: set.id,
        ...(blue ? { hardware: "blue" } : {}) };
      if (options.shard || options.joinShards) metadata.source = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
      let mode = options.shard ? ["--shard", options.shard] : [];
      if (options.joinShards) {
        const parts = shardFiles(resolve(options.joinShards));
        if (!parts.length) throw new Error("no shard results to join");
        mode = ["--join", ...parts.map((file, index) => {
          const path = join(work, `shard-${index}.json`);
          writeFileSync(path, JSON.stringify(shardReport(readFileSync(file, "utf8"), metadata)));
          return path;
        })];
      }
      const args = [join(root, "tools/emu/check.py"), "--base", base, "--patched", patched, ...hardware,
        ...res.allow.flatMap(s => ["--allow", span(s)]), ...res.allowCode.flatMap(s => ["--allow-code", span(s)]),
        ...(cases === null || cases === "all" ? [] : ["--cases", cases]), ...mode];
      console.log(`${file}: ${build}${blue ? " for the blue" : ""}, checking${cases === null ? "" : ` (cases: ${cases || "none"})`} ...`);
      const run = spawnSync(...command(python, args), { encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "inherit"] });
      let report = null;
      try { report = JSON.parse(run.stdout); } catch { /* reported below */ }
      if (options.shard && run.status === 0) {
        writeFileSync(resolve(options.output), shardText(report, metadata));
        console.log(`${options.output}: shard ${options.shard}, no complete verification written`);
        continue;
      }
      if (run.status !== 0 || !report?.ok || !Array.isArray(report.checks)) {
        const bad = report?.checks?.filter(c => !c.ok).map(c => `${c.id} (${JSON.stringify(c.detail)})`) ?? [`check.py ended with ${run.status}`];
        console.error(`${file}: not passed: ${bad.join(", ")}`);
        failed++;
        continue;
      }
      const { source: _, ...pair } = metadata;
      const entry = { ...pair, checks: report.checks.length, date: new Date().toISOString().slice(0, 10) };
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
  const options = parseOptions(argv);
  const { files, cases, merge, fromResults } = options;
  if (cases !== null || options.shard) {
    const { failed } = await check(files, cases, options);
    if (failed) {
      console.error(`${failed} file(s) did not pass.`);
      process.exit(1);
    }
    console.log(`all passed; a partial check writes nothing to ${VERIFIED_URL}`);
    return;
  }
  const { results, failed } = fromResults
    ? { results: files.flatMap(f => readResults(readFileSync(resolve(f), "utf8"), f)), failed: 0 }
    : await check(files, null, options);
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
