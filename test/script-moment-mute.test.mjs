import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

const key = name => KEY_NAMES.find(k => k.name === name).value;

/** Momentary Mute on the simulated device, running in the background. */
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
  const mutes = () => [...hw.mutes];
  return { device, hw, press, release, pad, mutes };
}

const muted = (...parts) => Array.from({ length: 16 }, (_, i) => (parts.includes(i) ? 1 : 0));

test("Momentary Mute: in PART MUTE mode a held pad mutes its part and the release brings it back", () => {
  const p = plugin();
  assert.equal(p.hw.padHold, 0, "the pads stay the firmware's until PART MUTE");
  p.press("PART_MUTE");
  assert.equal(p.hw.padHold, 1, "PART MUTE mode: the pads reach the plugin only");
  p.pad(3, 1);
  assert.deepEqual(p.mutes(), muted(3), "pad 4 held: part 4 is muted");
  p.device.run(10);
  assert.deepEqual(p.mutes(), muted(3), "still muted while held");
  p.pad(3, 0);
  assert.deepEqual(p.mutes(), muted(), "released: part 4 plays again");
  assert.deepEqual(p.device.status().scripts.map(s => s.fault ?? null), [null]);
});

test("Momentary Mute: two pads held at once mute both, each release brings back only its own part", () => {
  const p = plugin();
  p.press("PART_MUTE");
  p.pad(0, 1);
  p.pad(5, 1);
  assert.deepEqual(p.mutes(), muted(0, 5));
  p.pad(0, 0);
  assert.deepEqual(p.mutes(), muted(5), "pad 1 released, pad 6 still held");
  p.pad(5, 0);
  assert.deepEqual(p.mutes(), muted());
});

test("Momentary Mute: a part muted before plays while its pad is held and is muted again after", () => {
  const p = plugin();
  p.hw.mutes[2] = 1;
  p.press("PART_MUTE");
  p.pad(2, 1);
  assert.deepEqual(p.mutes(), muted(), "held: the muted part plays");
  p.pad(2, 0);
  assert.deepEqual(p.mutes(), muted(2), "released: muted as before");
});

test("Momentary Mute: other pad modes, SHIFT and other keys leave the pads to the firmware", () => {
  const p = plugin();
  p.pad(1, 1);
  p.pad(1, 0);
  assert.deepEqual(p.mutes(), muted(), "before PART MUTE a pad does not mute");
  p.press("PART_MUTE");
  for (const name of ["TAP", "PART_LEFT", "MENU", "BAR_1", "PART_MUTE"]) {
    p.press(name);
    p.release(name);
    assert.equal(p.hw.padHold, 1, `${name} keeps PART MUTE mode`);
  }
  p.press("SHIFT");
  assert.equal(p.hw.padHold, 0, "SHIFT held: SHIFT + pad goes to the firmware");
  p.pad(4, 1);
  p.pad(4, 0);
  assert.deepEqual(p.mutes(), muted(), "SHIFT + pad is not the plugin's");
  p.release("SHIFT");
  assert.equal(p.hw.padHold, 1);
  for (const mode of ["SEQUENCER", "TRIGGER", "KEYBOARD", "CHORD", "STEP_JUMP", "PATTERN_SET", "PART_ERASE"]) {
    p.press("PART_MUTE");
    p.press(mode);
    assert.equal(p.hw.padHold, 0, `${mode} ends PART MUTE mode`);
    p.pad(7, 1);
    p.pad(7, 0);
    assert.deepEqual(p.mutes(), muted(), `in ${mode} a pad does not mute`);
  }
});

test("Momentary Mute: a pad held when the mode ends still brings its part back on release", () => {
  const p = plugin();
  p.press("PART_MUTE");
  p.pad(9, 1);
  p.press("SEQUENCER");
  assert.deepEqual(p.mutes(), muted(9));
  p.pad(9, 0);
  assert.deepEqual(p.mutes(), muted());
});

test("Momentary Mute: the hold comes back each frame after an app close cleared it", () => {
  const p = plugin();
  p.press("PART_MUTE");
  p.hw.padHold = 0;
  p.device.run(1);
  assert.equal(p.hw.padHold, 1);
});

test("Momentary Mute: MOMENT MUTE 0 in the BLECH menu turns it off and keeps that", () => {
  const p = plugin();
  const page = p.device.menus.find(m => m.label === "MOMENT MUTE");
  assert.ok(page, "the plugin adds its page to the BLECH menu");
  assert.equal(page.value, 1, "on by default");
  p.press("PART_MUTE");
  p.device.menuSet(page.id, 0);
  p.device.run(1);
  assert.equal(p.hw.padHold, 0, "off: the pads latch in the firmware again");
  p.pad(3, 1);
  p.pad(3, 0);
  assert.deepEqual(p.mutes(), muted());
  p.device.menuSet(page.id, 1);
  p.device.run(1);
  assert.equal(p.hw.padHold, 1);
});
