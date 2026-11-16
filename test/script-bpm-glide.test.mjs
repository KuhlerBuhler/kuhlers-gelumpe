import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

const key = name => KEY_NAMES.find(k => k.name === name).value;

/** BPM Glide on the simulated device: the pattern in RAM has `length` steps, chains to pattern 5 and plays `repeat` times. */
function glide({ length = 16, repeat = 1, from = 1200, to = 1400, chain = 5, confirmed = 1000 } = {}) {
  const result = compile(PRESETS.find(p => p.id === "bpmglide").source, { name: "bpmglide" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice();
  assert.ok(device.load(result.blob).ok);
  const hw = device.hardware;
  hw.tempo = from;
  const live = hw.patternBlock(-1);
  live[37] = length / 16 - 1;
  live[15104] = chain + 1;
  live[15106] = repeat;
  new DataView(hw.patternBlock(0).buffer).setUint16(34, from, true);
  new DataView(hw.patternBlock(5).buffer).setUint16(34, to, true);
  new DataView(hw.patternBlock(7).buffer).setUint16(34, confirmed, true);
  device.run(2);
  return { device, hw };
}

/** Plays until part 1's step counter has moved `steps` times, and keeps the tempo seen at each step. */
function play(device, hw, steps) {
  const seen = [];
  let moves = 0;
  let last = hw.steps[0];
  if (hw.transport !== 1) device.post("buttonPress", key("PLAY"));
  while (moves < steps) {
    device.run(1);
    if (hw.steps[0] !== last) { moves += 1; last = hw.steps[0]; seen.push(hw.tempo); }
  }
  device.run(1);
  return seen;
}

test("the tempo glides to the next pattern's over the pattern's length and lands on it at the last step", () => {
  const { device, hw } = glide({ length: 16 });
  const seen = play(device, hw, 15);
  for (let i = 1; i < seen.length; i++) assert.ok(seen[i] >= seen[i - 1], `the tempo never falls back: ${seen}`);
  assert.ok(seen.at(-1) > 1300, `close to the target near the end: ${seen}`);
  assert.equal(hw.tempo, 1400, "the last step of the pattern is the new tempo");
  assert.deepEqual(device.status().scripts.map(s => s.fault ?? null), [null]);
});

test("Chain Repeat stretches the glide over every repetition", () => {
  const { device, hw } = glide({ length: 16, repeat: 2 });
  play(device, hw, 15);
  assert.ok(hw.tempo > 1250 && hw.tempo < 1350, `halfway after the first pass: ${hw.tempo}`);
  play(device, hw, 16);
  assert.equal(hw.tempo, 1400);
});

test("it glides down as well, and STOP gives the pattern its own tempo back", () => {
  const { device, hw } = glide({ length: 32, from: 1600, to: 1200 });
  play(device, hw, 16);
  assert.ok(hw.tempo < 1600 && hw.tempo > 1200, `on the way down: ${hw.tempo}`);
  device.post("buttonPress", key("STOP"));
  device.run(2);
  assert.equal(hw.tempo, 1600);
});

test("without a chain, with CHAIN MODE off, or switched off in the BLECH menu, the tempo is left alone", () => {
  const free = glide({ chain: -1 });
  play(free.device, free.hw, 15);
  assert.equal(free.hw.tempo, 1200);

  const noMode = glide();
  noMode.hw.chainMode = 0;
  play(noMode.device, noMode.hw, 15);
  assert.equal(noMode.hw.tempo, 1200);

  const off = glide();
  const page = off.device.menus.find(m => m.label === "GLIDE CHAIN");
  assert.ok(page, "the plugin adds its page to the BLECH menu");
  assert.equal(page.value, 1, "on until switched off");
  off.device.menuSet(page.id, 0);
  off.device.run(2);
  play(off.device, off.hw, 15);
  assert.equal(off.hw.tempo, 1200);
});

/** Plays until part 1's step counter shows `step`, and keeps the tempo seen at each step on the way. */
function playTo(device, hw, step) {
  const seen = [];
  let last = hw.steps[0];
  if (hw.transport !== 1) device.post("buttonPress", key("PLAY"));
  for (let frames = 0; frames < 2000; frames++) {
    device.run(1);
    if (hw.steps[0] !== last) { last = hw.steps[0]; seen.push(hw.tempo); if (last === step) return seen; }
  }
  throw new Error(`step ${step} never came`);
}

/** The firmware's switch at the sequence end: the confirmation is used up and the confirmed pattern loads. */
function switchTo(device, hw, pattern) {
  hw.next = -1;
  playTo(device, hw, 0);
  hw.api()["korg.pattern"](pattern);
  device.run(2);
}

test("both pages are in the BLECH menu and on by default", () => {
  const { device } = glide();
  const pages = device.menus.map(m => [m.label, m.value]);
  assert.deepEqual(pages, [["GLIDE CHAIN", 1], ["GLIDE SWITCH", 1]]);
  for (const [label] of pages) assert.ok(label.length <= 15, `${label} fits the menu`);
});

test("a switch confirmed at step 0 glides over the whole pattern and lands at the sequence end", () => {
  const { device, hw } = glide({ chain: -1, confirmed: 1400 });
  playTo(device, hw, 15);
  hw.next = 7;
  const seen = playTo(device, hw, 15);
  assert.equal(seen.length, 16);
  for (let i = 1; i < seen.length; i++) assert.ok(seen[i] > seen[i - 1], `rises at every step: ${seen}`);
  assert.equal(seen[0], 1200 + 200 / 16 | 0, "the first step already moves");
  assert.equal(seen[7], 1300, "half way at the half");
  assert.equal(hw.tempo, 1400, "the last step reaches the confirmed pattern's tempo");
  switchTo(device, hw, 7);
  assert.equal(hw.tempo, 1400, "no jump at the switch");
  playTo(device, hw, 8);
  assert.equal(hw.tempo, 1400, "the new pattern keeps its tempo");
  assert.deepEqual(device.status().scripts.map(s => s.fault ?? null), [null]);
});

test("a switch confirmed at the half glides over the other half", () => {
  const { device, hw } = glide({ chain: -1, from: 1600, confirmed: 1200 });
  playTo(device, hw, 7);
  assert.equal(hw.tempo, 1600, "nothing moves before the confirmation");
  hw.next = 7;
  const seen = playTo(device, hw, 15);
  assert.equal(seen.length, 8);
  assert.equal(seen[0], 1550, "one eighth of the way at step 8, the first after the confirmation");
  assert.equal(seen[3], 1400, "half of the way at step 11");
  assert.equal(hw.tempo, 1200);
});

test("a confirmed switch wins over the chain and EXIT gives the glide back to the chain", () => {
  const { device, hw } = glide({ length: 32, confirmed: 1000 });
  playTo(device, hw, 7);
  const chained = hw.tempo;
  assert.ok(chained > 1200 && chained < 1400, `the chain glides up: ${chained}`);
  hw.next = 7;
  playTo(device, hw, 15);
  assert.ok(hw.tempo < chained, `now it goes down to the confirmed pattern: ${hw.tempo}`);
  hw.next = -1;
  playTo(device, hw, 16);
  assert.equal(hw.tempo, 1200 + 200 * 17 / 32 | 0, "the chain glides on where it is");
  playTo(device, hw, 31);
  assert.equal(hw.tempo, 1400);
});

test("EXIT without a chain sets the tempo back, a new confirmation starts again from the tempo then", () => {
  const { device, hw } = glide({ chain: -1, confirmed: 1400 });
  playTo(device, hw, 3);
  hw.next = 7;
  playTo(device, hw, 9);
  assert.ok(hw.tempo > 1200);
  hw.next = -1;
  playTo(device, hw, 10);
  assert.equal(hw.tempo, 1200, "back where it was before the confirmation");
  new DataView(hw.patternBlock(8).buffer).setUint16(34, 1000, true);
  hw.next = 8;
  playTo(device, hw, 15);
  assert.equal(hw.tempo, 1000, "the other confirmed pattern's tempo at the last step");
});

test("STOP with a confirmed pattern leaves its tempo, with GLIDE SWITCH off a confirmation changes nothing", () => {
  const { device, hw } = glide({ chain: -1, confirmed: 1400 });
  playTo(device, hw, 3);
  hw.next = 7;
  playTo(device, hw, 8);
  device.post("buttonPress", key("STOP"));
  device.run(2);
  assert.equal(hw.tempo, 1400, "the firmware applies the confirmed pattern at STOP, with its tempo");

  const off = glide({ chain: -1, confirmed: 1400 });
  const page = off.device.menus.find(m => m.label === "GLIDE SWITCH");
  off.device.menuSet(page.id, 0);
  off.device.run(2);
  playTo(off.device, off.hw, 3);
  off.hw.next = 7;
  playTo(off.device, off.hw, 15);
  assert.equal(off.hw.tempo, 1200);
});

test("with both pages off the tempo is left alone", () => {
  const { device, hw } = glide({ confirmed: 1000 });
  for (const label of ["GLIDE CHAIN", "GLIDE SWITCH"]) device.menuSet(device.menus.find(m => m.label === label).id, 0);
  device.run(2);
  playTo(device, hw, 3);
  hw.next = 7;
  playTo(device, hw, 15);
  assert.equal(hw.tempo, 1200);
});
