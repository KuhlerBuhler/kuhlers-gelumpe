#!/usr/bin/env node
/**
 * Every test there is, side by side: the unit and emulator tests and the browser tests.
 *
 *   npm run test:all
 *
 * With E2_VSB (and E2_PATTERNS) set the tests against your own files run too, as in
 * `test:local` and `test:emu`; without them only what runs everywhere runs, as in CI.
 * A suite's output is shown in full when it fails, as a summary when it passes.
 * Passing emulator results are kept per input (tools/emu/bootcache.py); GELUMPE_CACHE=off runs them again.
 */
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const unitEnv = process.env.E2_VSB && process.env.E2_PATTERNS ? { E2_LOCAL_REQUIRED: "1" }
  : process.env.E2_VSB ? { E2_EMU_REQUIRED: "1" } : {};

const suites = [
  { name: unitEnv.E2_LOCAL_REQUIRED ? "unit + emulator + own files" : unitEnv.E2_EMU_REQUIRED ? "unit + emulator" : "unit",
    args: ["--test", "--test-reporter=spec", "test/*.test.mjs"], env: unitEnv },
  { name: "browser", args: ["--test", "--test-reporter=spec", "--test-timeout=180000", "test/e2e/*.e2e.mjs"], env: {} },
];

function runSuite({ name, args, env }) {
  const started = Date.now();
  return new Promise(resolve => {
    const child = spawn(process.execPath, args, { cwd: root, env: { ...process.env, ...env }, stdio: ["ignore", "pipe", "pipe"] });
    let output = "";
    child.stdout.on("data", d => { output += d; });
    child.stderr.on("data", d => { output += d; });
    child.on("close", status => resolve({ name, status, output, seconds: (Date.now() - started) / 1000 }));
  });
}

const results = await Promise.all(suites.map(runSuite));
for (const r of results) {
  const summary = r.output.split("\n").filter(l => /^ℹ (tests|pass|fail|cancelled|skipped|duration_ms)/.test(l)).join("  ").replaceAll("ℹ ", "");
  console.log(`${r.status === 0 ? "ok  " : "FAIL"} ${r.name}: ${r.seconds.toFixed(0)} s, ${summary}`);
  if (r.status !== 0) console.log(r.output);
}
if (!process.env.E2_VSB) console.log("Without E2_VSB the emulator tests are skipped (see README).");
process.exit(results.every(r => r.status === 0) ? 0 : 1);
