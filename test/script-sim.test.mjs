import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PRESETS } from "../data/script/presets.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice, probe, FRAME_MS } from "../src/script/sim.mjs";
import { Display, WIDTH, HEIGHT } from "../src/script/display.mjs";
import { Workspace, validName, sourceKey } from "../src/script/workspace.mjs";
import { exportGate } from "../src/script/gate.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";

const preset = id => PRESETS.find(p => p.id === id);
const build = (name, source) => {
  const result = compile(source, { name });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  return result.blob;
};
const blockOf = id => build(id, preset(id).source);
const fixture = name => readFileSync(new URL(`./fixtures/scripts/${name}`, import.meta.url), "utf8");
const korgKey = name => KEY_NAMES.find(n => n.name === name).value;
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

test("the pad hold is state in the simulated hardware and ends when the app closes", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("locks", `
    let pads = 0;
    korg.app("Locks", "TOOLS");
    korg.onEvent("open", () => { korg.padHold(1); });
    korg.onEvent("pad", (index, velocity) => { pads = pads + 1; });
  `)).ok);
  sim.frame();
  assert.equal(sim.hardware.padHold, 0);
  assert.ok(sim.openApp(0));
  sim.frame();
  assert.equal(sim.hardware.padHold, 1);
  sim.post("pad", 3, 100);
  sim.frame();
  assert.equal(Array.from(sim.runtime.scripts[0].script.vars)[0], 1, "the plugin still gets the pad");
  sim.post("buttonPress", 13);
  sim.frame();
  assert.equal(sim.hardware.padHold, 0, "EXIT closes the app and gives the pads back");
});

test("the knob hold and the knob value a plugin gives the firmware are state in the simulated hardware", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("filter", `
    korg.onEvent("ready", () => { korg.knobHold(9, 1); });
    korg.onEvent("knob", (index, value) => { if (index == 9) korg.knob(9, value); if (index == 0) korg.knobHold(9, 0); });
  `)).ok);
  sim.frame();
  assert.equal(sim.hardware.knobHold, 1 << 9);
  sim.post("knob", 9, 136);
  sim.frame();
  assert.equal(sim.hardware.firmwareKnobs[9], 136);
  assert.equal(sim.hardware.knobs[9], 136, "korg.read.knob keeps the panel's value");
  sim.post("knob", 0, 5);
  sim.frame();
  assert.equal(sim.hardware.knobHold, 0);
});

test("korg.passKeys chooses the keys that reach the firmware while the app is open, the app's close resets them", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("keys", `
    korg.app("Keys", "TOOLS");
    korg.onEvent("open", () => { korg.passKeys(korg.key.SHIFT, 1); korg.passKeys(korg.key.PLAY, 0); });
  `)).ok);
  sim.frame();
  assert.deepEqual([sim.hardware.keyPasses(10), sim.hardware.keyPasses(2)], [0, 1], "SHIFT is kept, PLAY passes by default");
  assert.ok(sim.openApp(0));
  sim.frame();
  assert.deepEqual([sim.hardware.keyPasses(10), sim.hardware.keyPasses(2)], [1, 0]);
  sim.post("buttonPress", 2);
  sim.frame();
  assert.equal(sim.hardware.transport, 0, "PLAY kept from the firmware does not start the sequencer");
  sim.post("buttonPress", 13);
  sim.frame();
  assert.deepEqual([sim.hardware.keyPasses(10), sim.hardware.keyPasses(2)], [0, 1], "EXIT closes the app and the keys are back to their defaults");
});

test("korg.seq.setPartValue writes a part value clamped to its range, a field past the list is an argument error", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("parts", `
    korg.onEvent("ready", () => {
      korg.parts[3].pitch = -100; korg.parts[3].cutoff = 64; korg.seq.setPartValue(0, 10, 300);
      korg.parts[2].sample = 300; korg.parts[4].sample = 5000; korg.parts[2].ampEg = 9; korg.parts[2].ifxType = 200;
    });
    korg.onEvent("buttonPress", () => { korg.seq.setPartValue(1, 21, 2); });
  `)).ok);
  sim.frame();
  const at = (part, offset) => sim.hardware.patternBlock(-1)[0x800 + part * 0x330 + offset];
  assert.deepEqual([at(3, 36), at(3, 13), at(0, 24)], [0xC1, 64, 127], "pitch -63 as a signed byte, level clamped to 127");
  assert.equal(sim.hardware.patternValue(-1, 3, 15), -63);
  assert.deepEqual([sim.hardware.patternValue(-1, 2, 0), sim.hardware.patternValue(-1, 4, 0)], [300, 999], "the sample as its two bytes, up to 999");
  assert.deepEqual([at(2, 26), at(2, 33)], [1, 127], "AMP EG on or off; IFX type to 127, the device stops at its type count");
  sim.post("buttonPress", 3);
  const faults = sim.run(1);
  assert.equal(faults[0]?.name, "API_ARG", "there is no field 21");
});

test("korg.read.patternBytes and korg.seq.writeSteps copy the steps of a part from a stored pattern into the one that plays", () => {
  const sim = new SimDevice();
  const stored = sim.hardware.patternBlock(5);
  const step = (block, part, s) => 0x800 + part * 0x330 + 0x30 + s * 12;
  stored.set([1, 96, 100, 1, 61, 65, 0, 0, 9, 9, 9, 9], step(stored, 2, 0));
  stored.set([1, 50, 80, 1, 49, 0, 0, 0], step(stored, 2, 1));
  assert.ok(sim.load(build("copy", `
    const steps = new Array(768);
    let read = 0; let wrote = 0; let tail = 0;
    korg.onEvent("ready", () => {
      read = korg.read.patternBytes(steps, 5, 0x800 + 2 * 0x330 + 0x30);
      steps[13] = 200; steps[14] = 0; steps[12] = 7;
      wrote = korg.seq.writeSteps(steps, 7, 0);
      tail = korg.read.patternBytes(steps, -1, 0x3FFF);
    });
  `)).ok);
  sim.frame();
  const vars = Array.from(sim.runtime.scripts[0].script.vars);
  assert.deepEqual(vars.slice(768, 771), [768, 64, 1], "768 bytes read, 64 steps written, one byte left at the end of the block");
  const live = sim.hardware.patternBlock(-1);
  assert.deepEqual(Array.from(live.subarray(step(live, 7, 0), step(live, 7, 0) + 12)), [1, 96, 100, 1, 61, 65, 0, 0, 0, 0, 0, 0], "bytes 8 to 11 are not written");
  assert.deepEqual(Array.from(live.subarray(step(live, 7, 1), step(live, 7, 1) + 5)), [1, 127, 1, 1, 49], "on, gate and velocity clamped to their ranges");
});

test("korg.keyHold keeps a key from the firmware without an app, korg.pressKey passes a press the plugins do not get", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("keys", `
    let seen = 0;
    korg.onEvent("ready", () => { korg.keyHold(korg.key.PLAY, 1); });
    korg.onEvent("buttonPress", (key) => { seen = seen + 1; if (key == korg.key.PLAY && seen == 1) korg.pressKey(korg.key.STOP); if (key == korg.key.REC) korg.keyHold(korg.key.PLAY, 0); });
  `)).ok);
  sim.frame();
  assert.equal(sim.hardware.keyHold[2], 1);
  sim.hardware.transport = 1;
  sim.post("buttonPress", 2);
  sim.frame();
  assert.deepEqual(sim.hardware.pressedKeys, [1], "the plugin got PLAY and pressed STOP");
  assert.equal(sim.hardware.transport, 0, "STOP reached the firmware");
  assert.equal(Array.from(sim.runtime.scripts[0].script.vars)[0], 1, "the pressed STOP is no event for the plugin");
  sim.post("buttonPress", 2);
  sim.frame();
  assert.equal(sim.hardware.transport, 0, "PLAY held: the firmware does not start");
  sim.post("buttonPress", 0);
  sim.frame();
  sim.post("buttonPress", 2);
  sim.frame();
  assert.equal(sim.hardware.transport, 1, "given back, PLAY starts the sequencer");
});

test("two plugins masking the same key: both get it, the firmware does not while either masks it", () => {
  const sim = new SimDevice();
  const PLAY = 2, REC = 0;
  assert.ok(sim.load(build("first", `
    let seen = 0;
    korg.onEvent("ready", () => { korg.keyMask((1 << korg.key.PLAY) | (1 << korg.key.PART_MUTE), 0); });
    korg.onEvent("buttonPress", (key) => { seen = seen + 1; if (key == korg.key.REC) korg.keyMask(0, 0); });
  `)).ok);
  assert.ok(sim.load(build("second", `
    let seen = 0;
    korg.onEvent("ready", () => { korg.keyHold(korg.key.PLAY, 1); });
    korg.onEvent("buttonPress", (key) => { seen = seen + 1; if (key == korg.key.STOP) korg.keyHold(korg.key.PLAY, 0); });
  `)).ok);
  sim.frame();
  const seen = i => Array.from(sim.runtime.scripts[i].script.vars)[0];
  assert.equal(sim.hardware.keyHold[PLAY], 1);
  assert.equal(sim.hardware.keyHold[korgKey("PART_MUTE")], 1);
  sim.post("buttonPress", PLAY);
  sim.frame();
  assert.deepEqual([seen(0), seen(1)], [1, 1], "every plugin gets the event, whoever masks it");
  assert.equal(sim.hardware.transport, 0, "masked: the firmware does not start");
  sim.post("buttonPress", REC);
  sim.frame();
  assert.equal(sim.hardware.keyHold[PLAY], 1, "the first plugin's mask is empty now, the second still keeps PLAY");
  assert.equal(sim.hardware.keyHold[korgKey("PART_MUTE")], 0, "what only the first kept is free");
  sim.post("buttonPress", PLAY);
  sim.frame();
  assert.equal(sim.hardware.transport, 0);
  sim.post("buttonPress", korgKey("STOP"));
  sim.frame();
  assert.equal(sim.hardware.keyHold[PLAY], 0, "nobody keeps PLAY: the firmware gets it");
  sim.post("buttonPress", PLAY);
  sim.frame();
  assert.equal(sim.hardware.transport, 1);
});

test("a plugin that stops running lets go of its keys, knobs and pads, the others keep theirs", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("a", `
    korg.onEvent("ready", () => { korg.keyHold(korg.key.PLAY, 1); korg.knobHold(9, 1); korg.padHold(1); });
  `)).ok);
  assert.ok(sim.load(build("b", `
    korg.onEvent("ready", () => { korg.keyHold(korg.key.PLAY, 1); korg.knobHold(3, 1); });
    korg.onEvent("buttonPress", () => { korg.keyHold(korg.key.EXIT, 1); });
  `)).ok);
  sim.frame();
  assert.deepEqual([sim.hardware.keyHold[2], sim.hardware.knobHold, sim.hardware.padHold], [1, 1 << 9 | 1 << 3, 1]);
  sim.post("buttonPress", 7);
  sim.frame();
  assert.equal(sim.runtime.scripts[1].script.state, "disabled", "b faulted");
  sim.frame();
  assert.deepEqual([sim.hardware.keyHold[2], sim.hardware.knobHold, sim.hardware.padHold], [1, 1 << 9, 1], "a keeps what it held");
});

test("korg.keyMask refuses EXIT in the mask and takes keys 32 and 33 from the second word", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("mask", `
    korg.onEvent("ready", () => { korg.keyMask(0, 3); });
    korg.onEvent("buttonPress", () => { korg.keyMask(1 << korg.key.EXIT, 0); });
  `)).ok);
  sim.frame();
  assert.deepEqual([sim.hardware.keyHold[32], sim.hardware.keyHold[33], sim.hardware.keyHold[31]], [1, 1, 0]);
  sim.post("buttonPress", 5);
  const faults = sim.run(1);
  assert.equal(faults[0]?.name, "API_ARG");
});

test("korg.keyHold refuses EXIT, korg.touchLockX is state in the simulated hardware", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("lock", `
    korg.onEvent("ready", () => { korg.touchLockX(64); });
    korg.onEvent("touch", (x, y) => { if (x > 900) korg.touchLockX(-1); });
    korg.onEvent("buttonPress", () => { korg.keyHold(korg.key.EXIT, 1); });
  `)).ok);
  sim.frame();
  assert.equal(sim.hardware.touchLock, 64);
  sim.post("touch", 1000, 300);
  sim.frame();
  assert.equal(sim.hardware.touchLock, -1, "the plugin gets the real X and lets go");
  sim.post("buttonPress", 5);
  const faults = sim.run(1);
  assert.equal(faults[0]?.name, "API_ARG");
});

test("korg.seq.setPatternValue writes a value of the pattern that plays, clamped and stored as it is read", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("pattern", `
    korg.onEvent("ready", () => {
      korg.seq.setPatternValue(0, 5000); korg.seq.setPatternValue(1, -20); korg.seq.setPatternValue(2, 3);
      korg.seq.setPatternValue(4, 7); korg.seq.setPatternValue(9, -1); korg.seq.setPatternValue(10, 4);
    });
  `)).ok);
  sim.frame();
  const read = field => sim.hardware.patternValue(-1, -1, field);
  assert.deepEqual([0, 1, 2, 4, 9, 10].map(read), [3000, -20, 3, 7, -1, 4]);
  const block = sim.hardware.patternBlock(-1);
  assert.deepEqual([block[34], block[35], block[37], block[15104]], [3000 & 255, 3000 >> 8, 2, 0], "tempo little endian, length 3 bars as 2, no chain as 0");
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

test("the panel calls of API 25 hand the firmware down and up like a finger, a second down sends nothing", () => {
  const sim = new SimDevice();
  assert.ok(sim.load(build("panel", `
    korg.onEvent("ready", () => {
      korg.keyDown(korg.key.SHIFT); korg.keyDown(korg.key.SHIFT); korg.keyUp(korg.key.SHIFT); korg.keyUp(korg.key.SHIFT);
      korg.padDown(3, 100); korg.padDown(3, 50); korg.padUp(3); korg.padUp(3);
      korg.encoder(1, -1); korg.encoder(4, 0); korg.touch(-1, 0); korg.touch(512, 700); korg.touch(-1, 0);
      korg.keyDown(korg.key.PLAY);
    });
  `)).ok);
  sim.frame();
  const shift = korgKey("SHIFT");
  assert.deepEqual(sim.hardware.firmwareInputs, [
    ["keyDown", shift], ["keyUp", shift], ["padDown", 3, 100], ["padUp", 3], ["encoder", 1, -1], ["touch", 512, 700], ["touchUp"],
    ["keyDown", korgKey("PLAY")],
  ]);
  assert.equal(sim.hardware.transport, 1, "PLAY down reached the firmware");
});

test("korg.pressKey and korg.keyDown take EXIT since API 25 and close an open app first", () => {
  const sim = new SimDevice();
  let closed = 0;
  sim.hardware.closeApp = () => { closed++; };
  assert.ok(sim.load(build("exit", `korg.onEvent("ready", () => { korg.pressKey(korg.key.EXIT); korg.keyDown(korg.key.EXIT); korg.keyUp(korg.key.EXIT); });`)).ok);
  sim.frame();
  assert.deepEqual(sim.hardware.pressedKeys, [korgKey("EXIT")]);
  assert.deepEqual(sim.hardware.firmwareInputs, [["keyDown", korgKey("EXIT")], ["keyUp", korgKey("EXIT")]]);
  assert.equal(closed, 2);
});
