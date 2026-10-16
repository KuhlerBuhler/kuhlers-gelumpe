import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PRESETS } from "../data/script/presets.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice, probe, FRAME_MS } from "../src/script/sim.mjs";
import { Display, WIDTH, HEIGHT } from "../src/script/display.mjs";
import { Workspace, validName, sourceKey } from "../src/script/workspace.mjs";
import { exportGate } from "../src/script/gate.mjs";

const preset = id => PRESETS.find(p => p.id === id);
const build = (name, source) => {
  const result = compile(source, { name });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  return result.blob;
};
const blockOf = id => build(id, preset(id).source);
const fixture = name => readFileSync(new URL(`./fixtures/scripts/${name}`, import.meta.url), "utf8");
const klickerBlock = () => build("klicker", fixture("klicker.js"));

test("every preset compiles; the Snake fixture the other tests run still compiles on its own", () => {
  assert.ok(compile(fixture("snake.js"), { name: "snake" }).ok);
  for (const p of PRESETS) {
    assert.ok(validName(p.id), p.id);
    assert.ok(p.title && p.description);
    assert.ok(compile(p.source, { name: p.id }).ok, p.id);
  }
});

test("the display clips at its edges, never wraps, and has the layout of the device's display RAM", () => {
  const d = new Display();
  d.rect(126, 62, 10, 10);
  assert.equal(d.get(127, 63), 1);
  assert.equal(d.get(0, 0), 0);
  assert.equal(d.bytes.length, 1024);
  d.clear();
  d.pixel(3, 9, 1);
  assert.equal(d.bytes[1 * WIDTH + 3], 0b10, "page 1, bit 1 for row 9");
  d.pixel(-1, 0, 1); d.pixel(WIDTH, 0, 1); d.pixel(0, HEIGHT, 1); d.pixel(1.5, 0, 1);
  assert.equal(d.bytes.reduce((n, b) => n + (b ? 1 : 0), 0), 1);
  d.clear();
  d.text("MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM", 0, 0);
  assert.equal(d.rows().slice(8).every(row => !row.includes("#")), true, "text stays in its own rows");
  d.clear();
  d.text("AA", 124, 0);
  assert.equal(d.rows().every(row => row.length === WIDTH), true);
  assert.deepEqual([d.get(126, 4), d.get(127, 4)], [1, 1], "the letter is cut at the edge: its columns past 127 are gone");
  d.clear();
  d.rect(10, 10, 4, 4);
  d.clearRect(11, 11, 2, 2);
  assert.deepEqual([d.get(10, 10), d.get(11, 11), d.get(13, 13)], [1, 0, 1]);
});

test("Klicker, an app, counts TAP on its screen and blinks the TAP LED", () => {
  const device = new SimDevice();
  assert.ok(device.load(klickerBlock()).ok);
  device.frame();
  assert.ok(device.openApp(0));
  device.frame();
  const shown = () => device.display.rows().slice(16, 23).join("\n");
  const zero = new Display(); zero.number(0, 0, 16);
  assert.equal(shown(), zero.rows().slice(16, 23).join("\n"));
  device.post("buttonPress", 3);
  device.frame();
  const one = new Display(); one.number(1, 0, 16);
  assert.equal(shown(), one.rows().slice(16, 23).join("\n"));
  assert.equal(device.leds[20], 255);
  device.post("buttonPress", 3);
  device.frame();
  assert.equal(device.leds[20], 0);
  device.post("buttonPress", 4);
  device.frame();
  const two = new Display(); two.number(2, 0, 16);
  assert.equal(shown(), two.rows().slice(16, 23).join("\n"), "other keys do nothing");
});

test("Lauflicht moves one pad LED along and Pulsieren changes all 16 red pad LEDs", () => {
  const run = new SimDevice();
  run.load(blockOf("lauflicht"));
  const lit = () => [...run.leds].flatMap((v, i) => (v ? [i] : []));
  run.frame();
  assert.deepEqual(lit(), [44]);
  run.run(2);
  assert.deepEqual(lit(), [46]);
  run.run(32);
  assert.equal(lit().length, 1);
  const pulse = new SimDevice();
  pulse.load(blockOf("pulsieren"));
  pulse.run(4);
  const reds = Array.from({ length: 16 }, (_, n) => pulse.leds[44 + n * 2]);
  assert.ok(reds.every(v => v === reds[0] && v > 0));
  const first = reds[0];
  pulse.run(3);
  assert.notEqual(pulse.leds[44], first);
  assert.equal(pulse.leds[45], 0);
});

test("Snake runs 300 frames with turns and no fault, once its app is open", () => {
  const device = new SimDevice();
  assert.ok(device.load(blockOf("snake")).ok);
  assert.deepEqual(device.run(10), []);
  assert.ok(device.display.bytes.every(b => b === 0), "closed, Snake neither runs nor draws");
  assert.ok(device.openApp(0));
  const inputs = [{ frame: 20, event: "buttonPress", args: [15] }, { frame: 60, event: "buttonPress", args: [11] }];
  assert.deepEqual(device.run(300, inputs), []);
  assert.ok(device.display.bytes.some(b => b !== 0));
  assert.equal(device.status().scripts[0].state, "armed");
});

test("the clock advances one frame per frame and a fault is reported with its script", () => {
  const device = new SimDevice();
  device.load(build("tick", `let t = 0; korg.onEvent("frame", () => { t = korg.millis(); });`));
  device.run(3);
  assert.equal(device.now(), 3 * FRAME_MS);
  const bad = new SimDevice();
  bad.load(build("bad", `let z = 0; korg.onEvent("frame", () => { z = 1 / z; });`));
  const faults = bad.run(2);
  assert.equal(faults.length, 1);
  assert.equal(faults[0].script, "bad");
  assert.equal(faults[0].name, "DIV_ZERO");
});

test("inputs are recorded with their frame and play back to the same result", () => {
  const first = new SimDevice();
  first.load(klickerBlock());
  first.openApp(0);
  first.startRecording();
  first.frame();
  first.post("buttonPress", 3);
  first.frame();
  first.frame();
  first.post("buttonPress", 3);
  first.frame();
  const inputs = first.stopRecording();
  assert.deepEqual(inputs.map(i => [i.frame, i.event, i.args]), [[1, "buttonPress", [3]], [3, "buttonPress", [3]]]);
  const again = new SimDevice();
  again.load(klickerBlock());
  again.openApp(0);
  again.run(4, inputs);
  assert.deepEqual(again.display.rows(), first.display.rows());
  assert.throws(() => first.post("frame"), /not an input event/);
});

test("the probe reports the lines no input reached, and none once the inputs reach them", () => {
  const klicker = klickerBlock();
  const bare = probe(klicker, []);
  assert.equal(bare.ok, true);
  assert.ok(bare.lines.missing.length > 0, "the buttonPress body never ran");
  const full = probe(klicker, [{ frame: 5, event: "buttonPress", args: [3] }]);
  assert.deepEqual(full.lines.missing, []);
  assert.ok(full.frames >= 100);
  const bad = probe(build("bad", `korg.onEvent("frame", () => { let z = 0; z = 1 / z; });`));
  assert.equal(bad.ok, false);
  assert.equal(bad.faults.length, 1);
  const broken = probe(new Uint8Array(20));
  assert.equal(broken.ok, false);
  assert.ok(broken.loadError);
});

class FakeStorage {
  constructor(initial = {}) { this.map = new Map(Object.entries(initial)); this.fail = false; }
  getItem(k) { if (this.fail) throw new Error("blocked"); return this.map.get(k) ?? null; }
  setItem(k, v) { if (this.fail) throw new Error("blocked"); this.map.set(k, v); }
}

test("the workspace keeps scripts across loads, rejects bad names and survives broken storage", () => {
  const storage = new FakeStorage();
  const w = new Workspace(storage);
  w.save({ name: "zaehler", source: "let a = 1;" });
  w.save({ name: "zaehler", source: "let a = 2;", inputs: [{ frame: 1, event: "buttonPress", args: [3] }] });
  assert.equal(new Workspace(storage).list().length, 1);
  assert.equal(new Workspace(storage).get("zaehler").source, "let a = 2;");
  assert.deepEqual(new Workspace(storage).get("zaehler").inputs, [{ frame: 1, event: "buttonPress", args: [3] }]);
  for (const name of ["", "1abc", "a b", "ä", "abcdefghijklmnop", "a-b"]) assert.equal(validName(name), false, name);
  assert.throws(() => w.save({ name: "a b", source: "" }), RangeError);
  w.rename("zaehler", "count");
  assert.equal(w.get("zaehler"), null);
  assert.throws(() => w.rename("count", "count"), /gibt es schon/);
  assert.equal(w.freeName("count"), "count2");
  assert.equal(w.freeName("1 Mein Skript!"), "sMeinSkript");
  w.remove("count");
  assert.equal(w.list().length, 0);
  const broken = new FakeStorage({ "cee.scripts.v1": "{not json" });
  assert.deepEqual(new Workspace(broken).list(), []);
  const failing = new FakeStorage();
  failing.fail = true;
  const memory = new Workspace(failing);
  memory.save({ name: "x", source: "" });
  assert.equal(memory.list().length, 1, "the page still works when the browser blocks storage");
  assert.deepEqual(new Workspace(null).list(), []);
});

test("a changed source drops the probe that belonged to the old text", () => {
  const w = new Workspace(null);
  w.save({ name: "a", source: "one", probe: { key: sourceKey("one"), ok: true, missing: [] } });
  assert.ok(w.save({ name: "a", source: "one", inputs: [] }).probe, "same text keeps it");
  assert.equal(w.save({ name: "a", source: "two" }).probe, null);
});

test("the export gate wants a probe of this text, a clean run, and a yes for lines that never ran", () => {
  const src = "let a = 1;";
  const probeOf = (over = {}) => ({ key: sourceKey(src), ok: true, missing: [], ...over });
  assert.equal(exportGate({ source: src, probe: null }).ok, false);
  assert.match(exportGate({ source: src, probe: null }).reason, /nicht im Lauf geprobt/);
  assert.equal(exportGate({ source: `${src} `, probe: probeOf() }).ok, false);
  assert.equal(exportGate({ source: src, probe: probeOf({ ok: false, missing: [3] }) }).ok, false);
  assert.deepEqual(exportGate({ source: src, probe: probeOf({ missing: [4, 9] }) }), { ok: true, confirm: true, missing: [4, 9], reason: "Zeilen ohne Lauf: 4, 9." });
  assert.deepEqual(exportGate({ source: src, probe: probeOf() }), { ok: true, confirm: false, missing: [], reason: null });
});

test("the read API answers from the simulated hardware and a knob keeps its last value", () => {
  const source = `
    let t = 9; let tempo = 0; let pattern = 9; let part = 9; let step = 9; let mute = 9; let knob = 0;
    korg.onEvent("frame", () => {
      t = korg.read.transport(); tempo = korg.read.tempo(); pattern = korg.read.pattern(); part = korg.read.part();
      step = korg.read.step(2); mute = korg.read.mute(3); knob = korg.read.knob(4);
    });`;
  const sim = new SimDevice();
  const added = sim.load(build("reads", source));
  assert.ok(added.ok);
  sim.hardware.transport = 1; sim.hardware.tempo = 1500; sim.hardware.pattern = 12; sim.hardware.part = 16;
  sim.hardware.steps[2] = 33; sim.hardware.mutes[3] = 1;
  sim.post("knob", 4, 700);
  sim.post("knob", 4, 701);
  sim.frame();
  assert.deepEqual(Array.from(sim.runtime.scripts[0].script.vars.slice(0, 7)), [1, 1500, 12, 16, 33, 1, 701]);
  sim.post("knob", 19, 5);
  assert.equal(sim.hardware.knobs[19], 5);
  assert.equal(sim.hardware.knobs[0], 0);
});

test("the actions change the simulated hardware and the matching events come back through the ring", () => {
  const source = `
    let plays = 0; let stops = 0; let steps = 0; let beats = 0; let lastStep = 0; let pat = -1; let tempoSeen = 0; let partSeen = -1; let muteSeen = -1;
    korg.onEvent("buttonPress", (key) => {
      if (key == 1) korg.play();
      if (key == 2) korg.stop();
      if (key == 3) korg.pattern(7);
      if (key == 4) korg.tempo(1200);
      if (key == 5) korg.part(4);
      if (key == 6) korg.mute(9, 1);
    });
    korg.onEvent("play", () => { plays += 1; });
    korg.onEvent("stop", () => { stops += 1; });
    korg.onEvent("step", (s) => { steps += 1; lastStep = s; });
    korg.onEvent("beat", () => { beats += 1; });
    korg.onEvent("patternChange", (i) => { pat = i; });
    korg.onEvent("tempo", (t) => { tempoSeen = t; });
    korg.onEvent("partChange", (p) => { partSeen = p; });
    korg.onEvent("mute", (p, m) => { muteSeen = p * 10 + m; });`;
  const sim = new SimDevice();
  assert.ok(sim.load(build("act", source)).ok);
  sim.frame();
  for (const key of [3, 4, 5, 6, 1]) sim.post("buttonPress", key);
  sim.frame();
  sim.frame();
  assert.deepEqual([sim.hardware.pattern, sim.hardware.tempo, sim.hardware.part, sim.hardware.mutes[9], sim.hardware.transport], [7, 1200, 4, 1, 1]);
  sim.run(50);
  const vars = Array.from(sim.runtime.scripts[0].script.vars);
  const [plays, stops, steps, beats, lastStep, pat, tempoSeen, partSeen, muteSeen] = vars;
  assert.deepEqual([plays, stops, pat, tempoSeen, partSeen, muteSeen], [1, 0, 7, 1200, 4, 91]);
  assert.ok(steps >= 15 && steps <= 17, `${steps} steps in two seconds at 120 BPM (8 a second)`);
  assert.equal(beats, Math.floor(steps / 4));
  assert.equal(lastStep, steps % 64);
  sim.post("buttonPress", 2);
  sim.run(3);
  assert.equal(sim.hardware.transport, 0);
  assert.equal(Array.from(sim.runtime.scripts[0].script.vars)[1], 1);
});

test("backlight and led hold are state in the simulated hardware", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("lights", 'korg.onEvent("buttonPress", (k) => { korg.backlight(1, 0, 1); korg.ledHold(1); });')).ok);
  assert.deepEqual([sim.hardware.backlight, sim.hardware.ledHold], [[1, 1, 1], 0]);
  sim.frame();
  sim.post("buttonPress", 1);
  sim.frame();
  assert.deepEqual([sim.hardware.backlight, sim.hardware.ledHold], [[1, 0, 1], 1]);
});

test("korg.menu.add puts a page in the device menu, the user's change reaches the script as a menu event", () => {
  const device = new SimDevice();
  const loaded = device.load(build("menus", `
    let speed = 0; let seen = 0; let again = -2;
    let id = korg.menu.add("Speed", 1, 10, 50);
    korg.onEvent("ready", () => { again = korg.menu.add("Speed", 1, 10, 3); });
    korg.onEvent("menu", (which, value) => { if (which == id) { seen = value; } });
  `));
  assert.equal(loaded.error, null);
  assert.deepEqual(device.menus, [{ id: 0, script: "menus", label: "Speed", min: 1, max: 10, value: 10 }], "the first value is clamped into the range");
  device.frame();
  assert.equal(device.menus.length, 1, "the same label from the same script is the same page");
  assert.equal(device.menuSet(0, 7), 7);
  assert.equal(device.menuSet(0, 99), 10);
  assert.equal(device.menuSet(0, -5), 1);
  assert.equal(device.menuSet(5, 1), null, "no such page");
  device.frame();
  const vars = device.runtime.scripts[0].script.vars;
  assert.equal(vars[1], 1, "seen holds the last value the handler got");
  assert.equal(vars[2], 0, "the second add in ready returned the id of the first");
});

test("korg.menu.add is only for start and ready, takes a range that is a range, and holds twelve pages", () => {
  const frameUse = compile(`korg.onEvent("frame", () => { korg.menu.add("x", 0, 1, 0); });`, { name: "late" });
  assert.equal(frameUse.ok, false, "not callable from a frame handler");
  assert.match(formatError(frameUse.errors[0]), /korg\.menu\.add/);
  const device = new SimDevice();
  const loaded = device.load(build("backwards", `let id = korg.menu.add("x", 5, 1, 2);`));
  assert.equal(loaded.error?.name, "API_ARG");
  const many = new SimDevice();
  many.load(build("many", Array.from({ length: 14 }, (_, i) => `let p${i} = korg.menu.add("page${i}", 0, 9, 0);`).join("\n")));
  assert.equal(many.menus.length, 12);
  assert.equal(many.runtime.scripts[0].script.vars[12], -1, "the thirteenth page is refused with -1");
});
