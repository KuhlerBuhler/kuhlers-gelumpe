import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

const key = name => KEY_NAMES.find(k => k.name === name).value;
const KEY = 4;

/** Key Pads on the simulated device, running in the background. */
function plugin() {
  const result = compile(PRESETS.find(p => p.id === "keypads").source, { name: "keypads" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice();
  assert.ok(device.load(result.blob).ok);
  assert.equal(device.apps.length, 0, "no app, a background plugin");
  device.run(2);
  const hw = device.hardware;
  const press = name => { device.post("buttonPress", key(name)); device.run(1); };
  const release = name => { device.post("buttonRelease", key(name)); device.run(1); };
  const pad = (index, down) => { device.post("pad", index, down, down ? 100 : 0); device.run(1); };
  const tap = index => { pad(index, 1); pad(index, 0); };
  const keyNow = () => hw.patternValue(-1, -1, KEY);
  return { device, hw, press, release, pad, tap, keyNow };
}

test("Key Pads: KEYBOARD held, a pad sets the KEY like a piano", () => {
  const p = plugin();
  assert.equal(p.hw.keyHold[key("KEYBOARD")], 1, "KEYBOARD is the plugin's");
  const lower = [0, 2, 4, 5, 7, 9, 11, 0];
  const upper = { 1: 1, 2: 3, 4: 6, 5: 8, 6: 10 };
  p.press("KEYBOARD");
  assert.equal(p.hw.padHold, 1, "the pads reach the plugin only while KEYBOARD is down");
  for (let i = 0; i < 8; i++) {
    p.tap(8 + i);
    assert.equal(p.keyNow(), lower[i], `pad ${9 + i}`);
  }
  for (const [i, k] of Object.entries(upper)) {
    p.tap(Number(i));
    assert.equal(p.keyNow(), k, `pad ${Number(i) + 1}`);
  }
  p.tap(14);
  for (const i of [0, 3, 7]) {
    p.tap(i);
    assert.equal(p.keyNow(), 11, `pad ${i + 1} has no black key`);
  }
  p.release("KEYBOARD");
  assert.equal(p.hw.padHold, 0, "released: the pads are the firmware's again");
  assert.deepEqual(p.hw.pressedKeys, [], "with a pad KEYBOARD does not switch the mode");
  assert.deepEqual(p.device.status().scripts.map(s => s.fault ?? null), [null]);
});

test("Key Pads: a short press of KEYBOARD alone goes on to the firmware on release", () => {
  const p = plugin();
  p.press("KEYBOARD");
  assert.deepEqual(p.hw.pressedKeys, []);
  p.release("KEYBOARD");
  assert.deepEqual(p.hw.pressedKeys, [key("KEYBOARD")]);
  p.tap(9);
  assert.equal(p.keyNow(), 0, "without KEYBOARD a pad does not touch the KEY");
});

test("Key Pads: SHIFT + KEYBOARD stays the firmware's", () => {
  const p = plugin();
  p.press("SHIFT");
  assert.equal(p.hw.keyHold[key("KEYBOARD")], 0);
  p.press("KEYBOARD");
  assert.equal(p.hw.padHold, 0);
  p.tap(9);
  p.release("KEYBOARD");
  p.release("SHIFT");
  assert.equal(p.keyNow(), 0);
  assert.deepEqual(p.hw.pressedKeys, []);
  assert.equal(p.hw.keyHold[key("KEYBOARD")], 1);
});

test("Key Pads: the pad hold comes back each frame after an app close cleared it", () => {
  const p = plugin();
  p.press("KEYBOARD");
  p.hw.padHold = 0;
  p.device.run(1);
  assert.equal(p.hw.padHold, 1);
  p.release("KEYBOARD");
  p.device.run(1);
  assert.equal(p.hw.padHold, 0);
});

test("Key Pads: KEY PADS 0 in the BLECH menu turns it off and keeps that", () => {
  const p = plugin();
  const page = p.device.menus.find(m => m.label === "KEY PADS");
  assert.ok(page, "the plugin adds its page to the BLECH menu");
  assert.equal(page.value, 1, "on by default");
  p.device.menuSet(page.id, 0);
  p.device.run(1);
  assert.equal(p.hw.keyHold[key("KEYBOARD")], 0, "off: KEYBOARD is the firmware's");
  p.press("KEYBOARD");
  p.tap(9);
  p.release("KEYBOARD");
  assert.equal(p.keyNow(), 0);
  assert.deepEqual(p.hw.pressedKeys, []);
  p.device.menuSet(page.id, 1);
  p.device.run(1);
  assert.equal(p.hw.keyHold[key("KEYBOARD")], 1);
});
