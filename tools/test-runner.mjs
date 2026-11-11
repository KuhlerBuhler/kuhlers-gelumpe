#!/usr/bin/env node
import { spawn } from "node:child_process";
import { availableParallelism } from "node:os";
import { fileURLToPath } from "node:url";
import { loadGate } from "./load-gate.mjs";
import { ensureRuntimePatches } from "./patch/ensure-runtime.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const EMULATOR = ["test/emulator.test.mjs", "test/emulator-session.test.mjs", "test/emulator-card.test.mjs",
  "test/emulator-card-stock.test.mjs", "test/emulator-stock.test.mjs", "test/emulator-update.test.mjs",
  "test/emulator-blue.test.mjs", "test/emulator-modtable.test.mjs", "test/emulator-sample-full.test.mjs",
  "test/emulator-sample-meta.test.mjs", "test/emulator-blechy.test.mjs", "test/emulator-fxcard.test.mjs", "test/emu-service.test.mjs"];
const positive = value => Number.isSafeInteger(Number(value)) && Number(value) > 0 ? Number(value) : null;

export function planSuite(mode, { cores = availableParallelism(), budget = cores, env = process.env, args = [] } = {}) {
  if (!positive(budget)) throw new Error("the test CPU budget must be a positive integer");
  if (!["unit", "ci", "local", "browser", "emu"].includes(mode)) throw new Error(`unknown test suite: ${mode}`);
  const files = Math.min(2, budget);
  // GELUMPE_JOBS controls both Python processes per file and each process's worker pool.
  const maxJobs = Math.max(1, Math.floor(Math.sqrt(Math.floor(budget / files))));
  const jobs = Math.min(positive(env.GELUMPE_JOBS) ?? 2, maxJobs);
  const variables = { ...env, GELUMPE_JOBS: String(jobs) };
  if (mode === "local") variables.E2_LOCAL_REQUIRED = "1";
  if (mode === "emu") variables.E2_EMU_REQUIRED = "1";
  const timeout = mode === "browser" ? ["--test-timeout=180000"] : mode === "ci" ? ["--test-timeout=300000"] : [];
  const patterns = mode === "browser" ? ["test/e2e/*.e2e.mjs"] : mode === "emu" ? EMULATOR : ["test/*.test.mjs"];
  return { name: mode, budget, files, env: variables,
    args: ["--test", `--test-concurrency=${files}`, ...timeout, ...args, ...patterns] };
}

export function planAll({ cores = availableParallelism(), env = process.env } = {}) {
  const parallel = cores > 1;
  const unitBudget = parallel ? Math.ceil(cores / 2) : 1;
  const browserBudget = parallel ? Math.floor(cores / 2) : 1;
  const own = env.E2_VSB && env.E2_PATTERNS ? { E2_LOCAL_REQUIRED: "1" }
    : env.E2_VSB ? { E2_EMU_REQUIRED: "1" } : {};
  const unit = planSuite("unit", { cores, budget: unitBudget, env: { ...env, ...own }, args: ["--test-reporter=spec"] });
  unit.name = own.E2_LOCAL_REQUIRED ? "unit + emulator + own files" : own.E2_EMU_REQUIRED ? "unit + emulator" : "unit";
  return { parallel, suites: [unit, planSuite("browser", { cores, budget: browserBudget, env, args: ["--test-reporter=spec"] })] };
}

export function runNode(plan, { cwd = root, executable = process.execPath, capture = false } = {}) {
  // The runtime patches are built, not committed: every suite, and every run of test-all.mjs, starts with them in place.
  ensureRuntimePatches({ log: message => process.stderr.write(message + "\n") });
  const start = Date.now();
  return new Promise(resolve => {
    const child = spawn(executable, plan.args, { cwd, env: { ...process.env, ...plan.env }, stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit" });
    let output = "";
    const signals = ["SIGINT", "SIGTERM", "SIGHUP"];
    const forward = signal => child.kill(signal);
    const handlers = signals.map(signal => [signal, () => forward(signal)]);
    for (const [signal, handler] of handlers) process.on(signal, handler);
    const finish = result => {
      for (const [signal, handler] of handlers) process.off(signal, handler);
      resolve({ ...result, output, seconds: (Date.now() - start) / 1000 });
    };
    if (capture) {
      child.stdout.setEncoding("utf8").on("data", data => { output += data; });
      child.stderr.setEncoding("utf8").on("data", data => { output += data; });
    }
    child.on("error", error => finish({ status: null, signal: null, error }));
    child.on("close", (status, signal) => finish({ status, signal }));
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    await loadGate();
    const result = await runNode(planSuite(process.argv[2] ?? "unit", { args: process.argv.slice(3) }));
    if (result.error) console.error(result.error.message);
    if (result.signal) process.kill(process.pid, result.signal);
    else process.exitCode = result.status ?? 1;
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
