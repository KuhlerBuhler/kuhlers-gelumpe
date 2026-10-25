import { test } from "node:test";
import assert from "node:assert/strict";
import { compile, formatError } from "../src/script/compiler.mjs";
import { API_BY_NAME } from "../data/script/contract.mjs";
import { PROPERTIES, KNOB_NAMES } from "../data/script/properties.mjs";
import { KNOBS } from "../data/panel.mjs";

const blob = src => {
  const r = compile(`function f() {\n${src}\n}\nkorg.onEvent("step", f);`);
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  return Buffer.from(r.blob).toString("hex");
};

const error = src => {
  const r = compile(`function f() {\n${src}\n}\nkorg.onEvent("step", f);`);
  assert.equal(r.ok, false, `compiled but should not have: ${src}`);
  return r.errors[0].message;
};

// Each pair is one line, so the line table of both blocks is the same.
const SAME = [
  ["let t = korg.tempo;", "let t = korg.read.tempo();"],
  ["korg.tempo = 1280;", "korg.tempo(1280);"],
  ["korg.tempo += 10;", "korg.tempo(korg.read.tempo() + 10);"],
  ["korg.tempo++;", "korg.tempo(korg.read.tempo() + 1);"],
  ["let t = korg.transport;", "let t = korg.read.transport();"],
  ["korg.selectedPattern = korg.selectedPattern + 1;", "korg.pattern(korg.read.pattern() + 1);"],
  ["korg.selectedPart = 3;", "korg.part(3);"],
  ["let t = korg.selectedPart;", "let t = korg.read.part();"],
  ["let t = korg.millis;", "let t = korg.millis();"],
  ["let t = korg.parts[2].step;", "let t = korg.read.step(2);"],
  ["let t = korg.parts[2].muted;", "let t = korg.read.mute(2);"],
  ["korg.parts[5].muted = 1;", "korg.mute(5, 1);"],
  ["let t = korg.knobs.LEVEL + korg.knobs[3];", "let t = korg.read.knob(0) + korg.read.knob(3);"],
  ["korg.store[2] = 7;", "korg.store.set(2, 7);"],
  ["let t = korg.store[2];", "let t = korg.store.get(2, 0);"],
  ["korg.store[2] += 1;", "korg.store.set(2, korg.store.get(2, 0) + 1);"],
  ["korg.led.TAP = 255;", "korg.led(korg.led.TAP, 255);"],
  ["korg.leds[4] = 9;", "korg.led(4, 9);"],
];

test("a property compiles to the same block as the call it stands for", () => {
  for (const [property, call] of SAME) assert.equal(blob(property), blob(call), property);
});

test("every property names API entries that exist, and the knob names follow the panel table", () => {
  for (const p of PROPERTIES) {
    for (const side of [p.read, p.write].filter(Boolean)) {
      const api = API_BY_NAME.get(side[0]);
      assert.ok(api, `${p.path}: ${side[0]}`);
      assert.equal(side[1].length, api.args.length, `${p.path}: ${side[0]} takes ${api.args.length} arguments`);
    }
    assert.ok(p.text, p.path);
  }
  assert.deepEqual(KNOB_NAMES.map(k => k.value), KNOBS.map(k => k.index));
  assert.equal(KNOB_NAMES.find(k => k.name === "MOD_DEPTH").value, 5);
});

test("what a property cannot do is said in words", () => {
  assert.match(error("korg.transport = 1;"), /lässt sich nur lesen/);
  assert.match(error("let t = korg.leds[1];"), /lässt sich nur setzen/);
  assert.match(error("let t = korg.parts[1];"), /ist ein Objekt.*korg\.parts\[i\]\.step, korg\.parts\[i\]\.muted, korg\.parts\[i\]\.sample/);
  assert.match(error("let t = korg.parts[1].volume;"), /gibt es nicht\. Es gibt: \.step, \.muted, \.sample/);
  assert.match(error("let t = korg.knobs.CUTOFF;"), /keinen Regler.*LEVEL/);
  assert.match(error("korg.parts[korg.read.part()].muted += 1;"), /Index keinen Funktionsaufruf/);
  assert.match(error("korg.millis = 3;"), /lässt sich nur lesen/);
  assert.match(error("korg.foo = 3;"), /lässt sich nicht setzen/);
});

test("a setter keeps the events of its call: korg.tempo = … in the body is refused like korg.tempo(…)", () => {
  const r = compile("korg.tempo = 1200;");
  assert.equal(r.ok, false);
  assert.equal(compile("korg.tempo(1200);").ok, false);
  assert.equal(r.errors[0].message, compile("korg.tempo(1200);").errors[0].message);
});

test("the values of a pattern have names: the pattern that plays, every stored pattern and the parts", async () => {
  for (const [named, call] of [
    ["let t = korg.current.tempo;", "let t = korg.read.patternValue(-1, -1, 0);"],
    ["let t = korg.patterns[7].swing;", "let t = korg.read.patternValue(7, -1, 1);"],
    ["let t = korg.parts[2].cutoff;", "let t = korg.read.patternValue(-1, 2, 2);"],
    ["let t = korg.chainMode;", "let t = korg.read.chainMode();"],
  ]) assert.equal(blob(named), blob(call), named);
  assert.match(error("korg.current.tempo = 1200;"), /nur lesen/);
  assert.match(error("let t = korg.patterns[1].nope;"), /gibt es nicht/);

  const { SimDevice } = await import("../src/script/sim.mjs");
  const r = compile(`let tempo = 0; let swing = 0; let bars = 0; let pan = 0; let next = 0;
korg.onEvent("ready", () => {
  tempo = korg.patterns[3].tempo; swing = korg.current.swing; bars = korg.current.length; pan = korg.parts[15].pan; next = korg.current.chainTo;
});`);
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  const device = new SimDevice();
  new DataView(device.hardware.patternBlock(3).buffer).setUint16(34, 1755, true);
  const live = device.hardware.patternBlock(-1);
  live[36] = 0xF6; live[37] = 2; live[0x800 + 15 * 0x330 + 25] = 0xC1;
  const loaded = device.load(r.blob);
  device.run(2);
  const v = name => loaded.script.vars[r.info.symbols[name].slot];
  assert.deepEqual([v("tempo"), v("swing"), v("bars"), v("pan"), v("next")], [1755, -10, 3, -63, -1]);
});
