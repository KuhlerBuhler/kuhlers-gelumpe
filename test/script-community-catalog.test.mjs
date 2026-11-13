import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { PART_FIELDS } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

// EUCLID FLOW, LIVE RELOAD, RANDOM SLOT, Better Accent, Easy Slides and Pad Finger came in from the BLECH Discord; these tests
// hold what the catalog takes them for.
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
  assert.deepEqual(Uint8Array.from(p.device.hardware.patternBlock(-1)), before, "TAP with the app closed belongs to TAP Motion, not a new rhythm");
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

/** Steps 0 to 15 of a part on, with the velocity and gate a step function gives. */
function fill(api, part, velocity, gate) {
  for (let s = 0; s < 16; s++) {
    api["korg.seq.setStep"](part, s, 60, velocity(s));
    api["korg.seq.setGate"](part, s, gate(s));
  }
}

test("Better Accent plays steps above velocity 96 with the accent values of parts 1 to 7 and STOP puts the normal ones back", () => {
  const p = plugin("betteraccent");
  for (const part of [0, 7]) fill(p.api, part, s => (s === 8 ? 120 : 90), () => 60);
  p.run(2);
  assert.equal(p.device.apps.length, 0, "a background plugin");
  p.device.post("buttonPress", key("SHIFT"));
  p.device.post("knob", 4, 200);
  p.run(1);
  p.device.post("buttonRelease", key("SHIFT"));
  p.run(1);
  const egInt = part => p.api["korg.read.patternValue"](-1, part, field("egInt"));
  assert.equal(egInt(0), 0, "SHIFT holds the knob from the firmware");
  p.press("PLAY");
  const seen = { 0: new Set(), 7: new Set() };
  for (let i = 0; i < 300; i++) { p.run(1); seen[0].add(egInt(0)); seen[7].add(egInt(7)); }
  assert.deepEqual([...seen[0]].sort((a, b) => a - b), [0, 36], "the accent step opens EG INT, the others stay normal");
  assert.deepEqual([...seen[7]], [0], "part 8 is beyond maxParts = 7");
  p.press("STOP");
  assert.equal(egInt(0), 0);
  assert.deepEqual(p.faults, []);
});

test("Easy Slides glides TIE steps of parts 1 to 8, leaves the glide of parts 9 to 16 alone and STOP puts it back", () => {
  const p = plugin("easyslides");
  for (let part = 0; part < 16; part++) {
    p.api["korg.seq.setPartValue"](part, field("glide"), 40);
    fill(p.api, part, () => 90, s => (s === 4 ? 127 : 60));
  }
  p.run(2);
  assert.equal(p.device.apps.length, 0, "a background plugin");
  const glide = part => p.api["korg.read.patternValue"](-1, part, field("glide"));
  p.press("PLAY");
  const seen = Array.from({ length: 16 }, () => new Set());
  for (let i = 0; i < 300; i++) { p.run(1); for (let part = 0; part < 16; part++) seen[part].add(glide(part)); }
  for (let part = 0; part < 8; part++) assert.deepEqual([...seen[part]].sort((a, b) => a - b), [40, 75], `part ${part + 1}`);
  for (let part = 8; part < 16; part++) assert.deepEqual([...seen[part]], [40], `part ${part + 1} keeps its glide`);
  p.press("STOP");
  assert.deepEqual(Array.from({ length: 16 }, (_, part) => glide(part)), Array(16).fill(40));
  assert.deepEqual(p.faults, []);
});

test("Pad Finger shows the touch, holds the firmware's X with LOCK and lets go on lift, with FREE and on EXIT", () => {
  const p = plugin("padfinger");
  assert.equal(p.device.apps.length, 1);
  assert.equal(p.device.apps[0].group, "TOOLS");
  const touch = (x, y) => { p.device.post("buttonPress", key("TOUCHPAD")); p.device.post("touch", x, y); p.run(2); };
  const lift = () => { p.device.post("buttonRelease", key("TOUCHPAD")); p.run(2); };
  touch(500, 500);
  assert.equal(p.device.hardware.touchLock, -1, "closed, the app leaves the touchpad alone");
  lift();
  assert.ok(p.device.openApp(0));
  p.run(2);
  assert.ok(p.device.display.bytes.some(b => b), "it draws when it opens");
  touch(800, 300);
  assert.equal(p.device.hardware.touchLock, 800 >> 3, "LOCK holds the X where the finger landed");
  p.device.post("touch", 100, 300);
  p.run(2);
  assert.equal(p.device.hardware.touchLock, 800 >> 3, "moving the finger keeps the held X");
  lift();
  assert.equal(p.device.hardware.touchLock, -1, "lifting lets go");
  touch(640, 300);
  assert.equal(p.device.hardware.touchLock, 640 >> 3);
  p.press("TAP");
  assert.equal(p.device.hardware.touchLock, -1, "FREE lets go");
  lift();
  touch(400, 300);
  assert.equal(p.device.hardware.touchLock, -1, "FREE holds nothing");
  lift();
  p.press("TAP");
  touch(256, 300);
  assert.equal(p.device.hardware.touchLock, 256 >> 3, "LOCK again");
  p.press("EXIT");
  assert.equal(p.device.hardware.touchLock, -1, "closing the app lets go");
  assert.deepEqual(p.faults, []);
});
