import test from "node:test";
import assert from "node:assert/strict";
import { LedPlayer, DELAY_MS } from "../site/app/led-trace.mjs";

const PAD = 0x2c;
// One service step: the device time at its end and the changes in it, in microseconds.
const step = (nowMs, changes) => ({ now: nowMs * 1000, changes: changes.map(([ms, led, v]) => [ms * 1000, ms * 1000, led, v]) });

test("led trace: a change shows at its device time, a fixed delay after the step", () => {
  const p = new LedPlayer();
  p.table({ [PAD]: 0 });
  p.trace(step(1000, [[990, PAD, 255]]), 5000);           // the step ends at device 1000 ms, page clock 5000 ms
  assert.deepEqual(p.frame(5000 + DELAY_MS - 20), {}, "not yet");
  assert.deepEqual(p.frame(5000 + DELAY_MS), { [PAD]: 255 / 2 }, "lit for the last 10 of the 20 ms of this frame");
  assert.deepEqual(p.frame(5000 + DELAY_MS + 20), { [PAD]: 255 }, "then fully");
  assert.equal(p.busy, false);
});

test("led trace: a short dark gap inside one frame dims that frame instead of vanishing", () => {
  const p = new LedPlayer();
  p.table({ [PAD]: 255 });
  p.trace(step(1000, [[1004, PAD, 0], [1009, PAD, 255]]), 0);   // dark for 5 ms
  const at = 1000 + p.offset;                                     // page time of device 1000 ms
  p.frame(at);
  const dip = p.frame(at + 16);
  assert.ok(Math.abs(dip[PAD] - 255 * 11 / 16) < 1e-9, `the frame shows 11 of 16 ms lit: ${dip[PAD]}`);
  assert.deepEqual(p.frame(at + 32), { [PAD]: 255 }, "the next frame is lit again");
  assert.deepEqual(p.frame(at + 48), {}, "and then nothing changes");
});

test("led trace: the steps keep the device's distances, a lagging service is laid onto the page clock again", () => {
  const p = new LedPlayer();
  p.trace(step(1000, [[1000, PAD, 255]]), 0);
  const first = p.queue[0].at;
  p.trace(step(1020, [[1020, PAD, 0]]), 20);
  assert.equal(p.queue[1].at - first, 20, "20 ms apart on the device, 20 ms apart on the page");
  p.frame(first + 100);
  p.trace(step(1040, [[1040, PAD, 255]]), 2000);                  // the service fell behind by almost 2 s
  assert.equal(p.queue[0].at, 2000 + DELAY_MS, "shown a delay after it came, not in the past");
});

test("led trace: the order of the firmware holds when the clock is laid again", () => {
  const p = new LedPlayer();
  p.trace(step(1000, [[1000, PAD, 255]]), 0);
  p.trace(step(5000, [[100, PAD, 0]]), 1);                         // device time far ahead: a new offset
  assert.ok(p.queue[1].at >= p.queue[0].at);
});

test("led trace: the whole table replaces what waits", () => {
  const p = new LedPlayer();
  p.trace(step(1000, [[1000, PAD, 255]]), 0);
  p.table({ [PAD + 1]: 64 });
  assert.equal(p.queue.length, 0);
  assert.deepEqual(p.frame(10_000), {});
  assert.equal(p.busy, false);
});
