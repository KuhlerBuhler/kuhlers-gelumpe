import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

const key = name => KEY_NAMES.find(k => k.name === name).value;

/** Momentary Mute in the background. The simulator has no pad modes, tools/emu/plugin_catalog15_cases.py checks those. */
function plugin() {
  const result = compile(PRESETS.find(p => p.id === "momentmute").source, { name: "momentmute" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice();
  assert.ok(device.load(result.blob).ok);
  assert.equal(device.apps.length, 0, "no app, a background plugin");
  device.run(2);
  const hw = device.hardware;
  const press = name => { device.post("buttonPress", key(name)); device.run(1); };
  const release = name => { device.post("buttonRelease", key(name)); device.run(1); };
  const pad = (index, down) => { device.post("pad", index, down, down ? 100 : 0); device.run(1); };
  const tap = name => { press(name); release(name); };
  return { device, hw, press, release, pad, tap };
}

test("Momentary Mute: PART MUTE and the pads stay the firmware's, the release of PART MUTE presses TRIGGER", () => {
  const p = plugin();
  assert.equal(p.hw.keyHold[key("PART_MUTE")], 0, "PART MUTE reaches the firmware");
  p.press("PART_MUTE");
  assert.equal(p.hw.padHold, 0, "held: the pads reach the firmware, which mutes in its PART MUTE mode");
  p.pad(3, 1);
  p.pad(3, 0);
  p.device.run(10);
  assert.deepEqual(p.hw.pressedKeys, [], "nothing pressed while PART MUTE is down");
  p.release("PART_MUTE");
  assert.deepEqual(p.hw.pressedKeys, [key("TRIGGER")], "released: back to TRIGGER mode");
  assert.equal(p.hw.padHold, 0);
  p.tap("PART_MUTE");
  assert.deepEqual(p.hw.pressedKeys, [key("TRIGGER"), key("TRIGGER")], "a short tap ends in TRIGGER as well");
  assert.deepEqual(p.device.status().scripts.map(s => s.fault ?? null), [null]);
});

test("Momentary Mute: other keys and pads alone press nothing", () => {
  const p = plugin();
  for (const name of ["TAP", "PART_LEFT", "MENU", "BAR_1", "TRIGGER", "SEQUENCER", "KEYBOARD"]) p.tap(name);
  p.pad(1, 1);
  p.pad(1, 0);
  assert.deepEqual(p.hw.pressedKeys, []);
});

test("Momentary Mute: SHIFT + PART MUTE stays the firmware's", () => {
  const p = plugin();
  p.press("SHIFT");
  p.tap("PART_MUTE");
  p.release("SHIFT");
  assert.deepEqual(p.hw.pressedKeys, [], "SHIFT down at the press: no TRIGGER on release");
  p.press("PART_MUTE");
  p.press("SHIFT");
  p.release("SHIFT");
  p.release("PART_MUTE");
  assert.deepEqual(p.hw.pressedKeys, [key("TRIGGER")], "SHIFT after the press does not change the release");
});

test("Momentary Mute: a mode key pressed while PART MUTE is held keeps its mode", () => {
  const p = plugin();
  for (const mode of ["SEQUENCER", "TRIGGER", "KEYBOARD", "CHORD", "STEP_JUMP", "PATTERN_SET", "PART_ERASE"]) {
    p.press("PART_MUTE");
    p.tap(mode);
    p.release("PART_MUTE");
    assert.deepEqual(p.hw.pressedKeys, [], `${mode} chosen while held: no TRIGGER`);
  }
});

test("Momentary Mute: MOMENT MUTE 0 in the BLECH menu turns it off and keeps that", () => {
  const p = plugin();
  const page = p.device.menus.find(m => m.label === "MOMENT MUTE");
  assert.ok(page, "the plugin adds its page to the BLECH menu");
  assert.equal(page.value, 1, "on by default");
  p.device.menuSet(page.id, 0);
  p.device.run(1);
  p.tap("PART_MUTE");
  assert.deepEqual(p.hw.pressedKeys, [], "off: PART MUTE stays a mode as without the plugin");
  p.press("PART_MUTE");
  p.device.menuSet(page.id, 1);
  p.device.run(1);
  p.release("PART_MUTE");
  assert.deepEqual(p.hw.pressedKeys, [], "switched on while held: the press it did not see changes nothing");
  p.tap("PART_MUTE");
  assert.deepEqual(p.hw.pressedKeys, [key("TRIGGER")]);
  p.press("PART_MUTE");
  p.device.menuSet(page.id, 0);
  p.device.run(1);
  p.release("PART_MUTE");
  assert.deepEqual(p.hw.pressedKeys, [key("TRIGGER")], "switched off while held: no TRIGGER");
});
