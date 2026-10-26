import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { API_BY_NAME, ERROR, PATTERN_PARTS, PATTERN_STEPS } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { decodeBlob } from "../src/script/blob.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import patternMap from "../data/map/pattern.mjs";

const build = source => {
  const result = compile(source, { name: "seq" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  return result.blob;
};
const loaded = (source, setup = () => {}) => {
  const device = new SimDevice();
  setup(device);
  assert.ok(device.load(build(source)).ok);
  device.frame();
  return device;
};

test("the step layout korg.seq writes is the one of the device map", () => {
  const offset = id => patternMap.fields.find(f => f.id === id).where.offset;
  const repeat = id => patternMap.fields.find(f => f.id === id).repeat;
  assert.equal(offset("step.on"), PATTERN_PARTS.base + PATTERN_STEPS.base + PATTERN_STEPS.on);
  assert.equal(offset("step.gate"), PATTERN_PARTS.base + PATTERN_STEPS.base + PATTERN_STEPS.gate);
  assert.equal(offset("step.velocity"), PATTERN_PARTS.base + PATTERN_STEPS.base + PATTERN_STEPS.velocity);
  assert.equal(offset("step.trigger"), PATTERN_PARTS.base + PATTERN_STEPS.base + PATTERN_STEPS.trigger);
  assert.equal(offset("step.note"), PATTERN_PARTS.base + PATTERN_STEPS.base + PATTERN_STEPS.notes);
  assert.deepEqual(repeat("step.on").map(r => [r.count, r.stride]), [[16, PATTERN_PARTS.stride], [PATTERN_STEPS.count, PATTERN_STEPS.stride]]);
  assert.equal(repeat("step.note").at(-1).count, 4, "four note places follow the trigger");
});

test("korg.seq is version 9, for the handlers that run in the UI task, with the documented ranges", () => {
  for (const name of ["korg.seq.setStep", "korg.seq.setGate", "korg.seq.clearPart"]) {
    const api = API_BY_NAME.get(name);
    assert.equal(api.since, 9, name);
    assert.ok(!api.events.includes("start") && !api.events.includes("save") && api.events.includes("step"), name);
  }
  assert.deepEqual(API_BY_NAME.get("korg.seq.setStep").args.map(a => [a.name, a.min, a.max]), [["part", 0, 15], ["step", 0, 63], ["note", -1, 127], ["velocity", 0, 127]]);
  assert.deepEqual(API_BY_NAME.get("korg.seq.setGate").args.map(a => [a.name, a.min, a.max]), [["part", 0, 15], ["step", 0, 63], ["gate", 0, 127]]);
  assert.equal(decodeBlob(build("korg.onEvent(\"step\", (s) => { korg.seq.setGate(0, s, 96); });")).header.apiVersion, 9);
  assert.equal(compile("korg.seq.clearPart(0);", { name: "seq" }).ok, false, "not in the body: the firmware has no pattern for it there yet");
});

test("setStep, setGate and clearPart write the bytes of the pattern in RAM and nothing else", () => {
  const device = loaded(`korg.onEvent("ready", () => {
    korg.seq.setStep(2, 5, 60, 100);
    korg.seq.setGate(2, 5, 127);
    korg.seq.setStep(2, 6, 61, 90);
    korg.seq.setStep(2, 6, -1, 90);
    korg.seq.setStep(2, 7, 62, 80);
    korg.seq.setStep(2, 7, 62, 0);
    korg.seq.setStep(15, 63, 127, 1);
    korg.seq.setStep(4, 0, 0, 127);
    korg.seq.clearPart(4);
  });`, d => {
    const block = d.hardware.patternBlock(-1);
    const at = d.hardware.stepAt(2, 5);
    block.set([0, 33, 0, 0, 9, 9, 9, 9, 7, 7, 7, 7], at);
  });
  const block = device.hardware.patternBlock(-1);
  const at = device.hardware.stepAt(2, 5);
  assert.deepEqual([...block.subarray(at, at + 12)], [1, 127, 100, 1, 61, 0, 0, 0, 7, 7, 7, 7], "the other note places cleared, the rest of the record kept");
  assert.deepEqual(device.hardware.stepValue(2, 6), { on: 0, gate: 0, velocity: 90, trigger: 1, note: 61 }, "note -1 turns only the step off");
  assert.deepEqual(device.hardware.stepValue(2, 7).on, 0, "velocity 0 turns it off as well");
  assert.deepEqual(device.hardware.stepValue(15, 63), { on: 1, gate: 0, velocity: 1, trigger: 1, note: 127 });
  assert.deepEqual(device.hardware.stepValue(4, 0), { on: 0, gate: 0, velocity: 127, trigger: 1, note: 0 }, "clearPart turns the steps off and leaves the notes");
  assert.equal(device.hardware.stepAt(2, 5), PATTERN_PARTS.base + 2 * PATTERN_PARTS.stride + PATTERN_STEPS.base + 5 * PATTERN_STEPS.stride);
});

test("values out of range end the plugin with an argument error", () => {
  for (const call of ["korg.seq.setStep(16, 0, 60, 100)", "korg.seq.setStep(0, 64, 60, 100)", "korg.seq.setStep(0, 0, 128, 100)",
    "korg.seq.setStep(0, 0, -2, 100)", "korg.seq.setStep(0, 0, 60, 128)", "korg.seq.setGate(0, 0, 128)", "korg.seq.clearPart(-1)"]) {
    const device = loaded(`let p = 0; korg.onEvent("ready", () => { ${call.replace("(", "(p + ")}; });`);
    assert.equal(device.status().scripts[0].fault?.code, ERROR.API_ARG, call);
  }
});

test("the arpeggio of the plugin docs compiles and writes the chord in the pattern's key over its length", () => {
  for (const doc of ["docs/plugins.md", "docs/plugins.en.md"]) {
    const text = readFileSync(new URL(`../${doc}`, import.meta.url), "utf8");
    const source = [...text.matchAll(/```js\n([\s\S]*?)```/g)].map(m => m[1]).find(code => code.includes("korg.seq.clearPart"));
    assert.ok(source, doc);
    const device = loaded(source, d => {
      const block = d.hardware.patternBlock(-1);
      block[37] = 1;                                            // two bars
      block[39] = 2;                                            // key D
    });
    device.hardware.part = 3;
    device.post("buttonPress", 3);
    device.frame();
    const on = Array.from({ length: 64 }, (_, step) => device.hardware.stepValue(3, step)).flatMap((v, step) => (v.on ? [[step, v.note, v.velocity, v.gate]] : []));
    assert.equal(on.length, 16, doc);
    assert.deepEqual(on.slice(0, 5), [[0, 50, 110, 40], [2, 54, 80, 40], [4, 57, 80, 40], [6, 62, 80, 40], [8, 50, 110, 40]], doc);
    assert.equal(on.at(-1)[0], 30, doc);
  }
});
