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

test("the step layout korg.seq reads and writes is the one of the device map", () => {
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
  assert.deepEqual(API_BY_NAME.get("korg.seq.setGate").args.map(a => [a.name, a.min, a.max]), [["part", 0, 15], ["step", 0, 63], ["gate", 0, 255]]);
  assert.equal(decodeBlob(build("korg.onEvent(\"step\", (s) => { korg.seq.setGate(0, s, 96); });")).header.apiVersion, 9);
  assert.equal(compile("korg.seq.clearPart(0);", { name: "seq" }).ok, false, "not in the body: the firmware has no pattern for it there yet");
});

test("step readers are API 13, read the active pattern, and decode its four note slots", () => {
  for (const [name, args] of [
    ["korg.seq.getOn", [["part", 0, 15], ["step", 0, 63]]],
    ["korg.seq.getGate", [["part", 0, 15], ["step", 0, 63]]],
    ["korg.seq.getVelocity", [["part", 0, 15], ["step", 0, 63]]],
    ["korg.seq.getNote", [["part", 0, 15], ["step", 0, 63], ["slot", 0, 3]]],
  ]) {
    const api = API_BY_NAME.get(name);
    assert.equal(api.since, 13, name);
    assert.ok(!api.events.includes("start") && !api.events.includes("save") && api.events.includes("step"), name);
    assert.deepEqual(api.args.map(a => [a.name, a.min, a.max]), args);
  }
  const device = loaded(`let on = 0, gate = 0, velocity = 0, note0 = 0, note1 = 0, note2 = 0, note3 = 0;
korg.onEvent("ready", () => {
  on = korg.seq.getOn(2, 5);
  gate = korg.seq.getGate(2, 5);
  velocity = korg.seq.getVelocity(2, 5);
  note0 = korg.seq.getNote(2, 5, 0);
  note1 = korg.seq.getNote(2, 5, 1);
  note2 = korg.seq.getNote(2, 5, 2);
  note3 = korg.seq.getNote(2, 5, 3);
});`, d => {
    d.hardware.patternBlock(-1).set([0, 255, 0, 1, 61, 0, 9, 128], d.hardware.stepAt(2, 5));
  });
  assert.deepEqual(Array.from(device.runtime.scripts[0].script.vars.slice(0, 7)), [0, 255, 0, 60, -1, 8, 127]);
  assert.equal(decodeBlob(build(`korg.onEvent("step", (step) => {
    let active = korg.seq.getOn(0, step);
    let note = korg.seq.getNote(0, step, 0);
    let velocity = korg.seq.getVelocity(0, step);
    let gate = korg.seq.getGate(0, step);
  });`)).header.apiVersion, 13);
});

test("setStep and setGate preserve trigger bytes; clearPart changes only on bytes", () => {
  const device = loaded(`let gate0 = -1, gate63 = -1, gate96 = -1, gateTie = -1;
korg.onEvent("ready", () => {
    korg.seq.setStep(2, 5, 60, 100);
    korg.seq.setGate(2, 5, 0);
    gate0 = korg.seq.getGate(2, 5);
    korg.seq.setGate(2, 5, 63);
    gate63 = korg.seq.getGate(2, 5);
    korg.seq.setGate(2, 5, 96);
    gate96 = korg.seq.getGate(2, 5);
    korg.seq.setGate(2, 5, 255);
    gateTie = korg.seq.getGate(2, 5);
    korg.seq.setStep(2, 8, 63, 90);
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
    block.set([0, 255, 0, 1, 9, 9, 9, 9, 7, 7, 7, 7], at);
    block.set([0, 255, 0, 0], d.hardware.stepAt(2, 8));
    block[d.hardware.stepAt(2, 7) + PATTERN_STEPS.gate] = 255;
    block[d.hardware.stepAt(2, 9) + PATTERN_STEPS.trigger] = 1;
    block[d.hardware.stepAt(2, 6) + PATTERN_STEPS.trigger] = 1;
    block[d.hardware.stepAt(2, 6) + PATTERN_STEPS.gate] = 255;
    block.set([1, 0, 127, 1], d.hardware.stepAt(4, 0));
  });
  const block = device.hardware.patternBlock(-1);
  const at = device.hardware.stepAt(2, 5);
  assert.deepEqual(Array.from(device.runtime.scripts[0].script.vars.slice(0, 4)), [0, 63, 96, 255], "getGate returns each raw gate byte, including TIE");
  assert.deepEqual([...block.subarray(at, at + 12)], [1, 255, 100, 1, 61, 0, 0, 0, 7, 7, 7, 7], "setStep preserves the trigger byte");
  assert.deepEqual(device.hardware.stepValue(2, 6), { on: 0, gate: 255, velocity: 90, trigger: 1, note: 61 }, "turning a step off preserves gate and trigger");
  assert.deepEqual(device.hardware.stepValue(2, 7).on, 0, "velocity 0 turns it off as well");
  assert.deepEqual(device.hardware.stepValue(2, 8), { on: 1, gate: 255, velocity: 90, trigger: 0, note: 63 }, "setStep preserves the trigger and gate bytes");
  assert.equal(device.hardware.stepValue(2, 9).trigger, 1, "setStep only updates its own trigger");
  assert.deepEqual(device.hardware.stepValue(15, 63), { on: 1, gate: 0, velocity: 1, trigger: 0, note: 127 });
  assert.deepEqual(device.hardware.stepValue(4, 0), { on: 0, gate: 0, velocity: 127, trigger: 1, note: 0 }, "clearPart turns the steps off and leaves the notes");
  assert.equal(device.hardware.stepAt(2, 5), PATTERN_PARTS.base + 2 * PATTERN_PARTS.stride + PATTERN_STEPS.base + 5 * PATTERN_STEPS.stride);
});

test("setStep and setGate preserve trigger at the pattern wrap", () => {
  for (const [bars, lastStep] of [[1, 15], [2, 31], [4, 63]]) {
    const device = loaded(`korg.onEvent("ready", () => {
      korg.seq.setGate(0, ${lastStep}, 96);
      korg.seq.setStep(0, 0, 60, 100);
    });`, d => {
      const block = d.hardware.patternBlock(-1);
      block[37] = bars - 1;
      block[d.hardware.stepAt(0, lastStep) + PATTERN_STEPS.gate] = 0;
      block[d.hardware.stepAt(0, 0) + PATTERN_STEPS.trigger] = 1;
    });
    assert.equal(device.hardware.stepValue(0, lastStep).gate, 96, `${bars} bar gate`);
    assert.equal(device.hardware.stepValue(0, 0).trigger, 1, `${bars} bar wrapped trigger remains unchanged`);
  }
});

test("setGate accepts only 0 to 96 or 255 and other values end the plugin with an argument error", () => {
  for (const call of ["korg.seq.setStep(16, 0, 60, 100)", "korg.seq.setStep(0, 64, 60, 100)", "korg.seq.setStep(0, 0, 128, 100)",
    "korg.seq.setStep(0, 0, -2, 100)", "korg.seq.setStep(0, 0, 60, 128)", "korg.seq.setGate(0, 0, 97)", "korg.seq.setGate(0, 0, 127)",
    "korg.seq.setGate(0, 0, 254)", "korg.seq.setGate(0, 0, 256)", "korg.seq.clearPart(-1)",
    "korg.seq.getOn(16, 0)", "korg.seq.getGate(0, 64)", "korg.seq.getVelocity(0, 64)", "korg.seq.getNote(0, 0, 4)"]) {
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
