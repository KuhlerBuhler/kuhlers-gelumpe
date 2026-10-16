import { test } from "node:test";
import assert from "node:assert/strict";
import { makeRecord } from "./helpers.mjs";
import { loadUnits } from "../src/units.mjs";
import { REC } from "../src/layout.mjs";
import { lint } from "../src/rules.mjs";
import { lintCheck } from "../src/gate.mjs";
import { suggestion, suggestionsFor, applySuggestion, refusal } from "../src/suggestions.mjs";
import SUGGESTIONS from "../data/suggestions.mjs";
import RANGES from "../data/map/fx-ranges.mjs";

const units = loadUnits();
const reverb = suggestion("pseudoReverb");

/** A short delay record with filler in every byte nobody decoded. */
const delay = (devices = { ifx1: 0x18 }) => makeRecord("ifx", { devices, params: { ifx1: [120, 30, 127, 0, 65, 24, 35, 17, 36, 0, 0, 15] } });

test("every suggestion names a unit that has the parameters, inside the range the table allows", () => {
  for (const s of SUGGESTIONS) {
    const unit = units.ifx.get(s.unit);
    assert.ok(unit, `${s.id}: unit ${s.unit}`);
    for (const [name, value] of Object.entries(s.params)) {
      const p = unit.params.find(x => x.name === name);
      assert.ok(p, `${s.id}: ${unit.unit} has no ${name}`);
      const [min, max] = RANGES.units[`0x${s.unit.toString(16).padStart(2, "0")}`][p.index];
      assert.ok(value >= min && value <= max, `${s.id}: ${name} ${value} outside ${min} to ${max}`);
    }
    assert.equal(s.untested, true, `${s.id}: not heard on hardware, and says so`);
  }
});

test("the pseudo reverb sets its parameters on the record and touches no other byte", () => {
  const record = delay();
  const before = Uint8Array.from(record.bytes);
  const changes = applySuggestion(record, reverb, units);
  assert.deepEqual(changes.map(c => c.param).sort(), Object.keys(reverb.params).sort());

  const unit = units.ifx.get(0x18);
  const at = name => REC.stage.ifx1.params + 2 * unit.params.find(p => p.name === name).index;
  const allowed = new Set(Object.keys(reverb.params).map(at));
  const touched = [...record.bytes.keys()].filter(i => record.bytes[i] !== before[i]);
  assert.ok(touched.length > 0);
  for (const i of touched) assert.ok(allowed.has(i), `byte ${i} changed but is not a suggested parameter`);
  for (const [name, value] of Object.entries(reverb.params)) assert.equal(record.bytes[at(name)], value, name);
});

test("the result passes the linter without a finding", () => {
  const record = delay();
  applySuggestion(record, reverb, units);
  const found = lint(record, { units }).filter(f => f.where === "ifx1" || f.code.startsWith("output") || f.code.startsWith("feedback"));
  assert.deepEqual(found.map(f => f.code), []);
});

test("short delay in stage 2 is fatal, and the suggestion refuses to go there", async () => {
  const record = delay({ ifx1: 0x0a, ifx2: 0x18 });
  const found = lint(record, { units }).find(f => f.code === "stage2-fatal");
  assert.equal(found.severity, "fatal");
  assert.match(refusal(record, reverb), /Stufe 2/);
  assert.throws(() => applySuggestion(record, reverb, units), /Stufe 2/);

  // The gate reads the same rule, so a send of that record is blocked as fatal.
  const edit = { kind: "fxRecord", table: "ifx", slot: 60, bytes: record.bytes, before: null };
  const gated = await lintCheck(edit, { units, profile: null });
  assert.equal(gated.find(f => f.code === "stage2-fatal").severity, "fatal");
});

test("the suggestion also refuses a record that is not a short delay, or has a second stage behind it", () => {
  assert.match(refusal(makeRecord("ifx", { devices: { ifx1: 0x0a } }), reverb), /Baustein/);
  assert.match(refusal(makeRecord("mfx", { devices: { mfx: 0x3b } }), reverb), /Insert/);
  assert.match(refusal(delay({ ifx1: 0x18, ifx2: 0x06 }), reverb), /zweite Stufe/);
  assert.equal(refusal(delay(), reverb), null);
  assert.deepEqual(suggestionsFor(delay()).map(s => s.refusal), [null]);
});
