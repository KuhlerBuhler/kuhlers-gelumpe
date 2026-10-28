#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync, readdirSync, realpathSync } from "node:fs";
import { resolve, dirname, relative, isAbsolute, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { sha256, buildOf } from "../../src/firmware.mjs";
import { applyPatches, selectFor } from "../../src/patch.mjs";
import { loadBlechSet, BLECH_SET_URL, BLECH_SYNTH_SET_URL } from "../../src/patcher.mjs";
import { FREE_RUNS, SYNTH_FREE_RUNS } from "../../data/patch-ram.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const BUILDS = ["hacktribe", "stock", "synth"];
const CORE = ["header", "dsp_stream", "boot:normal", "kill_switch", "dsp_boot_once", "start_phase"];

export function validateInputs(spec) {
  if (!spec || Object.keys(spec).sort().join() !== [...BUILDS].sort().join()) throw new Error("inputs must name exactly three builds");
  for (const build of BUILDS) {
    const entry = spec[build];
    if (!entry || typeof entry.path !== "string" || !entry.path.trim() || !/^[0-9a-f]{64}$/.test(entry.sha256)) {
      throw new Error(`${build}: path and SHA-256 required`);
    }
  }
}

export function checkArguments(base, patched, result) {
  if (resolve(base) === resolve(patched)) throw new Error("original and output must differ");
  const args = ["--base", base, "--patched", patched];
  for (const [key, flag] of [["allow", "--allow"], ["allowCode", "--allow-code"]]) {
    for (const pair of result[key]) {
      if (!Array.isArray(pair) || pair.length !== 2 || !Number.isSafeInteger(pair[0]) || pair[0] < 0 || !Number.isSafeInteger(pair[1]) || pair[1] <= 0) {
        throw new Error("invalid manifest exception");
      }
      args.push(flag, `0x${pair[0].toString(16)}:${pair[1]}`);
    }
  }
  return args;
}

export function validateReport(report, status, progress, requiredGroups) {
  if (status !== 0 || report?.ok !== true || !Array.isArray(report.checks) || !report.checks.length) throw new Error(`check.py failed or report missing${report?.checks ? ": " + report.checks.filter(c => !c.ok).map(c => c.id).join(", ") : ""}`);
  const ids = new Set();
  for (const check of report.checks) {
    if (typeof check.id !== "string" || check.ok !== true || check.skip || check.skipped || check.id === "quick" || ids.has(check.id)) {
      throw new Error(`invalid, failed, skipped or duplicate check: ${check.id}`);
    }
    ids.add(check.id);
  }
  if (CORE.some(id => !ids.has(id))) throw new Error("incomplete core checks");
  if (!progress || !Number.isInteger(progress.total) || progress.total < 1 || progress.done !== progress.total || progress.fail !== 0 || !Array.isArray(progress.groups) || !progress.groups.length) {
    throw new Error("incomplete task progress");
  }
  const groups = new Set();
  let total = 0;
  for (const group of progress.groups) {
    if (!Number.isInteger(group.total) || group.total < 1 || group.done !== group.total || group.fail !== 0 || group.state !== "done" || groups.has(group.id)) throw new Error("incomplete task group");
    groups.add(group.id);
    total += group.total;
  }
  if (total !== progress.total || requiredGroups.some(id => !groups.has(id))) throw new Error("required task groups missing");
}

function union(spans) {
  const out = [];
  for (const [a, b] of spans.filter(([a, b]) => b > a).sort((x, y) => x[0] - y[0])) {
    const last = out.at(-1);
    if (last && a <= last[1]) last[1] = Math.max(b, last[1]); else out.push([a, b]);
  }
  return out;
}
const size = spans => union(spans).reduce((n, [a, b]) => n + b - a, 0);
const clip = (spans, limits) => union(spans.flatMap(([a, b]) => limits.map(([c, d]) => [Math.max(a, c), Math.min(b, d)])));

export function footprint(original, spans, patches, runs) {
  const free = runs.map(r => [r.start, r.end]);
  for (const [a, b] of free) {
    const at = a - 0xbfffff00;
    if (at < 256 || at + b - a > original.length || !original.subarray(at, at + b - a).every(v => v === 255)) throw new Error("declared free run is not FF in original");
  }
  const writes = spans.map(s => [0xbfffff00 + s.file, 0xbfffff00 + s.file + s.length]);
  const ram = patches.flatMap(p => (p.ram ?? []).map(r => [Number(r.at), Number(r.at) + r.length]));
  if (ram.some(([a, b]) => !Number.isSafeInteger(a) || !Number.isSafeInteger(b) || b <= a || !free.some(([c, d]) => c <= a && b <= d))) throw new Error("RAM outside free runs");
  const code = clip(writes, free);
  const occupied = union([...code, ...ram]);
  const gaps = [];
  for (const [a, b] of free) {
    let at = a;
    for (const [c, d] of clip(occupied, [[a, b]])) { if (at < c) gaps.push([at, c]); at = Math.max(at, d); }
    if (at < b) gaps.push([at, b]);
  }
  return { freeBytes: size(free), codeDataBytes: size(code), ramBytes: size(ram), occupiedBytes: size(occupied),
    unallocatedBytes: size(gaps), largestGap: Math.max(0, ...gaps.map(([a, b]) => b - a)), gaps,
    patches: patches.map(p => ({ id: p.id, codeDataBytes: size(clip(writes.filter((_, i) => spans[i].patch === p.id), free)), ramBytes: size((p.ram ?? []).map(r => [Number(r.at), Number(r.at) + r.length])) })) };
}

function requiredGroups(patches, build) {
  const byId = { "splash-editor": "splash_cases", "mfx-switch": "mfx_cases", "script-runtime": "menu_cases", "pattern-switch": "pswitch_cases",
    "tap-motion": "tap_motion_cases", "note-assistant": "note_assist_cases", dice: "dice_cases", "ifx-idle": "ifx_idle_cases", "load-bar": "loadbar_cases",
    "sample-errors": "sample_error_cases", "synth-filters": "synth_filter_cases", "power-off": "power_off_cases", "blech-sysex": "sysex_cases", "preset-tables": "preset_cases",
    "last-pattern": "last_pattern_cases", "init-pattern": "init_pattern_cases" };
  const groups = ["bootmap", ...patches.map(p => byId[p.id]).filter(Boolean)];
  if (patches.some(p => p.id === "script-runtime")) groups.push("shortcut_cases");
  if (build !== "synth" && patches.some(p => p.id === "script-runtime")) groups.push("migrate_cases");
  return [...new Set(groups)];
}

async function sourceFiles() {
  const paths = [];
  const walk = folder => {
    for (const entry of readdirSync(join(ROOT, folder), { withFileTypes: true })) {
      if (entry.name.startsWith(".") || entry.name === "__pycache__") continue;
      const path = `${folder}/${entry.name}`;
      if (entry.isDirectory()) walk(path); else if (/\.(mjs|py|s|json)$/.test(entry.name) && !entry.name.startsWith("test_") && !["patch_performance.py", "check_sets.mjs"].includes(entry.name)) paths.push(path);
    }
  };
  for (const folder of ["tools/emu", "tools/patch", "data", "src"]) walk(folder);
  return Object.fromEntries(await Promise.all(paths.sort().map(async path => [path, await sha256(readFileSync(join(ROOT, path)))])));
}

export async function runSets(inputFile, output) {
  const spec = JSON.parse(readFileSync(inputFile, "utf8"));
  validateInputs(spec);
  mkdirSync(output, { recursive: true });
  const location = relative(realpathSync(ROOT), realpathSync(output));
  if (!isAbsolute(location) && location !== ".." && !location.startsWith(`..${process.platform === "win32" ? "\\" : "/"}`)) throw new Error("firmware output must be outside the repository");
  if (readdirSync(output).length) throw new Error("output directory must be empty");
  const python = process.env.E2_EMU_PYTHON || join(ROOT, "tools/emu/.venv/bin/python");
  const probe = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
  if (probe.error || probe.status !== 0) throw new Error(`emulator required: ${probe.error?.message ?? probe.stderr}`);
  const commit = spawnSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).stdout.trim();
  const sources = await sourceFiles();
  const { PRESETS } = await import("../../data/script/presets.mjs");
  const { compile } = await import("../../src/script/compiler.mjs");
  const programs = Object.fromEntries(PRESETS.map(preset => {
    const result = compile(preset.source, { name: preset.id });
    if (!result.ok) throw new Error(`${preset.id}: compile failed`);
    return [preset.id, { name: result.info.app?.name ?? preset.title, blob: Buffer.from(result.blob).toString("hex"), info: result.info }];
  }));
  writeFileSync(join(output, "programs.json"), JSON.stringify(programs, null, 2) + "\n");
  const summary = { format: "blech-check-sets", version: 1, commit, sources, builds: {}, ok: false };
  writeFileSync(join(output, "contract.inc"), (await import("../../src/script/arm-tables.mjs")).asmInclude());
  for (const build of BUILDS) {
    try {
      const input = resolve(dirname(inputFile), spec[build].path);
      const original = new Uint8Array(readFileSync(input));
      if (await sha256(original) !== spec[build].sha256) throw new Error("original SHA-256 differs");
      if (buildOf(original) !== build) throw new Error("original build differs");
      const set = await loadBlechSet(path => JSON.parse(readFileSync(join(ROOT, path), "utf8")), build === "synth" ? BLECH_SYNTH_SET_URL : BLECH_SET_URL);
      const selected = selectFor(set.patches, build);
      if (selected.reasons.length) throw new Error(selected.reasons.join("; "));
      const result = await applyPatches(original, set.patches);
      if (!result.ok) throw new Error(result.reasons.join("; "));
      const baseName = `${build}-original.VSB`, patchedName = `${build}.VSB`;
      const base = join(output, baseName), patched = join(output, patchedName);
      writeFileSync(base, original); writeFileSync(patched, result.bytes);
      const metadata = { inputSha256: await sha256(original), outputSha256: await sha256(result.bytes), original: baseName, patched: patchedName,
        set: set.id, patches: selected.patches.map(p => p.id), allow: result.allow, allowCode: result.allowCode,
        spans: result.spans, footprint: footprint(original, result.spans, selected.patches, build === "synth" ? SYNTH_FREE_RUNS : FREE_RUNS),
        freeRuns: build === "synth" ? SYNTH_FREE_RUNS : FREE_RUNS, requiredGroups: requiredGroups(selected.patches, build) };
      summary.builds[build] = metadata;
      writeFileSync(join(output, "sets.json"), JSON.stringify(summary, null, 2) + "\n");
      console.log(`${build}: ${metadata.patches.length} patches; full check.py`);
      const args = [join(ROOT, "tools/emu/check.py"), ...checkArguments(base, patched, result)];
      const run = spawnSync(python, args, { cwd: ROOT, env: { ...process.env, GELUMPE_CACHE: "off" }, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
      writeFileSync(join(output, `${build}-check.log`), run.stderr ?? "");
      writeFileSync(join(output, `${build}-check.json`), run.stdout || "null\n");
      if (run.error) throw run.error;
      const report = JSON.parse(run.stdout);
      const progress = (run.stderr ?? "").split("\n").flatMap(line => { try { const p = JSON.parse(line).progress; return p ? [p] : []; } catch { return []; } }).at(-1);
      validateReport(report, run.status, progress, metadata.requiredGroups);
      metadata.checks = report.checks.length; metadata.progress = progress; metadata.ok = true;
      console.log(`${build}: ${metadata.checks} checks passed`);
    } catch (error) {
      summary.builds[build] = { ...summary.builds[build], ok: false, error: error.message };
      console.error(`${build}: ${error.message}`);
    }
  }
  summary.ok = BUILDS.every(build => summary.builds[build]?.ok === true);
  summary.sourcesUnchanged = JSON.stringify(sources) === JSON.stringify(await sourceFiles());
  summary.ok &&= summary.sourcesUnchanged;
  writeFileSync(join(output, "sets.json"), JSON.stringify(summary, null, 2) + "\n");
  return summary;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = process.argv.slice(2);
    if (args.length !== 4 || args[0] !== "--inputs" || args[2] !== "--out") throw new Error("usage: check_sets.mjs --inputs INPUTS.json --out PRIVATE_EMPTY_DIRECTORY");
    process.exitCode = (await runSets(resolve(args[1]), resolve(args[3]))).ok ? 0 : 1;
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
