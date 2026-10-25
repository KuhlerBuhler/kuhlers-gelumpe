import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

const key = name => KEY_NAMES.find(k => k.name === name).value;

/** BPM Glide on the simulated device: the pattern in RAM has `length` steps, chains to pattern 5 and plays `repeat` times. */
function glide({ length = 16, repeat = 1, from = 1200, to = 1400, chain = 5 } = {}) {
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
  const page = off.device.menus.find(m => m.label === "BPM GLIDE");
  assert.ok(page, "the plugin adds its page to the BLECH menu");
  assert.equal(page.value, 1, "on until switched off");
  off.device.menuSet(page.id, 0);
  off.device.run(2);
  play(off.device, off.hw, 15);
  assert.equal(off.hw.tempo, 1200);
});
