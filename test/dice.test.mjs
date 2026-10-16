import { test } from "node:test";
import assert from "node:assert/strict";
import { Pattern, cleanName, PatternFile, toSinglePattern, parseSinglePattern } from "../src/pattern.mjs";
import { rollPart, rng, scalePool, checkRoll, SCALES, DEFAULTS } from "../src/dice.mjs";
import { converter } from "../src/map/convert.mjs";
import { lintPattern } from "../src/pattern-rules.mjs";
import { makePatternFile } from "./helpers.mjs";

const BLOCK = 0x4000;

/** A valid, silent pattern from nothing: framed, a sample on every part, nothing on. Own data, no Korg bytes. */
function blank() {
  const b = new Uint8Array(BLOCK);
  [..."PTST"].forEach((c, i) => { b[i] = c.charCodeAt(0); });
  [..."PTED"].forEach((c, i) => { b[15356 + i] = c.charCodeAt(0); });
  const p = new Pattern(b);
  p.setRaw("pattern.name", [], "Init Pattern");
  p.setRaw("pattern.tempo", [], 1200);
  p.setRaw("pattern.length", [], 0);
  for (let i = 0; i < 16; i++) p.setRaw("part.sample", [i], 10 + i);
  return p;
}

const onSteps = (p, part) => Array.from({ length: 64 }, (_, s) => s).filter(s => p.raw("step.on", [part, s]) === 1);
const diff = (a, b) => [...a.keys()].filter(i => a[i] !== b[i]);

test("the same seed and controls give the same bytes, another seed gives other steps", () => {
  const base = blank();
  const a = rollPart(base, { kind: "melody", density: 0.5, seed: 42, part: 3 });
  const b = rollPart(base, { kind: "melody", density: 0.5, seed: 42, part: 3 });
  const c = rollPart(base, { kind: "melody", density: 0.5, seed: 43, part: 3 });
  assert.deepEqual(a.pattern.bytes, b.pattern.bytes);
  assert.notDeepEqual(a.pattern.bytes, c.pattern.bytes);
  const d = rollPart(base, { kind: "drums", density: 0.5, seed: 42, part: 3 });
  const e = rollPart(base, { kind: "drums", density: 0.5, seed: 42, part: 3 });
  assert.deepEqual(d.pattern.bytes, e.pattern.bytes);
});

test("the generator's stream is fixed: seed 1 always starts the same way", () => {
  const r = rng(1);
  assert.deepEqual([r(), r(), r()].map(x => Math.round(x * 1e6)), [627074, 2736, 527447]);
});

test("the base is not changed and only the part, swing, length, mute and name move", () => {
  const base = blank();
  base.setRaw("part.mute", [5], 1);
  const before = Uint8Array.from(base.bytes);
  const { pattern } = rollPart(base, { part: 5, kind: "drums", density: 0.5, seed: 9, swing: 12, bars: 2, name: "Dice 9" });
  assert.deepEqual(base.bytes, before);
  const allowed = new Set();
  for (const id of ["pattern.name", "pattern.swing", "pattern.length", "part.mute"]) {
    const ix = id.startsWith("part") ? [5] : [];
    const at = Pattern.offset(id, ix);
    for (let i = 0; i < 18; i++) allowed.add(at + i);
  }
  for (let s = 0; s < 64; s++) for (const id of ["step.on", "step.gate", "step.velocity", "step.trigger"]) allowed.add(Pattern.offset(id, [5, s]));
  for (let s = 0; s < 64; s++) for (let k = 0; k < 4; k++) allowed.add(Pattern.offset("step.note", [5, s, k]));
  const stray = diff(before, pattern.bytes).filter(i => !allowed.has(i));
  assert.deepEqual(stray, []);
  assert.equal(pattern.raw("pattern.swing"), 12);
  assert.equal(pattern.raw("pattern.length"), 1);
  assert.equal(pattern.name, "Dice 9");
  assert.equal(pattern.raw("part.mute", [5]), 0, "a muted part is switched on so it is heard");
});

test("density sets the number of steps: none, a quarter, all", () => {
  const base = blank();
  for (const kind of ["drums", "melody"]) {
    assert.equal(onSteps(rollPart(base, { kind, density: 0 }).pattern, 0).length, 0);
    assert.equal(onSteps(rollPart(base, { kind, density: 0.25, seed: 5 }).pattern, 0).length, 4);
    assert.equal(onSteps(rollPart(base, { kind, density: 1 }).pattern, 0).length, 16);
  }
  const four = rollPart(base, { density: 0.5, bars: 4, seed: 3 });
  assert.equal(four.count, 32);
  assert.ok(onSteps(four.pattern, 0).every(s => s < 64));
});

test("steps beyond the pattern's length stay off and an old part is replaced", () => {
  const base = blank();
  for (let s = 0; s < 64; s++) base.setRaw("step.on", [1, s], 1);
  const { pattern } = rollPart(base, { part: 1, density: 0.5, seed: 11 });
  const on = onSteps(pattern, 1);
  assert.equal(on.length, 8);
  assert.ok(on.every(s => s < 16));
});

test("drum steps carry the factory default note C4 and nothing else", () => {
  const { pattern, steps } = rollPart(blank(), { kind: "drums", density: 0.75, seed: 2, part: 9 });
  for (const s of steps) {
    assert.equal(pattern.raw("step.note", [9, s.step, 0]), 61);
    for (let k = 1; k < 4; k++) assert.equal(pattern.raw("step.note", [9, s.step, k]), 0);
  }
});

test("heavy beats are chosen before the steps in between", () => {
  let downbeat = 0;
  let offbeat = 0;
  for (let seed = 1; seed <= 60; seed++) {
    for (const s of rollPart(blank(), { kind: "drums", density: 0.25, seed }).steps) { if (s.step % 4 === 0) downbeat++; else if (s.step % 2 === 1) offbeat++; }
  }
  assert.ok(downbeat > offbeat * 2, `downbeats ${downbeat}, odd steps ${offbeat}`);
});

test("melody notes lie in the scale above the root, within the span", () => {
  for (const scale of SCALES.map(x => x.name)) {
    for (const root of [0, 7, 11]) {
      const octave = 3;
      const span = 2;
      const { steps } = rollPart(blank(), { kind: "melody", density: 1, seed: 21, root, scale, octave, span });
      const pool = new Set(scalePool(scale, root, octave, span));
      assert.ok(steps.length > 0);
      for (const s of steps) assert.ok(pool.has(s.note), `${scale} ${root}: note ${s.note}`);
      const def = SCALES.find(x => x.name === scale);
      for (const s of steps) assert.ok(def.intervals.includes(((s.note - root) % 12 + 12) % 12), `${scale}: ${s.note} is not in the scale`);
      assert.ok(Math.min(...steps.map(x => x.note)) >= 12 * (octave + 1) + root);
      assert.ok(Math.max(...steps.map(x => x.note)) <= 12 * (octave + 1) + root + 12 * span);
    }
  }
});

test("a melody moves mostly by steps of the scale, not by random jumps", () => {
  const { steps } = rollPart(blank(), { kind: "melody", density: 1, bars: 4, seed: 8, scale: "Ionian", span: 3 });
  const pool = scalePool("Ionian", 0, 3, 3);
  const moves = steps.slice(1).map((s, i) => Math.abs(pool.indexOf(s.note) - pool.indexOf(steps[i].note)));
  const small = moves.filter(m => m <= 2).length;
  assert.ok(small / moves.length > 0.6, `${small} of ${moves.length} moves are small`);
});

test("velocity and gate stay in the ranges the pattern format takes", () => {
  for (const accent of [0, 1]) for (const gate of [0, 1]) {
    const { pattern, steps } = rollPart(blank(), { density: 1, bars: 4, seed: 4, accent, gate });
    for (const s of steps) {
      assert.ok(s.velocity >= 1 && s.velocity <= 127);
      assert.ok(s.gate >= 1 && s.gate <= 96);
      assert.equal(pattern.raw("step.velocity", [0, s.step]), s.velocity);
      assert.equal(pattern.raw("step.gate", [0, s.step]), s.gate);
    }
  }
  const short = rollPart(blank(), { density: 1, gate: 0.2, seed: 6 }).steps;
  const long = rollPart(blank(), { density: 1, gate: 0.9, seed: 6 }).steps;
  const mean = xs => xs.reduce((a, x) => a + x.gate, 0) / xs.length;
  assert.ok(mean(short) < mean(long));
});

test("every rolled step has on and trigger, so the linter finds nothing on the steps", () => {
  const { pattern, steps } = rollPart(blank(), { density: 1, bars: 4, seed: 10, kind: "melody" });
  for (const s of steps) assert.equal(pattern.raw("step.trigger", [0, s.step]), 1);
  assert.deepEqual(lintPattern(pattern.bytes), []);
  assert.deepEqual(checkRoll(pattern), []);
});

test("key and scale are written only on request, with the device's own scale number", () => {
  const base = blank();
  assert.equal(rollPart(base, { kind: "melody", root: 7, scale: "Dorian" }).pattern.raw("pattern.key"), 0);
  const { pattern } = rollPart(base, { kind: "melody", root: 7, scale: "Dorian", writeScale: true });
  assert.equal(pattern.raw("pattern.key"), 7);
  assert.equal(pattern.plain("pattern.scale").text, "Dorian");
  const drums = rollPart(base, { kind: "drums", root: 7, writeScale: true }).pattern;
  assert.equal(drums.raw("pattern.key"), 0, "drums have no key");
});

test("each scale carries the number and the name of the device's own list", () => {
  const device = converter("scale");
  for (const s of SCALES) assert.equal(device.format(s.device), s.name);
});

test("warnings: a part without a sample, a muted part left muted", () => {
  const base = blank();
  base.bytes.fill(0xff, Pattern.offset("part.sample", [4]), Pattern.offset("part.sample", [4]) + 2);
  assert.match(rollPart(base, { part: 4 }).warnings.join(" "), /kein Sample/);
  base.setRaw("part.mute", [6], 1);
  const kept = rollPart(base, { part: 6, unmute: false });
  assert.equal(kept.pattern.raw("part.mute", [6]), 1);
  assert.match(kept.warnings.join(" "), /gemutet und bleibt/);
  assert.deepEqual(rollPart(base, { part: 0 }).warnings, []);
});

test("bad controls are refused with a plain message", () => {
  const base = blank();
  for (const bad of [{ part: 16 }, { part: -1 }, { kind: "bass" }, { density: 1.5 }, { seed: -1 }, { seed: 1.5 }, { root: 12 }, { scale: "Raga 1" }, { span: 4 }, { gate: 2 }, { accent: -1 }, { swing: 49 }, { bars: 5 }]) {
    assert.throws(() => rollPart(base, bad), RangeError, JSON.stringify(bad));
  }
  assert.equal(DEFAULTS.seed, 1);
});

test("names: printable ASCII, 16 characters, and a name nobody can show is dropped", () => {
  assert.equal(cleanName("  Hello World, this is too long  "), "Hello World, thi");
  assert.equal(cleanName("Zürich☃ ok"), "Zrich ok");
  assert.equal(cleanName("☃"), "");
  assert.equal(cleanName(undefined), "");
  assert.equal(rollPart(blank(), { name: "☃" }).pattern.name, "Init Pattern");
  assert.equal(rollPart(blank(), { name: "  Kick Roll " }).pattern.name, "Kick Roll");
});

test("a rolled pattern goes into a backup slot and a single file and comes back the same", () => {
  const file = PatternFile.parse(makePatternFile(3));
  const { pattern } = rollPart(file.pattern(2), { part: 0, density: 0.5, seed: 77, name: "Roll" });
  file.replace(2, pattern);
  const again = PatternFile.parse(file.toBytes());
  assert.deepEqual(again.pattern(2).bytes, pattern.bytes);
  assert.equal(again.name(2), "Roll");
  assert.deepEqual(again.pattern(1).bytes, PatternFile.parse(makePatternFile(3)).pattern(1).bytes);
  assert.deepEqual(parseSinglePattern(toSinglePattern(pattern)).bytes, pattern.bytes);
});
