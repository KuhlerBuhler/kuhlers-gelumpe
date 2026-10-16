import { test } from "node:test";
import assert from "node:assert/strict";
import { makeRecord } from "./helpers.mjs";
import { loadUnits } from "../src/units.mjs";
import { lint } from "../src/rules.mjs";

const units = loadUnits();
const codes = record => lint(record, { units }).map(f => f.code);
const has = (record, code) => codes(record).includes(code);

test("a unit that kills the sound in stage two is fatal", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x15, ifx2: 0x18 } });
  const found = lint(r, { units }).find(f => f.code === "stage2-fatal");
  assert.ok(found);
  assert.equal(found.severity, "fatal");
});

test("a unit that goes quiet in stage two is reported as silent, not fatal", () => {
  // Two different faults that look identical on the device: it either stops
  // responding, or it responds and makes no sound.
  const r = makeRecord("ifx", { devices: { ifx1: 0x0a, ifx2: 0x16 } });
  const found = lint(r, { units }).find(f => f.code === "stage2-silent");
  assert.equal(found.severity, "silent");
});

test("proven combinations pass", () => {
  for (const [first, second] of [[0x10, 0x06], [0x0a, 0x0a], [0x0a, 0x10]]) {
    const r = makeRecord("ifx", { devices: { ifx1: first, ifx2: second } });
    assert.equal(has(r, "stage2-fatal"), false);
    assert.equal(has(r, "stage2-silent"), false);
    assert.equal(has(r, "stage2-untested"), false);
    assert.equal(has(r, "stage1-needs-solo"), false);
  }
});

test("a ring modulator with a second stage behind it is silent, not a crash", () => {
  // Heard 2026-09-21, two independent builds of 0x16 -> 0x0a.
  const r = makeRecord("ifx", { devices: { ifx1: 0x16, ifx2: 0x0a } });
  const found = lint(r, { units }).find(f => f.code === "stage1-needs-solo");
  assert.equal(found.severity, "silent");
  const decimator = lint(makeRecord("ifx", { devices: { ifx1: 0x09, ifx2: 0x0a } }), { units })
    .find(f => f.code === "stage1-needs-solo");
  assert.equal(decimator.severity, "fatal");
});

test("an untried second stage is flagged as untried, not as broken", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x16, ifx2: 0x11 } });
  const found = lint(r, { units }).find(f => f.code === "stage2-untested");
  assert.equal(found.severity, "warn");
});

test("the decimator with anything behind it is fatal", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x09, ifx2: 0x0a } });
  assert.ok(has(r, "stage1-needs-solo"));
  const alone = makeRecord("ifx", { devices: { ifx1: 0x09 } });
  assert.equal(has(alone, "stage1-needs-solo"), false);
});

test("a master unit inside an insert chain is fatal", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x36 } });
  const found = lint(r, { units }).find(f => f.code === "master-unit-in-insert");
  assert.equal(found.severity, "fatal");
});

test("a master preset carrying a second unit is wrong", () => {
  const r = makeRecord("mfx", { devices: { mfx: 0x3b } });
  r.setDevice("ifx1", 0x0a);
  assert.ok(has(r, "master-extra-stage"));
});

test("the touchpad does not reach an insert preset", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x16 } });
  r.map = [{ source: 0x43, chain: 0, param: 0, low: 0, high: 100 }];
  const found = lint(r, { units }).find(f => f.code === "map-source-unavailable");
  assert.equal(found.severity, "error");
});

test("a map row reaching past the end of the parameter list is caught", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x0a } });   // four parameters
  r.map = [{ source: 0x42, chain: 0, param: 9, low: 0, high: 100 }];
  assert.ok(has(r, "map-param-out-of-range"));
});

test("a row pointing at an empty stage is caught", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x16 } });
  r.map = [{ source: 0x42, chain: 1, param: 0, low: 0, high: 100 }];
  assert.ok(has(r, "map-chain-empty"));
});

test("a control that leaves the effect on at rest is flagged", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x16 } });
  r.setParams(units, "ifx1", { dry_wet: 100 });
  r.map = [{ source: 0x45, chain: 0, param: 1, low: 5, high: 60 }];  // osc_freq only
  assert.ok(has(r, "rest-not-silent"));
});

test("putting the mix on the control clears that", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x16 } });
  r.setParams(units, "ifx1", { dry_wet: 100 });
  r.map = [
    { source: 0x45, chain: 0, param: 0, low: 0, high: 100 },
    { source: 0x45, chain: 0, param: 1, low: 5, high: 60 },
  ];
  assert.equal(has(r, "rest-not-silent"), false);
});

test("a value the factory never uses is flagged when a profile is supplied", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  r.setParams(units, "ifx1", { output_gain: 95 });
  const profile = { params: { "ifx:0x15:output_gain": { samples: 4, min: 32, max: 36, enum: null } } };
  const found = lint(r, { units, profile }).find(f => f.code === "value-outside-factory-range");
  assert.match(found.message, /95/);
  assert.match(found.message, /32 and 36/);
});

test("an invented choice on a parameter that is a list is an error", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  r.setParams(units, "ifx1", { level_mod_source: 7 });
  const profile = { params: { "ifx:0x15:level_mod_source": { samples: 4, min: 0, max: 4, enum: [0, 2, 3] } } };
  const found = lint(r, { units, profile }).find(f => f.code === "value-not-in-factory-set");
  assert.equal(found.severity, "error");
});

test("a master preset with nothing to fade it in is silent", () => {
  const r = makeRecord("mfx", { devices: { mfx: 0x3b } });
  r.map = [{ source: 0x42, chain: 2, param: 9, low: 60, high: 4 }];
  const found = lint(r, { units }).find(f => f.code === "no-switch-on-fade");
  assert.equal(found.severity, "silent");
});

test("either way of fading it in counts", () => {
  const crossfade = makeRecord("mfx", { devices: { mfx: 0x3b } });
  crossfade.map = [
    { source: 0x41, chain: 0x0a, param: 4, low: 127, high: 0 },
    { source: 0x41, chain: 0x0a, param: 0, low: 0, high: 127 },
  ];
  assert.equal(has(crossfade, "no-switch-on-fade"), false);

  // An axis reads zero until it is touched, so opening the input from zero
  // works just as well. Korg does it in ten of its own presets.
  const inputFade = makeRecord("mfx", { devices: { mfx: 0x3b } });
  inputFade.map = [{ source: 0x43, chain: 0x07, param: 5, low: 0, high: 88 }];
  assert.equal(has(inputFade, "no-switch-on-fade"), false);
});

test("the mute unit has nothing to fade and is left alone", () => {
  const r = makeRecord("mfx", { devices: { mfx: 0x27 } });
  r.map = [];
  assert.equal(has(r, "no-switch-on-fade"), false);
});

test("an insert record in the master table is caught before it goes quiet", () => {
  const r = makeRecord("mfx", { devices: { ifx1: 0x16 } });
  const found = lint(r, { units }).find(f => f.code === "wrong-table");
  assert.equal(found.severity, "silent");
});

test("an output level near the ceiling is flagged", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  r.setParams(units, "ifx1", { output_gain: 95 });
  assert.ok(has(r, "output-too-loud"));
});

test("runaway feedback is flagged", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x18 } });
  r.setParams(units, "ifx1", { fb_depth: 120 });
  assert.ok(has(r, "feedback-runs-away"));
});

test("an enum is noted as unchecked when there is no profile to check it against", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  const found = lint(r, { units }).find(f => f.code === "enum-unchecked");
  assert.equal(found.severity, "note");
});

test("the quiet point of a bipolar depth is the middle, not zero", () => {
  // level_mod_int at 0 and at 127 both modulate, in opposite directions, and
  // Korg's own Pumper maps the knob from 63 upwards. A check that treats 0 as
  // off is wrong about the one unit it was written for.
  const idx = units.ifx.get(0x15).params.find(p => p.name === "level_mod_int").index;

  const centred = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  centred.setParams(units, "ifx1", { level_mod_int: 63 });
  centred.map = [{ source: 0x42, chain: 0, param: idx, low: 63, high: 126 }];
  assert.equal(has(centred, "rest-not-silent"), false);

  const fromZero = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  fromZero.map = [{ source: 0x42, chain: 0, param: idx, low: 0, high: 126 }];
  const found = lint(fromZero, { units }).find(f => f.code === "rest-not-silent");
  assert.match(found.message, /bipolar/);
});

test("a value Korg itself uses is not called invented", () => {
  // level_mod_source 4 was blamed for a device-wide silence. The factory
  // preset on IFX 36 ships with 4 and works, so the blame was misplaced.
  const r = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  r.setParams(units, "ifx1", { level_mod_source: 4 });
  const profile = { params: { "ifx:0x15:level_mod_source": { samples: 4, min: 0, max: 4, enum: [0, 3, 4] } } };
  assert.equal(lint(r, { units, profile }).some(f => f.code === "value-not-in-factory-set"), false);
});

test("a modulator with no play row is flagged as free-running", () => {
  const idx = units.ifx.get(0x15).params.find(p => p.name === "lfo_reset").index;

  const free = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  free.setParams(units, "ifx1", { lfo_reset: 1 });   // the value alone does nothing
  assert.ok(has(free, "no-play-row"));

  const synced = makeRecord("ifx", { devices: { ifx1: 0x15 } });
  synced.map = [{ source: 0x4a, chain: 0, param: idx, low: 0, high: 1 }];
  assert.equal(has(synced, "no-play-row"), false);
});
