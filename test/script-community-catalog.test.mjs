import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { PART_FIELDS } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

// EUCLID FLOW, LIVE RELOAD, RANDOM SLOT, Better Accent, Easy Slides and Pad Finger came in from the BLECH Discord, Blechy Run is
// our own game; these tests hold what the catalog takes them for.
const key = name => KEY_NAMES.find(k => k.name === name).value;
const field = name => PART_FIELDS.findIndex(f => f.name === name);

function plugin(id, { storage = null } = {}) {
  const result = compile(PRESETS.find(p => p.id === id).source, { name: id });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice({ storage });
  const loaded = device.load(result.blob);
  assert.ok(loaded.ok);
  const api = device.hardware.api();
  const faults = [];
  const run = frames => faults.push(...device.run(frames));
  const press = name => { device.post("buttonPress", key(name)); run(1); device.post("buttonRelease", key(name)); run(1); };
  const v = (name, i = 0) => loaded.script.vars[result.info.symbols[name].slot + i];
  return { device, api, faults, run, press, v };
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

test("Blechy Run jumps, ends on a block with GAME OVER, keeps the best score and starts again", () => {
  const saved = [];
  const storage = { load: name => (name === "blechyrun" ? { mask: 1, values: [3] } : null), save: records => saved.push(records) };
  const p = plugin("blechyrun", { storage });
  const pixel = (x, y) => (p.device.display.bytes[(y >> 3) * 128 + x] >> (y & 7)) & 1;
  assert.equal(p.device.apps.length, 1);
  assert.equal(p.device.apps[0].group, "GAMES");
  assert.equal(p.v("best"), 3, "the best score comes from the card");
  p.device.post("pad", 0, 1, 90);
  p.run(2);
  assert.equal(p.v("state"), 0, "closed, a pad does not start a run");
  assert.ok(p.device.openApp(0));
  p.run(2);
  assert.equal(p.v("state"), 0, "it waits for the first jump");
  assert.equal(pixel(8 + 10, 60), 1, "the ground is drawn");
  p.press("TAP");
  assert.equal(p.v("state"), 1, "a key starts the run");
  assert.ok(p.v("height") > 0, "and he jumps");
  let peak = 0;
  for (let i = 0; i < 30; i++) { p.run(1); peak = Math.max(peak, p.v("height") >> 4); }
  assert.ok(peak >= 20 && 36 - peak >= 10, `at his highest (${peak} px) he stays below the score line`);
  assert.equal(p.v("height"), 0, "he lands again");
  const speed = p.v("speed");
  // no more jumps: the first block reaches him
  let frames = 0;
  while (p.v("state") == 1 && frames < 400) { p.run(1); frames++; }
  assert.equal(p.v("state"), 2, "a block ends the run");
  assert.ok(p.v("speed") > speed, "it got faster on the way");
  const score = p.v("score");
  assert.ok(score > 3, `score ${score}`);
  assert.equal(p.v("best"), score, "a new best");
  assert.equal(saved.at(-1)?.find(r => r.name === "blechyrun").values[0], score, "the best score goes to korg.store");
  assert.ok([...Array(54).keys()].some(x => pixel(37 + x, 18)), "GAME OVER is on the display");
  p.device.post("pad", 3, 1, 90);
  p.run(1);
  assert.equal(p.v("state"), 2, "a pad right after the hit does not start the next run yet");
  p.run(20);
  p.device.post("pad", 3, 1, 90);
  p.run(1);
  assert.equal(p.v("state"), 1, "after the pause a pad starts the next run");
  assert.equal(p.v("score"), 0);
  // a jump a few frames before the first block reaches him clears it
  const nearest = () => Math.min(...[0, 1, 2].map(i => (p.v("ow", i) ? p.v("ox", i) >> 4 : 999)));
  while (nearest() > 8 + 18 + 4 * (p.v("speed") >> 4)) p.run(1);
  p.press("TRIGGER");
  p.run(20);
  assert.equal(p.v("state"), 1, "he jumped over the block");
  assert.ok(nearest() > 26, "and it is behind him");
  p.press("EXIT");
  assert.ok(!p.device.runtime.open, "EXIT closes the app");
  assert.equal(p.v("state"), 0);
  // 0.5 ms, the warning line of a handler: the Snake frame took 0.103 ms for 542 units
  for (const [handler, units] of Object.entries(p.device.status().scripts[0].maxCost)) assert.ok(units <= Math.floor(542 * 0.5 / 0.103), `${handler} costs ${units}`);
  assert.deepEqual(p.faults, []);
});
