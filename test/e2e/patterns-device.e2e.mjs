import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { makeFirmware, makePattern } from "../helpers.mjs";

let h;
before(async () => {
  h = await setUp();
  h.file("system.vsb", await makeFirmware());
  const start = makePattern();
  for (let p = 0; p < 16; p++) {
    start[0x800 + p * 0x330 + 37] = 0;
    start[0x800 + p * 0x330 + 13] = 64;
  }
  h.file("pattern.bin", start);
});
after(async () => { await h.tearDown(); });

async function open({ unknown = false } = {}) {
  const page = await h.page({ device: true });
  if (unknown) await page.route("**/data/devices.mjs", r => r.fulfill({ contentType: "text/javascript", body: "export default [];" }));
  await page.goto(h.url);
  await page.evaluate(() => window.__ceeStubReady);
  return page;
}

test("browser pattern transport: a cutoff changes, is read back, and undo restores the entire buffer", async () => {
  const page = await open();
  const result = await page.evaluate(async () => {
    const { session, pattern, start, sim } = await (await import("/test-support/patterns.mjs")).patternSession();
    pattern.setRaw("part.cutoff", [0], 65);
    const sent = await session.apply({ kind: "patternSend", block: pattern.bytes });
    const changed = Array.from(sim.device.pattern.keys()).filter(i => start[i] !== sim.device.pattern[i]);
    const undone = await session.undo();
    return { sent: sent.ok, changed, undone: undone.ok, restored: sim.device.pattern.every((b, i) => b === start[i]) };
  });
  assert.deepEqual(result, { sent: true, changed: [0x800 + 13], undone: true, restored: true });
  assert.deepEqual(page.errors, []);
});

test("browser pattern transport: a step without trigger requires confirmation and sends nothing before it", async () => {
  const page = await open();
  const result = await page.evaluate(async () => {
    const { session, pattern, start, sim } = await (await import("/test-support/patterns.mjs")).patternSession();
    pattern.setRaw("step.on", [0, 0], 1);
    pattern.setRaw("step.trigger", [0, 0], 0);
    const res = await session.apply({ kind: "patternSend", block: pattern.bytes });
    return { confirm: res.needsConfirmation, reasons: res.gate.reasons.map(r => r.code), unchanged: sim.device.pattern.every((b, i) => b === start[i]) };
  });
  assert.equal(result.confirm, true);
  assert.ok(result.reasons.includes("step-without-trigger"));
  assert.equal(result.unchanged, true);
  assert.deepEqual(page.errors, []);
});

test("browser pattern transport: an unknown device is readable and takes no changed pattern", async () => {
  const page = await open({ unknown: true });
  const result = await page.evaluate(async () => {
    const { session, pattern, start, sim } = await (await import("/test-support/patterns.mjs")).patternSession();
    const read = pattern.bytes.every((b, i) => b === start[i]);
    pattern.setRaw("part.cutoff", [0], 65);
    const res = await session.apply({ kind: "patternSend", block: pattern.bytes });
    return { read, sent: res.ok, reasons: res.gate.reasons.map(r => r.code), unchanged: sim.device.pattern.every((b, i) => b === start[i]) };
  });
  assert.equal(result.read, true);
  assert.equal(result.sent, false);
  assert.ok(result.reasons.includes("unknown-device"));
  assert.equal(result.unchanged, true);
  assert.deepEqual(page.errors, []);
});
