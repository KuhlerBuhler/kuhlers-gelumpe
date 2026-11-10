import { test } from "node:test";
import assert from "node:assert/strict";
import { busyReason, waitForLoad } from "../tools/load-gate.mjs";

test("busy when the 1 minute load reaches 0.8 x cores", () => {
  assert.equal(busyReason({ load1: 7.9, cores: 10 }), null);
  assert.match(busyReason({ load1: 8, cores: 10 }), /load 8\.0 on 10 cores, limit 8\.0/);
  assert.notEqual(busyReason({ load1: 4, cores: 10, max: 0.3 }), null);
});

test("busy when free memory is below the minimum, unknown memory does not block", () => {
  assert.match(busyReason({ load1: 1, cores: 10, memoryFree: 5 }), /free memory 5%/);
  assert.equal(busyReason({ load1: 1, cores: 10, memoryFree: 40 }), null);
  assert.equal(busyReason({ load1: 1, cores: 10, memoryFree: null }), null);
});

const busy = { load1: 20, cores: 10, memoryFree: 50 };
const quiet = { load1: 1, cores: 10, memoryFree: 50 };
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
  assert.equal(await waitForLoad({ env: { GELUMPE_LOAD_MAX: "3" }, read: () => busy, sleep: noSleep, log: () => {} }), true);
});
