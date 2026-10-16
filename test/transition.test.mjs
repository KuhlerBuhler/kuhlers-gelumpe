import { test } from "node:test";
import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import assert from "node:assert/strict";
import { Pattern, PatternFile, parseSinglePattern, toSinglePattern } from "../src/pattern.mjs";
import { makePatternFile } from "./helpers.mjs";
import { makeTransitions, checkTransition, pickSlots, tailArc, describe, main } from "../tools/set/transition.mjs";
import { chainsOf, summarize, motionSlots, onSteps, effectChanges, DEST } from "../tools/set/lib.mjs";

const BLOCK = 0x4000;

/** A pattern block that is valid and empty: framed, no sample on any part, nothing on. Own data, no Korg bytes. */
function blank(name = "T") {
  const b = new Uint8Array(BLOCK);
  [..."PTST"].forEach((c, i) => { b[i] = c.charCodeAt(0); });
  [..."PTED"].forEach((c, i) => { b[15356 + i] = c.charCodeAt(0); });
  const p = new Pattern(b);
  p.setRaw("pattern.name", [], name);
  p.setRaw("pattern.tempo", [], 1500);
  p.setRaw("pattern.length", [], 3);
  for (let i = 0; i < 16; i++) p.bytes.fill(0xff, Pattern.offset("part.sample", [i]), Pattern.offset("part.sample", [i]) + 2);
  return p;
}

/** Give a part a sample, a filter and steps; `notes` are cycled over the steps. */
function addPart(p, i, { sample, steps, notes = [60], cutoff = 100, filterType = 1, mute = 0, ifx = null }) {
  if (ifx) { p.setRaw("part.ifxOn", [i], ifx.on); p.setRaw("part.ifxType", [i], ifx.type); p.setRaw("part.ifxEdit", [i], ifx.edit ?? 64); }
  p.setRaw("part.sample", [i], sample);
  p.setRaw("part.cutoff", [i], cutoff);
  p.setRaw("part.filterType", [i], filterType);
  p.setRaw("part.mute", [i], mute);
  p.setRaw("part.motionMode", [i], 1);
  p.setRaw("part.level", [i], 100);
  steps.forEach((s, k) => {
    p.setRaw("step.on", [i, s], 1);
    p.setRaw("step.trigger", [i, s], 1);
    p.setRaw("step.gate", [i, s], 48);
    p.setRaw("step.velocity", [i, s], 100);
    p.setRaw("step.note", [i, s, 0], notes[k % notes.length] + 1);
  });
}
const every = n => Array.from({ length: 64 / n }, (_, k) => k * n);

/** A: a busy end state, B: a sparse start. */
function pair() {
  const a = blank("A side");
  addPart(a, 0, { sample: 10, steps: every(2) });
  addPart(a, 1, { sample: 11, steps: every(4), notes: [36, 43] });
  addPart(a, 2, { sample: 12, steps: every(1), notes: [60, 63, 67], cutoff: 120 });
  addPart(a, 3, { sample: 13, steps: every(8), mute: 1 });
  a.setRaw("pattern.mfx.type", [], 2);
  a.setRaw("pattern.mfx.hold", [], 1);
  a.setRaw("pattern.mfx.padX", [], 20);
  a.setRaw("pattern.mfx.padY", [], 110);
  a.setRaw("pattern.tempo", [], 1500);
  const b = blank("B side");
  addPart(b, 4, { sample: 20, steps: every(16) });
  addPart(b, 5, { sample: 21, steps: every(8) });
  addPart(b, 2, { sample: 22, steps: every(16) });
  b.setRaw("pattern.mfx.type", [], 5);
  b.setRaw("pattern.tempo", [], 1600);
  return { a, b };
}

/** A longer set-like scene: five parts in A (one shared with B), a muted spare, three parts of B's own. */
function scene() {
  const a = blank("A scene");
  addPart(a, 0, { sample: 10, steps: every(4), ifx: { on: 1, type: 5 } });
  addPart(a, 1, { sample: 11, steps: every(8) });
  addPart(a, 2, { sample: 12, steps: every(2), notes: [60, 63, 67] });
  addPart(a, 3, { sample: 13, steps: every(4) });
  addPart(a, 4, { sample: 14, steps: every(16), ifx: { on: 1, type: 36, edit: 49 } });
  addPart(a, 12, { sample: 15, steps: every(8), mute: 1 });
  a.setRaw("pattern.mfx.type", [], 1);
  a.setRaw("pattern.mfx.padX", [], 14);
  a.setRaw("pattern.mfx.padY", [], 108);
  a.setRaw("pattern.tempo", [], 1630);
  const b = blank("B scene");
  addPart(b, 4, { sample: 14, steps: every(16), ifx: { on: 1, type: 36, edit: 49 } });
  addPart(b, 5, { sample: 20, steps: every(16), ifx: { on: 1, type: 34, edit: 90 } });
  addPart(b, 6, { sample: 21, steps: every(4), ifx: { on: 0, type: 36 } });
  addPart(b, 7, { sample: 22, steps: every(8) });
  b.setRaw("pattern.mfx.type", [], 5);
  b.setRaw("pattern.tempo", [], 1450);
  return { a, b };
}

const audibleSteps = p => summarize(p).audibleSteps;
const motionOf = (p, part, dest) => motionSlots(p).find(m => m.part === part && m.dest === Object.keys(DEST).find(k => DEST[k] === dest));
const stepsOf = (p, i) => onSteps(p, i).length;
const sample = (p, i) => p.raw("part.sample", [i]);
const muted = (p, i) => p.raw("part.mute", [i]) === 1;

test("direction auto: blend when both sides have parts of their own, else up or down; bad options are refused", () => {
  const { a, b } = pair();
  assert.equal(makeTransitions(a, b).direction, "blend");
  assert.equal(makeTransitions(b, a).direction, "blend");
  const bOnly = blank("B only"); addPart(bOnly, 0, { sample: 10, steps: every(2) }); addPart(bOnly, 5, { sample: 21, steps: every(4) });
  const aOnly = blank("A only"); addPart(aOnly, 0, { sample: 10, steps: every(2) });
  assert.equal(makeTransitions(aOnly, bOnly).direction, "up");
  assert.equal(makeTransitions(bOnly, aOnly).direction, "down");
  assert.equal(makeTransitions(a, b, { direction: "up" }).direction, "up");
  assert.throws(() => makeTransitions(a, b, { direction: "sideways" }), /direction/);
  assert.throws(() => makeTransitions(a, b, { count: 0 }), /count/);
  assert.throws(() => makeTransitions(a, b, { pad: "x" }), /pad/);
  assert.throws(() => makeTransitions(a, b, { sweep: "x" }), /sweep/);
  assert.throws(() => makeTransitions(a, b, { tempo: "x" }), /tempo/);
});

test("blend: A's own parts leave in groups of at most leaveMax, B's own parts come in sparsest first", () => {
  const { a, b } = scene();
  const flat = { valley: "none", accent: "none" };
  const { items, direction } = makeTransitions(a, b, { count: 5, ...flat });
  assert.equal(direction, "blend");
  const at = i => items[i - 1].pattern;
  const leaveAt = { 0: 1, 3: 2, 1: 3, 2: 4 };
  for (const [part, L] of Object.entries(leaveAt)) {
    for (let i = 1; i <= 5; i++) {
      assert.equal(muted(at(i), Number(part)), i >= L, `part ${Number(part) + 1} at transition ${i}`);
      assert.equal(stepsOf(at(i), Number(part)), stepsOf(a, Number(part)), "a leaving part keeps its steps");
    }
  }
  const together = makeTransitions(a, b, { count: 5, leaveMax: 4, ...flat }).items;
  assert.deepEqual([0, 1, 2, 3].map(p => muted(together[0].pattern, p)), [true, false, false, false], "leaving is spread over the transitions, leaveMax only caps a transition");
  const two = makeTransitions(a, b, { count: 5, leaveMax: 1, ...flat }).items;
  assert.deepEqual(two.map(it => [0, 1, 2, 3].filter(p => muted(it.pattern, p)).length), [1, 2, 3, 4, 4], "one per transition at most");
  assert.throws(() => makeTransitions(a, b, { leaveMax: 0 }), /leaveMax/);
  assert.ok(!summarize(at(1)).parts[5].audible && summarize(at(2)).parts[5].audible, "part 6 (4 steps) comes in at transition 2");
  assert.ok(!summarize(at(2)).parts[7].audible && summarize(at(3)).parts[7].audible, "part 8 at 3");
  assert.ok(!summarize(at(3)).parts[6].audible && summarize(at(4)).parts[6].audible, "part 7 (the densest) last, at 4");
  assert.equal(sample(at(2), 5), 20, "a copy of B's own part block");
  assert.deepEqual([2, 3, 4, 5].map(i => stepsOf(at(i), 5)), [2, 3, 3, 4], "fuller with every transition, whole in the last");
  assert.deepEqual([4, 5].map(i => stepsOf(at(i), 6)), [8, 16]);
  for (let i = 1; i <= 4; i++) assert.equal(stepsOf(at(i), 4), 4, "a part that sounds in both stays as A has it");
  assert.equal(stepsOf(at(5), 4), 3, "and stops short of the end in the last transition");
  assert.ok(items[0].notes.some(n => /nicht kopiert/.test(n)));
  const thin = makeTransitions(a, b, { count: 5, thinBefore: 0.5, ...flat }).items;
  assert.equal(stepsOf(thin[0].pattern, 3), 8, "thinBefore: half the steps in the transition before the part goes (part 4 leaves at 2)");
  assert.equal(stepsOf(thin[1].pattern, 3), 16, "and then the steps are as they were, muted");
});

test("offbeat parts of B wait for B unless arrive is all", () => {
  const { a, b } = scene();
  addPart(b, 9, { sample: 23, steps: [2, 6, 10, 14, 18, 22, 26, 30] });
  const waits = makeTransitions(a, b, { count: 5, valley: "none" });
  waits.items.forEach(it => assert.ok(!summarize(it.pattern).parts[9].audible));
  assert.ok(waits.items[0].notes.some(n => /Part 10.*erst mit B/.test(n)));
  const all = makeTransitions(a, b, { count: 5, valley: "none", arrive: "all" });
  assert.ok(all.items.some(it => summarize(it.pattern).parts[9].audible));
  assert.throws(() => makeTransitions(a, b, { arrive: "x" }), /arrive/);
});

test("valley: the middle of the chain has few parts and few steps, the ends do not", () => {
  const { a, b } = scene();
  const sum = o => makeTransitions(a, b, { count: 5, accent: "none", ...o }).items.map(it => summarize(it.pattern));
  const deep = sum({}), flat = sum({ valley: "none" });
  assert.ok(deep[2].audible <= 3, `parts at the deepest point: ${deep[2].audible}`);
  const base = (summarize(a).audibleSteps + summarize(b).audibleSteps) / 2;
  assert.ok(deep[2].audibleSteps <= base * 0.4, `${deep[2].audibleSteps} steps against ${base}`);
  assert.ok(deep[2].audibleSteps < deep[0].audibleSteps && deep[2].audibleSteps < deep[4].audibleSteps);
  assert.ok(flat[2].audibleSteps >= deep[2].audibleSteps);
  assert.ok(sum({ valleyParts: 2 })[2].audible <= 2, "valleyParts sets the part count");
  assert.ok(sum({ valley: 0.1 })[2].audibleSteps < deep[2].audibleSteps, "a number sets the share of steps left");
  const one = makeTransitions(a, b, { count: 1, accent: "none" }).items[0].pattern;
  assert.ok(summarize(one).audibleSteps > 0);
  const result = makeTransitions(a, b, { count: 5, accent: "none" });
  result.items.forEach(it => assert.ok(summarize(it.pattern).parts[6].audible || it !== result.items[4], "the carrying part is never muted in the last transition"));
});

test("accent: a muted spare part of A that sounds in neither A nor B comes in at 40 percent and in the last transition", () => {
  const { a, b } = scene();
  const { items } = makeTransitions(a, b, { count: 5 });
  const heard = items.map(it => summarize(it.pattern).parts[12].audible);
  assert.deepEqual(heard, [false, true, false, false, true]);
  assert.ok(items[1].notes.some(n => /Akzent: Part 13/.test(n)));
  assert.ok(makeTransitions(a, b, { count: 5, accent: "none" }).items.every(it => !summarize(it.pattern).parts[12].audible));
  assert.ok(makeTransitions(a, b, { count: 2 }).items.every(it => !summarize(it.pattern).parts[12].audible), "not in a short chain");
  assert.ok(makeTransitions(a, b, { count: 5, accent: 13 }).items[1].notes.some(n => /Part 13/.test(n)));
});

test("the part that plays on into B is clipped to a short decay in the last transition, insert motion is optional", () => {
  const { a, b } = scene();
  b.setRaw("part.decay", [6], 100);
  const decays = o => makeTransitions(a, b, { count: 5, ...o }).items.map(it => it.pattern.raw("part.decay", [6]));
  assert.deepEqual(decays({}), [0, 0, 0, 100, 15], "B's own decay until the last transition");
  assert.equal(decays({ clip: "none" })[4], 100);
  assert.equal(decays({ clip: 30 })[4], 30);
  assert.equal(motionSlots(makeTransitions(a, b, { count: 5 }).items[4].pattern).filter(m => m.dest === "ifxOn").length, 0);
  const on = motionSlots(makeTransitions(a, b, { count: 5, insertMotion: true }).items[4].pattern).find(m => m.dest === "ifxOn");
  assert.equal(on.part, 7);
  assert.deepEqual([on.values[31], on.values[32], on.values[48], on.values[49]], [0, 128, 128, 0]);
});

test("pad release: the last transition runs the pad into the corner in its last quarter", () => {
  const { a, b } = scene();
  const { items } = makeTransitions(a, b, { count: 3, pad: "release" });
  const last = items[2].pattern;
  assert.equal(last.raw("pattern.mfx.hold"), 0);
  assert.deepEqual([last.raw("pattern.mfx.padX"), last.raw("pattern.mfx.padY")], [127, 1]);
  const x = motionOf(last, 17, DEST.mfxX), y = motionOf(last, 17, DEST.mfxY);
  assert.deepEqual([x.values[47], x.values[63], y.values[47], y.values[63]], [28, 127, 110, 1]);
  assert.equal(motionOf(items[1].pattern, 17, DEST.mfxX), undefined);
  assert.equal(items[1].pattern.raw("pattern.mfx.hold"), 1);
});

test("every transition keeps A's insert and master effects; the differences land in the switch into B and are reported", () => {
  const { a, b } = scene();
  const result = makeTransitions(a, b, { count: 5 });
  for (const it of result.items) {
    assert.deepEqual(effectChanges(a, it.pattern), [], it.name);
    assert.deepEqual(it.fx, []);
  }
  assert.equal(result.items[1].pattern.raw("part.ifxType", [5]), 0, "part 6 came in with A's insert, not B's type 34");
  assert.equal(result.items[1].pattern.raw("part.ifxOn", [5]), 0);
  assert.deepEqual(result.arrivalFx, ["Part 1", "Part 6", "Part 7", "Master"]);
  assert.deepEqual(effectChanges(result.items[4].pattern, b), result.arrivalFx);
  const forced = makeTransitions(a, b, { count: 3, mfx: 7 });
  assert.equal(forced.items[1].pattern.raw("pattern.mfx.type"), 1);
  assert.equal(forced.items[2].pattern.raw("pattern.mfx.type"), 7);
  assert.deepEqual(forced.items[2].fx, ["Master"]);
  assert.ok(forced.items[2].notes.some(n => /Effekt-Wechsel/.test(n)));
  assert.deepEqual(makeTransitions(a, a, { count: 2 }).arrivalFx, []);
});

test("hold goes on after the first transition at the start of the corner curve and off in the last, both header bytes together", () => {
  const { a, b } = scene();
  const { items } = makeTransitions(a, b, { count: 4 });
  const view = p => [p.raw("pattern.mfx.hold"), p.bytes[60], p.raw("pattern.mfx.padX"), p.raw("pattern.mfx.padY")];
  assert.deepEqual(view(items[0].pattern), [1, 1, 48, 110]);
  assert.deepEqual(view(items[1].pattern), [1, 1, 28, 110]);
  assert.deepEqual(view(items[2].pattern), [1, 1, 28, 110]);
  assert.deepEqual(view(items[3].pattern), [0, 0, 28, 110], "off in the last, the pad stays");
  assert.equal(a.raw("pattern.mfx.hold"), 0, "A itself is not changed");
  assert.deepEqual(view(makeTransitions(a, b, { count: 1 }).items[0].pattern), [0, 0, 14, 108], "one transition: nothing to hold");
  const pairs = pair();
  const kept = makeTransitions(pairs.a, pairs.b, { count: 3 }).items.map(it => view(it.pattern));
  assert.deepEqual(kept.map(v => v[0]), [1, 1, 0], "A had hold on: it stays, then goes off in the last");
  assert.equal(kept[0][2], 20, "and the pad stays where A has it");
  assert.deepEqual(makeTransitions(a, b, { count: 3, pad: "none" }).items.map(it => it.pattern.raw("pattern.mfx.hold")), [0, 0, 0]);
});

test("tempo: ease holds, moves in the middle and settles; ramp is a straight line; keep leaves it", () => {
  const { a, b } = scene();
  const raws = o => makeTransitions(a, b, { count: 5, ...o }).items.map(it => it.pattern.raw("pattern.tempo"));
  assert.deepEqual(raws({}), [1630, 1620, 1540, 1460, 1450]);
  assert.deepEqual(raws({ tempo: "keep" }), [1630, 1630, 1630, 1630, 1630]);
  const near = scene(); near.b.setRaw("pattern.tempo", [], 1660);
  assert.deepEqual(makeTransitions(near.a, near.b, { count: 5 }).items.map(it => it.pattern.raw("pattern.tempo")), [1630, 1630, 1660, 1660, 1660], "a change of 5 BPM or less is one step");
  const p = pair();
  assert.deepEqual(makeTransitions(p.a, p.b, { count: 2, tempo: "ramp" }).items.map(it => it.pattern.raw("pattern.tempo")), [1530, 1570], "a third and two thirds of the way from 150 to 160 BPM, to whole BPM");
});

test("tail sweep: one filter arc in the last transition on the part that carries over", () => {
  const { a, b } = scene();
  const { items } = makeTransitions(a, b, { count: 5 });
  items.slice(0, 4).forEach(it => assert.equal(motionSlots(it.pattern).filter(m => m.dest === "cutoff").length, 0));
  const arc = motionSlots(items[4].pattern).filter(m => m.dest === "cutoff");
  assert.equal(arc.length, 1);
  assert.equal(arc[0].part, 7, "part 7 is B's densest own part, it plays on in B");
  assert.equal(items[4].pattern.raw("part.motionMode", [6]), 1);
  const v = arc[0].values;
  assert.ok(v.slice(0, 40).every(x => x === 100), "constant at the base cutoff first");
  assert.equal(Math.min(...v), 26, "from a high cutoff it goes down: base - 74");
  assert.equal(Math.max(...v), 100);
  assert.ok(v[63] > Math.min(...v), "and comes back part of the way");
  const hp = tailArc(22, 64);
  assert.equal(Math.max(...hp.values), 96, "from a low cutoff it goes up: base + 74");
  assert.equal(hp.values[63], 34);
  assert.equal(hp.values[0], 22);
  assert.equal(tailArc(120, 64).peak, 46);
  assert.equal(tailArc(22, 32).values.length, 64);
  const lonely = makeTransitions(...Object.values(pair()), { count: 2, direction: "down" });
  assert.equal(motionSlots(lonely.items[1].pattern).filter(m => m.dest === "cutoff").length, 1, "a shared part carries over when B brings none");
  const off = makeTransitions(a, b, { count: 5, sweep: "none" });
  assert.equal(motionSlots(off.items[4].pattern).filter(m => m.dest === "cutoff").length, 0);
});

test("run sweep and corner pad: the old moves still run across all transitions without a jump", () => {
  const { a, b } = pair();
  const { items } = makeTransitions(a, b, { count: 3, direction: "down", sweep: "run", pad: "corner" });
  const steps = items.map(it => audibleSteps(it.pattern));
  assert.ok(steps[0] < audibleSteps(a) && steps[1] <= steps[0] && steps[2] <= steps[1], `steps never grow: ${steps}`);
  const lead = motionOf(items[0].pattern, 3, DEST.cutoff);
  assert.ok(lead, "part 3 (highest cutoff, most notes) gets the filter sweep");
  assert.ok(lead.values[0] > lead.values[63], "closing sweep");
  items.forEach(it => assert.equal(it.pattern.raw("part.mute", [2]), 0, "the lead is never muted"));
  const c1 = motionOf(items[1].pattern, 3, DEST.cutoff);
  assert.ok(Math.abs(lead.values[63] - c1.values[0]) <= 1);
  const x0 = motionOf(items[0].pattern, 17, DEST.mfxX), x1 = motionOf(items[1].pattern, 17, DEST.mfxX);
  assert.ok(Math.abs(x0.values[63] - x1.values[0]) <= 1);
  assert.equal(motionOf(items[2].pattern, 17, DEST.mfxX).values[63], 127, "the pad ends in the corner");
  assert.equal(motionOf(items[2].pattern, 17, DEST.mfxY).values[63], 1);
  assert.equal(items[2].pattern.raw("pattern.mfx.padX"), 127);
});

test("build-up: B's parts come in by copy, parts that sound in A stay as they are", () => {
  const { a, b } = pair();
  const { items, direction } = makeTransitions(b, a, { count: 2, direction: "up", sweep: "run" });
  assert.equal(direction, "up");
  const last = summarize(items[1].pattern);
  assert.equal(summarize(b).audible, 3);
  assert.ok(last.parts[0].audible && last.parts[1].audible, "A's parts 1 and 2 came in");
  assert.equal(last.parts[0].sample, 10);
  assert.equal(last.parts[2].sample, 22, "part 3 sounds in both and keeps the sample it had");
  assert.ok(items[0].notes.some(n => /nicht kopiert/.test(n)), "the clash is reported");
  assert.ok(audibleSteps(items[1].pattern) > audibleSteps(items[0].pattern) - 1);
  const sweeps = motionSlots(items[0].pattern).filter(m => m.dest === "cutoff");
  assert.equal(sweeps.length, 1);
  assert.ok(sweeps[0].values[0] < sweeps[0].values[63], "opening sweep");
  assert.ok(summarize(b).parts[sweeps[0].part - 1].audible, "on a part that sounds");
});

test("a transition is an edit: bytes the rules do not touch stay as A had them", () => {
  const { a, b } = pair();
  for (let k = 44; k < 60; k++) a.bytes[k] = 0xa5;
  for (let i = 0; i < 16; i++) a.setRaw("part.byte38", [i], 0xa5);
  const before = Array.from(a.bytes);
  const { items } = makeTransitions(a, b, { count: 2 });
  for (const it of items) {
    assert.deepEqual([...it.pattern.bytes.subarray(44, 60)], [...a.bytes.subarray(44, 60)]);
    for (let i = 0; i < 16; i++) if (i !== 4 && i !== 5) assert.equal(it.pattern.raw("part.byte38", [i]), 0xa5, "parts that B does not replace");
    assert.equal(it.pattern.raw("pattern.swing"), a.raw("pattern.swing"));
    assert.equal(it.pattern.raw("pattern.key"), a.raw("pattern.key"));
    for (const i of [3]) assert.equal(it.pattern.raw("part.sample", [i]), a.raw("part.sample", [i]));
  }
  assert.deepEqual(Array.from(a.bytes), before, "A itself is not changed by making transitions");
});

test("every transition passes the pattern checks and survives the single file round trip", () => {
  const { a, b } = pair();
  for (const dir of ["down", "up", "blend"]) {
    const { items } = makeTransitions(a, b, { count: 3, direction: dir });
    for (const it of items) {
      assert.deepEqual(checkTransition(it.pattern, a).filter(f => f.severity === "error"), [], `${dir} ${it.name}`);
      const again = parseSinglePattern(toSinglePattern(it.pattern));
      assert.deepEqual(Array.from(again.bytes), Array.from(it.pattern.bytes));
      assert.ok(it.name.length <= 16);
    }
  }
  const s = scene();
  for (const it of makeTransitions(s.a, s.b, { count: 5 }).items) assert.deepEqual(checkTransition(it.pattern, s.a).filter(f => f.severity === "error"), [], it.name);
});

test("a step that is on without trigger is reported, a broken frame too", () => {
  const { a, b } = pair();
  const { items } = makeTransitions(a, b, { count: 1 });
  const t = items[0].pattern;
  t.setRaw("step.on", [9, 3], 1);
  assert.ok(checkTransition(t, a).some(f => /Trigger/.test(f.message)));
  t.bytes[0] = 0;
  assert.ok(checkTransition(t, a).some(f => f.severity === "error"));
});

test("chain: each transition points at the next, the last at B; chains found in a set follow it", () => {
  const { a, b } = pair();
  const { items } = makeTransitions(a, b, { count: 3, chain: true, slots: [201, 202, 203], slotB: 192 });
  assert.deepEqual(items.map(it => it.pattern.raw("pattern.chainTo")), [202, 203, 192]);
  const without = makeTransitions(a, b, { count: 2 });
  assert.deepEqual(without.items.map(it => it.pattern.raw("pattern.chainTo")), [0, 0]);
  const set = new PatternFile(new Uint8Array(0x10100), Array.from({ length: 6 }, () => blank().bytes));
  [[1, 2], [2, 3], [4, 5]].forEach(([n, to]) => { const p = set.pattern(n); p.setRaw("pattern.chainTo", [], to); set.replace(n, p); });
  assert.deepEqual(chainsOf(set), [[1, 2, 3], [4, 5]]);
});

test("no transition has an insert type A does not have, and many heavy inserts are reported", () => {
  const { a, b } = scene();
  for (const it of makeTransitions(a, b, { count: 5 }).items) for (let i = 0; i < 16; i++) assert.equal(it.pattern.raw("part.ifxType", [i]), a.raw("part.ifxType", [i]), `part ${i + 1} in ${it.name}`);
  const light = makeTransitions(a, b, { count: 2 });
  assert.deepEqual(light.heavy, [], "type 5 and 36 are not heavy");
  const quiet = describe(light, summarize(a), summarize(b), a, b, 1, 2);
  assert.ok(!/schweren Insert/.test(quiet));
  for (const i of [0, 1, 2, 3]) a.setRaw("part.ifxType", [i], 24);
  const heavy = makeTransitions(a, b, { count: 2 });
  assert.deepEqual(heavy.heavy, ["Part 1", "Part 2", "Part 3", "Part 4"]);
  assert.match(describe(heavy, summarize(a), summarize(b), a, b, 1, 2), /4 Parts mit schweren Insert-Typen \(Part 1, Part 2, Part 3, Part 4\)/);
});

test("effectChanges counts a part whose insert flag or type differs, and the master type", () => {
  const x = blank(), y = blank();
  assert.deepEqual(effectChanges(x, y), []);
  y.setRaw("part.ifxType", [3], 12);
  y.setRaw("part.ifxOn", [9], 1);
  y.setRaw("part.ifxEdit", [5], 99);
  y.setRaw("pattern.mfx.type", [], 4);
  assert.deepEqual(effectChanges(x, y), ["Part 4", "Part 10", "Master"], "an edit value alone is not an effect change");
});

test("the command line takes two single pattern files and writes the transitions next to a summary", () => {
  const { a, b } = scene();
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-transition-"));
  writeFileSync(join(dir, "a.e2spat"), toSinglePattern(a));
  writeFileSync(join(dir, "b.e2spat"), toSinglePattern(b));
  const log = console.log;
  console.log = () => {};
  try {
    assert.equal(main(["--a-file", join(dir, "a.e2spat"), "--b-file", join(dir, "b.e2spat"), "--slots", "214,215,216", "--slot-b", "219", "--chain", "--label", "G219", "--out", join(dir, "out")]), 0);
  } finally { console.log = log; }
  const files = readdirSync(join(dir, "out")).sort();
  assert.deepEqual(files.filter(f => f.endsWith(".e2spat")), ["T1_214_PREG2190.e2spat", "T2_215_PREG2191.e2spat", "T3_216_PREG2192.e2spat"]);
  const last = parseSinglePattern(readFileSync(join(dir, "out", "T3_216_PREG2192.e2spat")));
  assert.equal(last.raw("pattern.chainTo"), 219);
  assert.match(readFileSync(join(dir, "out", "UEBERSICHT.txt"), "utf8"), /Wechsel in B: Effekt-Wechsel in 4 Slots/);
});

test("pickSlots takes the first run of free patterns above A, else any free ones", () => {
  const file = makePatternFile(10);
  const set = PatternFile.parse(file);
  for (let n = 1; n <= 10; n++) {
    const p = blank(`P${n}`);
    if (![3, 4, 5, 9].includes(n)) addPart(p, 0, { sample: n, steps: [0, 4] });
    set.replace(n, p);
  }
  assert.deepEqual(pickSlots(set, 2, 1), [3, 4]);
  assert.deepEqual(pickSlots(set, 2, 4), [3, 4]);
  assert.deepEqual(pickSlots(set, 3, 5), [3, 4, 5]);
  assert.deepEqual(onSteps(set.pattern(3), 0), []);
});

test("names: the generated name, a name of your own, and one nobody can show falls back", () => {
  const { a, b } = pair();
  assert.deepEqual(makeTransitions(a, b, { count: 3 }).items.map(i => i.name), ["PREB side0", "PREB side1", "PREB side2"]);
  const named = makeTransitions(a, b, { count: 3, names: ["Intro Build", "", "☃"] }).items;
  assert.deepEqual(named.map(i => i.name), ["Intro Build", "PREB side1", "PREB side2"]);
  assert.equal(named[0].pattern.name, "Intro Build");
});
