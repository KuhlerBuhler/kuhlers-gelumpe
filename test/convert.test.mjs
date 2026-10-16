import { test } from "node:test";
import assert from "node:assert/strict";
import { CONVERTERS, converter, noteLabel } from "../src/map/convert.mjs";

const raws = c => {
  const out = [];
  for (let r = c.domain[0]; r <= c.domain[1]; r++) if (!c.valid || c.valid(r)) out.push(r);
  return out;
};

// Several bytes can share one plain value, so a round trip may land on a
// different byte. What must hold is that it lands on the same plain value.
// For every raw value: either a stable round trip, or a refusal for a value
// the converter cannot write. Never a silent change.
test("every converter round-trips stably or refuses, for every raw value", () => {
  for (const c of Object.values(CONVERTERS)) {
    for (let r = c.domain[0]; r <= c.domain[1]; r++) {
      const v = c.fromRaw(r);
      let back;
      try { back = c.toRaw(v); } catch (e) {
        assert.ok(e instanceof RangeError, `${c.name}: raw ${r} threw ${e}`);
        assert.ok(c.choices && !c.choices.some(x => x.raw === r), `${c.name}: refused raw ${r}, which it names`);
        continue;
      }
      if (c.valid && !c.valid(r)) continue;
      assert.deepEqual(c.fromRaw(back), v, `${c.name}: raw ${r}`);
    }
  }
});

test("what a converter cannot write it refuses, and gates outside Korg's range land on 96", () => {
  assert.throws(() => converter("fxSource").toRaw(0x48), RangeError);
  assert.throws(() => converter("fxChain").toRaw(0x05), RangeError);
  assert.equal(converter("gateTime").toRaw(100), 96);
  assert.throws(() => converter("cutoffHz").toRaw("abc"), RangeError);
  assert.throws(() => converter("plain").toRaw(NaN), RangeError);
  assert.equal(converter("oscPitchCents").format(-100), "unbekannt (-100)");
});

test("every converter formats every raw value in its domain", () => {
  for (const c of Object.values(CONVERTERS)) {
    for (const r of raws(c)) assert.equal(typeof c.format(r), "string", `${c.name}: raw ${r}`);
  }
});

const near = (actual, expected, tolerance) =>
  assert.ok(Math.abs(actual - expected) <= tolerance * expected, `${actual} is not within ${tolerance * 100}% of ${expected}`);

test("cutoff hits the measured points (measure:2026-09-17/cutoff-resonance-peak)", () => {
  const c = converter("cutoffHz");
  // The measurement gives "at most 10 percent" for the formula; at 120 it is 10.01.
  for (const [raw, hz] of [[16, 41], [48, 263], [64, 652], [84, 2106]]) near(c.fromRaw(raw), hz, 0.1);
  near(c.fromRaw(120), 14739, 0.101);
  near(c.fromRaw(64), 652, 0.01);
  assert.equal(c.format(64), "654 Hz");
});

test("osc pitch hits the measured corner points (measure:2026-09-17/osc-pitch)", () => {
  const c = converter("oscPitchCents");
  for (const [raw, cents] of [[14, 100], [17, 200], [24, 600], [48, 1200], [63, 2400]]) {
    assert.equal(c.fromRaw(raw), cents);
    assert.equal(c.fromRaw(-raw), -cents);
  }
  assert.equal(c.format(48), "+1 Okt.");
  assert.equal(c.format(-14), "-1 Halbt.");
});

test("a value between table entries lands on the nearest one", () => {
  const pitch = converter("oscPitchCents");
  assert.equal(pitch.toRaw(110), 14);
  assert.equal(pitch.toRaw(1190), 48);
  const speed = converter("modSpeed");
  assert.equal(speed.format(60), "1/4");
  assert.equal(speed.toRaw(speed.fromRaw(60)), 56);
  const cutoff = converter("cutoffHz");
  assert.equal(cutoff.toRaw(652), 64);
});

test("envelope, glide and resonance follow the measurements", () => {
  near(converter("envTime").fromRaw(64), 490, 0.01);
  near(converter("envTime").fromRaw(127), 5300, 0.01);
  assert.equal(converter("envTime").format(4), "unter 30 ms");
  near(converter("glideMs").fromRaw(64), 321, 0.01);
  assert.equal(converter("glideMs").format(0), "aus");
  assert.equal(converter("resonanceDb").fromRaw(64), 12.5);
  assert.equal(converter("resonanceDb").format(127), "Selbstoszillation");
});

test("notes: 60 is C4, and a step slot stores the note plus one", () => {
  assert.equal(noteLabel(60), "C4");
  assert.equal(noteLabel(0), "C-1");
  const slot = converter("stepNote");
  assert.equal(slot.format(61), "C4");
  assert.equal(slot.format(0), "leer");
  assert.equal(slot.toRaw(60), 61);
  assert.equal(slot.toRaw(null), 0);
});

test("a list refuses what is not on it and names what it does not know", () => {
  const beat = converter("beat");
  assert.throws(() => beat.toRaw(7), /not a choice/);
  assert.equal(beat.format(9), "unbekannt (9)");
  assert.equal(converter("filterType").format(1), "electribe LPF");
  assert.equal(converter("filterType").format(3), "Hacktribe-Filter 3");
  assert.equal(converter("fxSource").format(0x43), "Y");
  assert.equal(converter("fxChain").format(0x05), "unbekannt (5)");
});

test("bipolar and stored-upside-down values read the right way round", () => {
  assert.equal(converter("bipolar63").format(63), "Mitte (Ruhepunkt)");
  assert.equal(converter("bipolar63").fromRaw(0), -63);
  assert.equal(converter("playLevel").fromRaw(127), 0);
  assert.equal(converter("pan").format(-63), "L63");
  assert.equal(converter("gateTime").format(255), "unbekannt (255)");
});

test("an effect parameter with a negative table minimum shows the byte minus that minimum", () => {
  const c = converter("fxShift36");
  assert.equal(c.fromRaw(36), 0);
  assert.equal(c.format(36), "0");
  assert.equal(c.format(72), "+36");
  assert.equal(c.format(0), "-36");
  assert.equal(c.toRaw(-36), 0);
});

test("a time ratio shows the DSP's label and writes back the first byte that holds the same ratio", () => {
  const c = converter("timeRatio");
  assert.equal(c.format(0), "0.5%");
  assert.equal(c.format(127), "400.0%");
  assert.equal(c.fromRaw(65), 100);
  assert.equal(c.toRaw(100), 61);
  assert.equal(converter("looperStep").format(9), "0.0");
});
