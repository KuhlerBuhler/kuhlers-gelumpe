import { test } from "node:test";
import assert from "node:assert/strict";
import { run } from "./support/spawn.mjs";

// `run` stands in for spawnSync in the emulator tests. A child the system ended has no exit status,
// and a failure that only says "null" hides what happened (the memory killer, a segfault).
const noSignals = process.platform === "win32" ? "Windows has no signals to report" : false;

test("a normal run carries its status, its output and no signal", async () => {
  const r = await run(process.execPath, ["-e", "console.log('hello'); console.error('careful')"]);
  assert.deepEqual({ status: r.status, signal: r.signal, error: r.error },
    { status: 0, signal: null, error: undefined });
  assert.equal(r.stdout.trim(), "hello");
  assert.equal(r.stderr.trim(), "careful");
});

test("input is delivered completely and ends before the child finishes", async () => {
  const code = "const chunks=[];process.stdin.on('data',c=>chunks.push(c));process.stdin.on('end',()=>process.stdout.write(Buffer.concat(chunks)))";
  for (const input of ["", "ä".repeat(150_000), Buffer.from([0, 1, 127, 255])]) {
    const r = await run(process.execPath, ["-e", code], { input, timeout: 3000 });
    assert.ifError(r.error);
    assert.equal(r.status, 0);
    assert.equal(r.stdout, Buffer.from(input).toString("utf8"));
  }
});

test("a run killed from outside names the signal that ended it", { skip: noSignals }, async () => {
  const r = await run(process.execPath, ["-e", "process.kill(process.pid, 'SIGKILL')"]);
  assert.equal(r.status, null);
  assert.equal(r.signal, "SIGKILL");
  assert.equal(r.error, undefined);
});

test("a run that outlives its timeout is killed and says so", async () => {
  const r = await run(process.execPath, ["-e", "setTimeout(() => {}, 60_000)"], { timeout: 300 });
  assert.equal(r.error?.code, "ETIMEDOUT");
  assert.equal(r.status, null);
});
