import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { PART_FIELDS } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

// EUCLID FLOW, LIVE RELOAD and RANDOM SLOT came in from the BLECH Discord; these tests hold what the catalog takes them for.
const key = name => KEY_NAMES.find(k => k.name === name).value;
const field = name => PART_FIELDS.findIndex(f => f.name === name);

function plugin(id) {
  const result = compile(PRESETS.find(p => p.id === id).source, { name: id });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice();
  assert.ok(device.load(result.blob).ok);
  const api = device.hardware.api();
  const faults = [];
  const run = frames => faults.push(...device.run(frames));
  const press = name => { device.post("buttonPress", key(name)); run(1); device.post("buttonRelease", key(name)); run(1); };
  return { device, api, faults, run, press };
}

test("the three community apps compile, sit under TOOLS and draw when they open", () => {
  for (const id of ["euclidflow", "livereload", "randomslot"]) {
    const p = plugin(id);
    assert.equal(p.device.apps.length, 1, id);
    assert.equal(p.device.apps[0].group, "TOOLS", id);
    assert.ok(p.device.openApp(0));
    p.run(20);
    assert.deepEqual(p.faults, [], id);
    assert.ok(p.device.display.bytes.some(b => b), `${id} draws`);
  }
});

test("EUCLID FLOW leaves the pattern alone while it is closed and writes 5 hits on 16 steps with TAP when open", () => {
  const p = plugin("euclidflow");
  p.run(5);
  const before = Uint8Array.from(p.device.hardware.patternBlock(-1));
  p.press("TAP");
  assert.deepEqual(Uint8Array.from(p.device.hardware.patternBlock(-1)), before, "TAP with the app closed is tap tempo, not a new rhythm");
  assert.ok(p.device.openApp(0));
  p.run(2);
  p.press("TAP");
  const on = Array.from({ length: 16 }, (_, s) => p.api["korg.seq.getOn"](0, s));
  assert.deepEqual(on, [0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1]);
  assert.deepEqual(p.faults, []);
});

test("LIVE RELOAD puts the saved part values back, SHIFT + 1 at once and SHIFT + 2 over a few frames", () => {
  for (const bar of ["BAR_1", "BAR_2"]) {
    const p = plugin("livereload");
    p.device.hardware.patternBlock(0);
    p.api["korg.seq.setPartValue"](3, field("cutoff"), 20);
    const saved = p.api["korg.read.patternValue"](0, 3, field("cutoff"));
    assert.notEqual(saved, 20);
    assert.ok(p.device.openApp(0));
    p.run(2);
    p.device.post("buttonPress", key("SHIFT"));
    p.press(bar);
    p.run(30);
    assert.equal(p.api["korg.read.patternValue"](-1, 3, field("cutoff")), saved, bar);
    assert.deepEqual(p.faults, [], bar);
  }
});

test("RANDOM SLOT solos the picked part with PART MUTE and brings the mutes back", () => {
  const p = plugin("randomslot");
  p.api["korg.mute"](7, 1);
  assert.ok(p.device.openApp(0));
  p.run(2);
  p.device.post("pad", 4, 1, 100);
  p.run(2);
  p.press("PART_MUTE");
  assert.deepEqual(Array.from({ length: 16 }, (_, i) => p.api["korg.read.mute"](i)), Array.from({ length: 16 }, (_, i) => (i === 4 ? 0 : 1)));
  p.press("PART_MUTE");
  assert.deepEqual(Array.from({ length: 16 }, (_, i) => p.api["korg.read.mute"](i)), Array.from({ length: 16 }, (_, i) => (i === 7 ? 1 : 0)));
  for (const bar of ["BAR_1", "BAR_2", "BAR_3", "BAR_4"]) {
    p.press(bar);
    p.run(30);
  }
  assert.deepEqual(p.faults, []);
});
