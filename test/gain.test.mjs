import { render } from "../src/text.mjs";
import { test } from "node:test";
import assert from "node:assert/strict";
import { makePattern, makeRecord } from "./helpers.mjs";
import { Pattern } from "../src/pattern.mjs";
import { loadUnits } from "../src/units.mjs";
import { lint } from "../src/rules.mjs";
import { judgeOutput, outputLevels, readLevels, planScale, applyScale } from "../src/gain.mjs";

const units = loadUnits();
const codes = (record, profile = null) => lint(record, { units, profile }).filter(f => /^output-/.test(f.code)).map(f => f.code);

/** A pattern whose part levels and play level we set, everything else filler. */
function pattern(levels = [], playLevel = 100) {
  const p = new Pattern(makePattern());
  p.setRaw("pattern.playLevel", [], 127 - playLevel);
  for (let part = 0; part < 16; part++) p.setRaw("part.level", [part], levels[part] ?? 0);
  return p;
}

test("the play level is stored upside down and read the way the device shows it", () => {
  const levels = readLevels(pattern([], 100));
  assert.equal(levels.master.value, 100);
});

test("the levels of a pattern: sixteen parts, mute and the insert the part asks for", () => {
  const p = pattern([90, 60]);
  p.setRaw("part.mute", [1], 1);
  p.setRaw("part.ifxOn", [0], 1);
  p.setRaw("part.ifxType", [0], 11);
  p.setRaw("part.ifxOn", [1], 0);
  const { parts } = readLevels(p);
  assert.equal(parts.length, 16);
  assert.deepEqual([parts[0].value, parts[1].value, parts[2].value], [90, 60, 0]);
  assert.equal(parts[0].ifx, 12, "the menu counts from one, the byte from zero");
  assert.equal(parts[1].muted, true);
  assert.equal(parts[1].ifx, null);
});

test("a factor moves every level and keeps the balance", () => {
  const plan = planScale(readLevels(pattern([100, 50, 25])), { mode: "factor", value: 0.5 });
  assert.deepEqual(plan.rows.slice(0, 3).map(r => r.after), [50, 25, 13]);
  assert.equal(plan.limited, false);
  assert.equal(plan.changed, true);
  assert.equal(plan.peakAfter, 50);
});

test("a target makes the loudest part that value and scales the rest by the same factor", () => {
  const plan = planScale(readLevels(pattern([100, 50, 25])), { mode: "target", value: 80 });
  assert.deepEqual(plan.rows.slice(0, 3).map(r => r.after), [80, 40, 20]);
  assert.equal(plan.factor, 0.8);
});

test("a factor that would clip the loudest level is held back so the balance survives", () => {
  const plan = planScale(readLevels(pattern([100, 50])), { mode: "factor", value: 2 });
  assert.equal(plan.limited, true);
  assert.equal(plan.requested, 2);
  assert.deepEqual(plan.rows.slice(0, 2).map(r => r.after), [127, 64]);
});

test("a quiet level never rounds down to silence, and silence stays silence", () => {
  const plan = planScale(readLevels(pattern([100, 1, 0])), { mode: "factor", value: 0.1 });
  assert.deepEqual(plan.rows.slice(0, 3).map(r => r.after), [10, 1, 0]);
});

test("the play level takes part only when asked", () => {
  const levels = readLevels(pattern([100], 80));
  const without = planScale(levels, { value: 0.5 });
  assert.equal(without.rows.some(r => r.id === "pattern.playLevel"), false);
  const withMaster = planScale(levels, { value: 0.5, master: true });
  assert.equal(withMaster.rows.find(r => r.id === "pattern.playLevel").after, 40);
});

test("nonsense is refused with a reason, nothing is planned", () => {
  const levels = readLevels(pattern([100]));
  for (const value of [0, -1, NaN, "abc"]) assert.ok(planScale(levels, { value }).error, String(value));
  assert.ok(planScale(levels, { mode: "target", value: 200 }).error);
  assert.equal(render(planScale(readLevels(pattern([])), { mode: "target", value: 50 }).error), "Alle Pegel stehen auf 0, daraus lässt sich kein Faktor ableiten.");
});

test("applying a plan writes the levels and nothing else, and undo puts every byte back", () => {
  const p = pattern([100, 50, 25], 90);
  const before = Uint8Array.from(p.bytes);
  const plan = planScale(readLevels(p), { value: 0.5, master: true });
  const changes = applyScale(p, plan);
  const touched = [...p.bytes.keys()].filter(i => p.bytes[i] !== before[i]);
  const expected = new Set([Pattern.offset("pattern.playLevel"), ...[0, 1, 2].map(k => Pattern.offset("part.level", [k]))]);
  assert.deepEqual(new Set(touched), expected);
  assert.equal(readLevels(p).master.value, 45);
  for (const c of [...changes].reverse()) p.undo(c);
  assert.deepEqual(p.bytes, before);
});

test("a plan that changes nothing writes nothing", () => {
  const p = pattern([100]);
  const before = Uint8Array.from(p.bytes);
  const plan = planScale(readLevels(p), { value: 1 });
  assert.equal(plan.changed, false);
  assert.deepEqual(applyScale(p, plan), []);
  assert.deepEqual(p.bytes, before);
});

test("the output levels of a record are found by name", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  r.setParams(units, "ifx1", { output_gain: 33 });
  const found = outputLevels(r, units);
  assert.deepEqual(found.map(f => [f.stage, f.param, f.value]), [["ifx1", "output_gain", 33]]);
});

test("playable levels are quiet, the gap between playable and too loud is untested, the heard cases say so", () => {
  assert.equal(judgeOutput(0x0f, "output_level", 38), null);
  assert.equal(judgeOutput(0x0f, "output_level", 60), null);
  const gap = judgeOutput(0x0f, "output_level", 75);
  assert.equal(gap.code, "output-above-usable");
  assert.match(gap.message, /Untested/);
  const loud = judgeOutput(0x0f, "output_level", 124);
  assert.equal(loud.code, "output-too-loud");
  assert.equal(loud.measured, true);
  assert.match(loud.message, /unplayably loud/);
  const gain = judgeOutput(0x15, "output_gain", 95);
  assert.equal(gain.measured, true);
  assert.match(gain.message, /every knob position/);
  assert.equal(judgeOutput(0x0a, "output_level", 100).measured, false, "another unit has no measurement, only the ceiling");
  assert.equal(judgeOutput(0x15, "frequency", 120), null);
});

test("what Korg's own presets of the unit reach is not called too loud", () => {
  assert.equal(judgeOutput(0x09, "output_level", 127, { max: 127 }), null);
  assert.equal(judgeOutput(0x09, "output_level", 127, { max: 100 }).code, "output-too-loud");
});

test("the linter warns before the measured cases, as a warning and not an error", () => {
  const distortion = makeRecord("ifx", { devices: { ifx1: 0x0f } });
  distortion.setParams(units, "ifx1", { output_level: 124 });
  const found = lint(distortion, { units }).find(f => f.code === "output-too-loud");
  assert.equal(found.severity, "warn");
  assert.match(found.message, /Heard on hardware/);

  const modulator = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  modulator.setParams(units, "ifx1", { output_gain: 95 });
  assert.match(lint(modulator, { units }).find(f => f.code === "output-too-loud").message, /every knob position/);
});

test("the usable range is quiet, the untested range between is a warning that says so", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x0f } });
  r.setParams(units, "ifx1", { output_level: 45 });
  assert.deepEqual(codes(r), []);
  r.setParams(units, "ifx1", { output_level: 80 });
  const found = lint(r, { units }).find(f => f.code === "output-above-usable");
  assert.equal(found.severity, "warn");
  assert.match(found.message, /Untested/);
  assert.equal(codes(r).includes("output-too-loud"), false);
});

test("with a profile, a value the factory presets of the unit reach is left alone", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x09 } });
  r.setParams(units, "ifx1", { output_level: 127 });
  assert.deepEqual(codes(r), ["output-too-loud"]);
  const profile = { params: { "ifx:0x09:output_level": { samples: 2, min: 127, max: 127, enum: null } } };
  assert.deepEqual(codes(r, profile), []);
});
