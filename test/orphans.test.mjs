import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { emuPython } from "./support/emu.mjs";

// No emulator process outlives the run that started it, whatever ended the run. Each case starts a
// "run" of its own (a node or Python process that starts the service or the pool), ends it the hard
// way and looks for what it left. Needs no firmware and no Unicorn.
const root = fileURLToPath(new URL("../", import.meta.url));
const python = emuPython();
const skip = process.platform === "win32" ? "uses ps and POSIX signals" : spawnSync(python, ["--version"]).error ? `${python} not found` : false;
const emuUrl = pathToFileURL(join(root, "test/support/emu.mjs")).href;
const GONE_WITHIN_MS = 8_000;

const wait = ms => new Promise(r => setTimeout(r, ms));
const table = () => spawnSync("ps", ["-axo", "pid=,ppid=,stat=,command="], { encoding: "utf8" }).stdout.split("\n")
  .map(line => /^\s*(\d+)\s+(\d+)\s+(\S+)\s+(.*)$/.exec(line)).filter(Boolean)
  .map(m => ({ pid: Number(m[1]), ppid: Number(m[2]), stat: m[3], command: m[4] }));
/** Running, not a zombie that nobody collects (a container without init leaves those behind). */
const running = pid => table().some(p => p.pid === pid && !p.stat.startsWith("Z"));
const descendants = pid => {
  const rows = table();
  const found = new Set();
  const todo = [pid];
  while (todo.length) {
    const parent = todo.pop();
    for (const p of rows) if (p.ppid === parent && !found.has(p.pid)) { found.add(p.pid); todo.push(p.pid); }
  }
  return [...found];
};
async function until(check, ms = GONE_WITHIN_MS) {
  for (const end = Date.now() + ms; Date.now() < end; await wait(100)) if (check()) return true;
  return check();
}
const exited = proc => new Promise(resolve => (proc.exitCode !== null || proc.signalCode !== null ? resolve() : proc.once("exit", resolve)));

/** Ends the run for good; a failing case must not leave pipes open that keep this file from finishing. */
const dispose = proc => { proc.kill("SIGKILL"); proc.stdout.destroy(); proc.stderr.destroy(); };

/** Starts `command` as the "run"; resolves with it and its first line of output (JSON when the line is). */
async function startRun(command, args) {
  const proc = spawn(command, args, { cwd: root, stdio: ["ignore", "pipe", "pipe"] });
  let stderr = "";
  proc.stderr.on("data", d => { stderr += d; });
  const line = await new Promise((resolve, reject) => {
    let out = "";
    const timer = setTimeout(() => reject(new Error(`the run printed nothing: ${stderr}`)), 20_000);
    proc.stdout.on("data", d => {
      out += d;
      if (out.includes("\n")) { clearTimeout(timer); resolve(out.split("\n")[0]); }
    });
    proc.once("exit", code => { clearTimeout(timer); reject(new Error(`the run ended with ${code}: ${stderr}`)); });
  });
  return { proc, line };
}

const serviceRun = `
import { startService } from ${JSON.stringify(emuUrl)};
const service = await startService();
console.log(JSON.stringify({ pid: service.child.pid, cards: service.cards }));
setInterval(() => {}, 1000);
`;

for (const signal of ["SIGKILL", "SIGTERM", "SIGINT", "SIGHUP"]) {
  test(`orphans: a service is gone, with its temporary folder, after its test run gets ${signal}`, { skip }, async () => {
    const { proc, line } = await startRun(process.execPath, ["--input-type=module", "-e", serviceRun]);
    const { pid, cards } = JSON.parse(line);
    try {
      assert.ok(running(pid), "the service runs");
      assert.ok(existsSync(cards), "and has its folder");
      proc.kill(signal);
      await exited(proc);
      assert.ok(await until(() => !running(pid)), `the service (pid ${pid}) is still running ${GONE_WITHIN_MS} ms after the run got ${signal}`);
      assert.ok(await until(() => !existsSync(cards)), `the folder ${cards} is still there`);
    } finally {
      try { process.kill(pid, "SIGKILL"); } catch {}
      dispose(proc);
    }
  });
}

test("orphans: a test file and its service are gone after the test runner gets SIGKILL", { skip }, async () => {
  const runnerRun = `
import { spawn } from "node:child_process";
const file = spawn(process.execPath, ["--input-type=module", "-e", ${JSON.stringify(serviceRun)}], { stdio: ["ignore", "pipe", "inherit"] });
file.stdout.once("data", d => console.log(JSON.stringify({ file: file.pid, ...JSON.parse(String(d).split("\\n")[0]) })));
setInterval(() => {}, 1000);
`;
  const { proc, line } = await startRun(process.execPath, ["--input-type=module", "-e", runnerRun]);
  const { file, pid, cards } = JSON.parse(line);
  try {
    assert.ok(running(file) && running(pid), "the test file and its service run");
    proc.kill("SIGKILL");
    await exited(proc);
    assert.ok(await until(() => !running(file) && !running(pid)), `still running ${GONE_WITHIN_MS} ms after the runner got SIGKILL: ${[file, pid].filter(running)}`);
    assert.ok(await until(() => !existsSync(cards)), `the folder ${cards} is still there`);
  } finally {
    for (const orphan of [file, pid]) try { process.kill(orphan, "SIGKILL"); } catch {}
    dispose(proc);
  }
});

test("orphans: pool workers are gone after the process that started the pool gets SIGKILL", { skip }, async () => {
  const code = [
    "import sys",
    "sys.path.insert(0, 'tools/emu')",
    "import parallel",
    "print('ready', flush=True)",
    "parallel.run_tasks([('time', 'sleep', (120,))] * 3, {}, 3)",
  ].join("\n");
  const { proc } = await startRun(python, ["-c", code]);
  let workers = [];
  try {
    assert.ok(await until(() => (workers = descendants(proc.pid)).length >= 3, 20_000), "the pool starts its workers");
    proc.kill("SIGKILL");
    await exited(proc);
    assert.ok(await until(() => workers.every(pid => !running(pid))), `workers still running after ${GONE_WITHIN_MS} ms: ${workers.filter(running)}`);
  } finally {
    for (const pid of workers) try { process.kill(pid, "SIGKILL"); } catch {}
    dispose(proc);
  }
});

test("orphans: a one-shot tool that was given its parent ends with it", { skip }, async () => {
  const toolRun = `
import { spawn } from "node:child_process";
import { parentEnv } from ${JSON.stringify(pathToFileURL(join(root, "test/support/lifetime.mjs")).href)};
const code = "import sys, time; sys.path.insert(0, 'tools/emu'); import lifetime; lifetime.exit_with_parent(); time.sleep(120)";
const tool = spawn(${JSON.stringify(python)}, ["-c", code], { cwd: ${JSON.stringify(root)}, env: parentEnv(), stdio: "ignore" });
console.log(tool.pid);
setInterval(() => {}, 1000);
`;
  const { proc, line } = await startRun(process.execPath, ["--input-type=module", "-e", toolRun]);
  const pid = Number(line);
  try {
    assert.ok(running(pid), "the tool runs");
    proc.kill("SIGKILL");
    await exited(proc);
    assert.ok(await until(() => !running(pid)), `the tool (pid ${pid}) is still running ${GONE_WITHIN_MS} ms after its parent got SIGKILL`);
  } finally {
    try { process.kill(pid, "SIGKILL"); } catch {}
    dispose(proc);
  }
});

test("orphans: --ephemeral refuses a folder outside the temporary folder and leaves it alone", { skip }, () => {
  const folder = join(homedir(), ".gelumpe-test-ephemeral-must-not-exist");
  const run = spawnSync(python, [join(root, "tools/emu/server.py"), "--ephemeral", "--sd-dir", folder, "--port", "0"], { encoding: "utf8", timeout: 20_000 });
  assert.equal(run.status, 1, run.stderr);
  assert.match(run.stderr, /--ephemeral/);
  assert.equal(existsSync(folder), false);
});
