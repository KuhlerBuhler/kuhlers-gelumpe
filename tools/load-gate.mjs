#!/usr/bin/env node
/**
 * Load gate: waits until the machine is quiet before a local test run starts (docs/development.md).
 *
 *   node tools/load-gate.mjs [command ...]
 *
 * Env: GELUMPE_LOAD_GATE=off skips, GELUMPE_LOAD_MAX (0.8 x cores), GELUMPE_LOAD_WAIT (1200 s), GELUMPE_LOAD_POLL (15 s).
 * GELUMPE_LOAD_GATE_PASSED=1 is set after passing so nested gated runs do not wait twice.
 */
import { spawn, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { cpus } from "node:os";
import { fileURLToPath } from "node:url";

export const DEFAULTS = { max: 0.8, memoryFreeMin: 10, waitSeconds: 1200, pollSeconds: 15 };

/** Pure decision. `memoryFree` is a percentage or null when unknown. Returns null when quiet, else the reason. */
export function busyReason({ load1, cores, max = DEFAULTS.max, memoryFree = null, memoryFreeMin = DEFAULTS.memoryFreeMin }) {
  const limit = max * cores;
  if (load1 >= limit) return `load ${load1.toFixed(1)} on ${cores} cores, limit ${limit.toFixed(1)} (${max} x cores)`;
  if (memoryFree !== null && memoryFree < memoryFreeMin) return `free memory ${memoryFree}%, limit ${memoryFreeMin}%`;
  return null;
}

function sysctl(name) {
  const run = spawnSync("sysctl", ["-n", name], { encoding: "utf8" });
  return run.status === 0 ? run.stdout.trim() : "";
}

/** { load1, cores, memoryFree } of this machine, or null when it cannot be read (then there is no gate). */
export function readMachine() {
  try {
    if (process.platform === "darwin") {
      const load1 = Number(sysctl("vm.loadavg").match(/[\d.]+/)?.[0]);
      const free = Number(sysctl("kern.memorystatus_level"));
      return Number.isFinite(load1) ? { load1, cores: Number(sysctl("hw.ncpu")) || cpus().length, memoryFree: free > 0 ? free : null } : null;
    }
    const load1 = Number(readFileSync("/proc/loadavg", "utf8").split(" ")[0]);
    const mem = readFileSync("/proc/meminfo", "utf8");
    const total = Number(mem.match(/MemTotal:\s+(\d+)/)?.[1]);
    const available = Number(mem.match(/MemAvailable:\s+(\d+)/)?.[1]);
    return Number.isFinite(load1) ? { load1, cores: cpus().length, memoryFree: total > 0 && available >= 0 ? Math.round(100 * available / total) : null } : null;
  } catch {
    return null;
  }
}

const number = (text, fallback) => (Number.isFinite(Number(text)) && Number(text) > 0 ? Number(text) : fallback);

/** Waits until the machine is quiet. Resolves true when the run may start, false after the max wait. */
export async function waitForLoad({ env = process.env, read = readMachine, sleep = ms => new Promise(r => setTimeout(r, ms)), log = m => process.stderr.write(m + "\n") } = {}) {
  if (env.CI || env.GELUMPE_LOAD_GATE === "off" || env.GELUMPE_LOAD_GATE_PASSED === "1") return true;
  const max = number(env.GELUMPE_LOAD_MAX, DEFAULTS.max);
  const waitMs = number(env.GELUMPE_LOAD_WAIT, DEFAULTS.waitSeconds) * 1000;
  const pollMs = number(env.GELUMPE_LOAD_POLL, DEFAULTS.pollSeconds) * 1000;
  let waited = 0;
  for (;;) {
    const machine = read();
    const reason = machine && busyReason({ ...machine, max });
    if (!reason) return true;
    if (waited >= waitMs) {
      log(`load gate: still busy after ${Math.round(waited / 1000)} s (${reason}), not starting. GELUMPE_LOAD_GATE=off skips the gate.`);
      return false;
    }
    log(`load gate: machine busy, ${reason}; checking again in ${pollMs / 1000} s (gives up after ${waitMs / 1000} s)`);
    await sleep(pollMs);
    waited += pollMs;
  }
}

/** The gate for a script: waits, exits 1 when it gives up, marks the environment for what the script starts. */
export async function loadGate() {
  if (!(await waitForLoad())) process.exit(1);
  process.env.GELUMPE_LOAD_GATE_PASSED = "1";
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  await loadGate();
  const [command, ...args] = process.argv.slice(2);
  if (command) {
    const child = spawn(command, args, { stdio: "inherit" });
    for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(signal, () => child.kill(signal));
    child.on("error", error => { console.error(error.message); process.exit(127); });
    child.on("close", (status, signal) => process.exit(status ?? (signal ? 128 : 1)));
  }
}
