import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { PATTERN_STEPS } from "../data/script/contract.mjs";

const LENGTH = 37;

/** Step Copy on the simulated device, the pattern in RAM `bars` bars long, part `part` selected. */
function plugin({ bars = 4, part = 0 } = {}) {
  const result = compile(PRESETS.find(p => p.id === "stepcopy").source, { name: "stepcopy" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice();
  assert.ok(device.load(result.blob).ok);
  const hw = device.hardware;
  hw.patternBlock(-1)[LENGTH] = bars - 1;
  hw.part = part;
  device.run(2);
  const page = label => device.menus.find(m => m.label === label);
  const set = (label, value) => { device.menuSet(page(label).id, value); device.run(1); };
  const fill = (p, step, note, velocity = 100) => {
    const b = hw.patternBlock(-1);
    const o = hw.stepAt(p, step);
    b[o + PATTERN_STEPS.on] = 1;
    b[o + PATTERN_STEPS.gate] = 60;
    b[o + PATTERN_STEPS.velocity] = velocity;
    b[o + PATTERN_STEPS.trigger] = 1;
    b[o + PATTERN_STEPS.notes] = note + 1;
  };
  const record = (p, step) => [...hw.patternBlock(-1).subarray(hw.stepAt(p, step), hw.stepAt(p, step) + PATTERN_STEPS.stride)];
  const copy = mode => { set("STEP COPY", mode); device.run(40); };
  return { device, hw, set, fill, record, copy, page };
}

test("Step Copy: bar 1 into bar 2 copies the selected part's steps whole, other bars and parts stay", () => {
  const p = plugin({ part: 3 });
  p.fill(3, 0, 36);
  p.fill(3, 5, 40, 77);
  p.fill(3, 15, 43);
  p.fill(5, 0, 50);
  p.set("STEP COPY TO", 2);
  p.copy(1);
  for (const s of [0, 5, 15]) assert.deepEqual(p.record(3, 16 + s), p.record(3, s), `step ${s}`);
  assert.equal(p.record(3, 21)[PATTERN_STEPS.notes], 41);
  assert.equal(p.record(3, 17)[PATTERN_STEPS.on], 0, "an empty step stays empty");
  assert.equal(p.record(5, 16)[PATTERN_STEPS.on], 0, "another part is left alone");
  assert.equal(p.record(3, 32)[PATTERN_STEPS.on], 0, "bar 3 is left alone");
  assert.deepEqual(p.device.status().scripts.map(s => s.fault ?? null), [null]);
});

test("Step Copy: all parts into bar 3", () => {
  const p = plugin();
  p.fill(0, 2, 30);
  p.fill(9, 2, 60);
  p.set("STEP COPY TO", 3);
  p.copy(2);
  assert.deepEqual(p.record(0, 34), p.record(0, 2));
  assert.deepEqual(p.record(9, 34), p.record(9, 2));
  assert.equal(p.record(9, 18)[PATTERN_STEPS.on], 0, "bar 2 is left alone");
});

test("Step Copy: TO 0 fills every bar after the source up to the pattern's length", () => {
  const p = plugin({ bars: 3 });
  p.fill(0, 20, 55);
  p.set("STEP COPY FROM", 2);
  p.set("STEP COPY TO", 0);
  p.copy(1);
  assert.deepEqual(p.record(0, 36), p.record(0, 20), "bar 3 gets bar 2");
  assert.equal(p.record(0, 52)[PATTERN_STEPS.on], 0, "bar 4 is outside the length, nothing written");
  assert.equal(p.hw.patternValue(-1, -1, 2), 3, "the length stays");
});

test("Step Copy: a target bar beyond the length lengthens the pattern, a source bar beyond it copies nothing", () => {
  const p = plugin({ bars: 1 });
  p.fill(0, 4, 48);
  p.set("STEP COPY TO", 3);
  p.copy(1);
  assert.equal(p.hw.patternValue(-1, -1, 2), 3, "length 3 bars");
  assert.deepEqual(p.record(0, 36), p.record(0, 4));
  const q = plugin({ bars: 2 });
  q.fill(0, 0, 40);
  q.set("STEP COPY FROM", 4);
  q.set("STEP COPY TO", 1);
  q.copy(1);
  assert.equal(q.hw.patternValue(-1, -1, 2), 2);
  assert.equal(q.record(0, 0)[PATTERN_STEPS.notes], 41, "nothing was overwritten");
});

test("Step Copy: the copy waits for the dial to rest, 0 copies nothing, the same bar is no copy", () => {
  const p = plugin();
  p.fill(0, 0, 36);
  p.set("STEP COPY TO", 2);
  p.set("STEP COPY", 1);
  p.set("STEP COPY", 2);
  p.set("STEP COPY", 0);
  p.device.run(40);
  assert.equal(p.record(0, 16)[PATTERN_STEPS.on], 0, "turned past 1 and 2 back to 0: nothing copied");
  p.set("STEP COPY TO", 1);
  p.copy(1);
  assert.equal(p.record(0, 16)[PATTERN_STEPS.on], 0, "source and target the same bar");
  assert.equal(p.record(0, 0)[PATTERN_STEPS.on], 1);
});

test("Step Copy: the pages start at bar 1 to bar 2, nothing to copy", () => {
  const p = plugin();
  assert.deepEqual(["STEP COPY FROM", "STEP COPY TO", "STEP COPY"].map(l => p.page(l).value), [1, 2, 0]);
});
