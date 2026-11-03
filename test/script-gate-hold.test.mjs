import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

const key = name => KEY_NAMES.find(k => k.name === name).value;
const GATE_ARP = 11;

/** Gate Hold on the simulated device, running in the background, the pattern in RAM on rhythm `rhythm`. */
function plugin(rhythm = 7) {
  const result = compile(PRESETS.find(p => p.id === "gatehold").source, { name: "gatehold" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice();
  assert.ok(device.load(result.blob).ok);
  assert.equal(device.apps.length, 0, "no app, a background plugin");
  const hw = device.hardware;
  hw.setPatternValue(GATE_ARP, rhythm);
  device.run(2);
  const press = name => { device.post("buttonPress", key(name)); device.run(1); };
  const release = name => { device.post("buttonRelease", key(name)); device.run(1); };
  const down = () => press("TOUCHPAD");
  const up = () => release("TOUCHPAD");
  const move = (x, y = 500) => { device.post("touch", x, y); device.run(1); };
  const rhythmNow = () => hw.patternValue(-1, -1, GATE_ARP);
  return { device, hw, press, release, down, up, move, rhythmNow };
}

test("Gate Hold: in Gate Arp mode the first touch fixes the note and X then picks the rhythm", () => {
  const p = plugin();
  p.press("GATE_ARP");
  p.down();
  p.move(300);
  assert.equal(p.hw.touchLock, 300 >> 3, "the X of the first touch stays the firmware's");
  assert.equal(p.rhythmNow(), 7, "the first touch plays the note, the rhythm stays");
  p.move(0);
  assert.equal(p.rhythmNow(), 0, "far left: the first rhythm");
  p.move(1023);
  assert.equal(p.rhythmNow(), 49, "far right: the last rhythm");
  p.move(512);
  assert.equal(p.rhythmNow(), 25);
  assert.equal(p.hw.touchLock, 300 >> 3, "the note does not move with the finger");
  p.up();
  assert.equal(p.rhythmNow(), 7, "let go: the pattern's rhythm comes back");
  assert.equal(p.hw.touchLock, -1, "and X is the finger's again");
  assert.deepEqual(p.device.status().scripts.map(s => s.fault ?? null), [null]);
});

test("Gate Hold: a touch without moving leaves the rhythm alone", () => {
  const p = plugin(12);
  p.press("GATE_ARP");
  p.down();
  p.move(800);
  p.up();
  assert.equal(p.rhythmNow(), 12);
  assert.equal(p.hw.touchLock, -1);
});

test("Gate Hold: Master FX and Touch Scale mode leave the touchpad to the firmware", () => {
  const p = plugin();
  p.down();
  p.move(300);
  p.move(900);
  p.up();
  assert.equal(p.hw.touchLock, -1, "Master FX at the start: nothing held");
  assert.equal(p.rhythmNow(), 7);
  for (const mode of ["MASTER_FX", "TOUCH_SCALE"]) {
    p.press("GATE_ARP");
    p.press(mode);
    p.down();
    p.move(300);
    p.move(900);
    assert.equal(p.hw.touchLock, -1, `${mode} ends Gate Arp mode`);
    assert.equal(p.rhythmNow(), 7);
    p.up();
  }
  p.press("SHIFT");
  p.press("TOUCH_SCALE");
  p.release("SHIFT");
  p.down();
  p.move(300);
  assert.equal(p.hw.touchLock, -1, "SHIFT + TOUCH SCALE is Touch Scale mode");
  p.up();
});

test("Gate Hold: SHIFT + GATE ARP and SHIFT + MASTER FX keep the mode they find", () => {
  const p = plugin();
  p.press("SHIFT");
  p.press("GATE_ARP");
  p.release("SHIFT");
  p.down();
  p.move(300);
  assert.equal(p.hw.touchLock, -1, "SHIFT + GATE ARP opens the menu page, the mode stays Master FX");
  p.up();
  p.press("GATE_ARP");
  p.press("SHIFT");
  p.press("MASTER_FX");
  p.release("SHIFT");
  p.down();
  p.move(300);
  assert.equal(p.hw.touchLock, 300 >> 3, "SHIFT + MASTER FX keeps Gate Arp mode");
  p.up();
});

test("Gate Hold: leaving Gate Arp mode with the finger down lets go at once", () => {
  const p = plugin();
  p.press("GATE_ARP");
  p.down();
  p.move(300);
  p.move(900);
  assert.notEqual(p.rhythmNow(), 7);
  p.press("MASTER_FX");
  assert.equal(p.rhythmNow(), 7);
  assert.equal(p.hw.touchLock, -1);
  p.up();
});

test("Gate Hold: a new pattern while the finger is down brings back that pattern's rhythm on release", () => {
  const p = plugin();
  p.press("GATE_ARP");
  p.down();
  p.move(300);
  p.move(900);
  p.hw.setPatternValue(GATE_ARP, 20);
  p.device.post("patternChange", 3);
  p.device.run(1);
  p.move(100);
  assert.equal(p.rhythmNow(), (100 * 50) >> 10);
  p.up();
  assert.equal(p.rhythmNow(), 20);
});

test("Gate Hold: GATE HOLD 0 in the BLECH menu turns it off and keeps that", () => {
  const p = plugin();
  const page = p.device.menus.find(m => m.label === "GATE HOLD");
  assert.ok(page, "the plugin adds its page to the BLECH menu");
  assert.equal(page.value, 1, "on by default");
  p.press("GATE_ARP");
  p.device.menuSet(page.id, 0);
  p.device.run(1);
  p.down();
  p.move(300);
  p.move(900);
  assert.equal(p.hw.touchLock, -1);
  assert.equal(p.rhythmNow(), 7);
  p.up();
});
