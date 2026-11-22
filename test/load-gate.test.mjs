import { test } from "node:test";
import assert from "node:assert/strict";
import { busyReason, cpuBusyBetween, readMachine, waitForLoad } from "../tools/load-gate.mjs";

test("busy when the CPUs are 80 % busy", () => {
  assert.equal(busyReason({ cpuBusy: 0.79, cores: 10 }), null);
  assert.match(busyReason({ cpuBusy: 0.8, cores: 10 }), /CPU 80% busy on 10 cores, limit 80%/);
  assert.notEqual(busyReason({ cpuBusy: 0.4, cores: 10, max: 0.3 }), null);
});

test("the busy share counts every CPU time but idle, over all cores", () => {
  const t = (user, idle) => ({ times: { user, nice: 0, sys: 0, idle, irq: 0 } });
  assert.equal(cpuBusyBetween([t(0, 0), t(0, 0)], [t(100, 0), t(0, 100)]), 0.5);
  assert.equal(cpuBusyBetween([t(5, 5)], [t(5, 5)]), null);
});

test("reads this machine", async () => {
  const m = await readMachine({ sampleMs: 200 });
  assert.ok(m && m.cpuBusy >= 0 && m.cpuBusy <= 1 && m.cores > 0, JSON.stringify(m));
});

test("busy when free memory is below the minimum, unknown memory does not block", () => {
  assert.match(busyReason({ cpuBusy: 0.1, cores: 10, memoryFree: 5 }), /free memory 5%/);
  assert.equal(busyReason({ cpuBusy: 0.1, cores: 10, memoryFree: 40 }), null);
  assert.equal(busyReason({ cpuBusy: 0.1, cores: 10, memoryFree: null }), null);
});

const busy = { cpuBusy: 0.95, cores: 10, memoryFree: 50 };
const quiet = { cpuBusy: 0.1, cores: 10, memoryFree: 50 };
const noSleep = async () => {};

test("waits while busy, starts when quiet", async () => {
  const reads = [busy, busy, quiet];
  const lines = [];
  const ok = await waitForLoad({ env: {}, read: () => reads.shift(), sleep: noSleep, log: m => lines.push(m) });
  assert.equal(ok, true);
  assert.equal(lines.length, 2);
});

test("gives up after the max wait", async () => {
  const lines = [];
  const env = { GELUMPE_LOAD_WAIT: "30", GELUMPE_LOAD_POLL: "10" };
  assert.equal(await waitForLoad({ env, read: () => busy, sleep: noSleep, log: m => lines.push(m) }), false);
  assert.match(lines.at(-1), /not starting/);
});

test("CI, the off switch and a passed outer gate skip it", async () => {
  for (const env of [{ CI: "1" }, { GELUMPE_LOAD_GATE: "off" }, { GELUMPE_LOAD_GATE_PASSED: "1" }]) {
    assert.equal(await waitForLoad({ env, read: () => busy, sleep: noSleep, log: () => {} }), true);
  }
});

test("the threshold can be raised by env", async () => {
  assert.equal(await waitForLoad({ env: { GELUMPE_LOAD_MAX: "1" }, read: () => busy, sleep: noSleep, log: () => {} }), true);
});
