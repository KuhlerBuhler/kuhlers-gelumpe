/**
 * What a test run starts, it also ends: child processes and temporary folders are removed on exit and on
 * SIGINT, SIGTERM and SIGHUP, and when the process that started this one is gone. SIGKILL cannot be caught;
 * the Python side covers it (tools/emu/lifetime.py).
 */
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const children = new Set();
const folders = new Set();
let armed = false;

function sweep() {
  for (const child of children) {
    try { child.kill("SIGKILL"); } catch {}
  }
  children.clear();
  for (const folder of folders) {
    try { rmSync(folder, { recursive: true, force: true }); } catch {}
  }
  folders.clear();
}

function arm() {
  if (armed) return;
  armed = true;
  process.on("exit", sweep);
  // A test file whose runner was killed would otherwise run on, with its services, as an orphan itself.
  const runner = process.ppid;
  setInterval(() => { if (process.ppid !== runner) process.exit(1); }, 1000).unref();
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.once(signal, () => {
      sweep();
      process.kill(process.pid, signal);
    });
  }
}

/** A child process that must not outlive this one. */
export function track(child) {
  arm();
  children.add(child);
  child.once("exit", () => children.delete(child));
  return child;
}

/** A temporary folder that is removed when this process ends. `release` removes it earlier. */
export function tempDir(prefix) {
  arm();
  const folder = mkdtempSync(join(tmpdir(), prefix));
  folders.add(folder);
  return folder;
}

export function release(folder) {
  folders.delete(folder);
  rmSync(folder, { recursive: true, force: true });
}

/** The environment for a Python tool started by a test: it ends with this process (tools/emu/lifetime.py). */
export const parentEnv = env => ({ ...(env ?? process.env), GELUMPE_PARENT_PID: String(process.pid) });
