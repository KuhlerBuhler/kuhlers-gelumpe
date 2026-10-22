import { test } from "node:test";
import assert from "node:assert/strict";
import { readUnits } from "../src/node.mjs";
import { FxRecord } from "../src/record.mjs";
import { presetFile } from "../src/preset-file.mjs";
import { fxText, readFx, fxFromRecord, fxToRecord, modFromType } from "../src/fx-v2.mjs";
import { buildCollection, parseCollection, collectionEntry, HEADER_SIZE, MOD_RECORD } from "../src/fx-collection.mjs";
import { locateModTable, readModType } from "../src/modtable.mjs";
import { recordOf, RECORD } from "../src/presets.mjs";
import { makeRecord, makeFirmwareWithArrays } from "./helpers.mjs";

const units = readUnits();
const MOD_DELAY = 0x3b;
const TAPE_ECHO = 0x3c;

/** The Short Delay of the author's ESX, as plain values (own values, no firmware bytes). */
const shortDelay = () => ({
  kind: "mfx", name: "Short Delay",
  stages: [{ stage: "mfx", unit: MOD_DELAY, unitName: "M_mod_delay", params: { dry_wet: 122, wet_spread: 100, off_l_delay_time: 19, off_r_delay_time: 21, fb_depth: 0 } }],
  map: [{ source: 65, chain: 2, param: 0, low: 45, high: 122 }, { source: 67, chain: 2, param: 15, low: 0, high: 127 }],
});

test("a v2 preset is plain values with a checksum: it reads back the same, and a changed value breaks it", () => {
  const text = fxText(shortDelay());
  assert.doesNotMatch(text, /record/, "no firmware bytes in the file");
  const read = readFx(text, units);
  assert.equal(read.ok, true, read.reason);
  assert.deepEqual(read.preset.stages[0].params, shortDelay().stages[0].params);
  assert.equal(fxText(read.preset), text, "the same preset gives the same text");
  const broken = readFx(text.replace('"dry_wet": 122', '"dry_wet": 121'), units);
  assert.equal(broken.ok, false);
  assert.match(broken.reason, /Prüfsumme/);
  assert.equal(readFx("{}", units).ok, false);
});

test("a record becomes v2 by unit id and parameter names; written back over another record it gives the same values", () => {
  const source = makeRecord("mfx", { name: "Short Delay", devices: { mfx: MOD_DELAY }, params: { mfx: [122, 100, 95] } });
  source.map = shortDelay().map;
  const preset = fxFromRecord(source, "mfx", units);
  assert.equal(preset.stages[0].unit, MOD_DELAY);
  assert.equal(preset.stages[0].unitName, "M_mod_delay");
  assert.equal(preset.stages[0].params.dry_wet, 122);
  const base = makeRecord("mfx", { name: "Other", devices: { mfx: MOD_DELAY } });
  const made = fxToRecord(preset, base.bytes, [], units);
  assert.equal(made.ok, true, made.reason);
  assert.deepEqual(fxFromRecord(new FxRecord(made.record, "mfx"), "mfx", units), preset);
});

test("a building block the slot does not have comes from a donor record of the same firmware, never from zeros", () => {
  const preset = shortDelay();
  const base = makeRecord("mfx", { name: "Echo", devices: { mfx: TAPE_ECHO } });
  const donor = makeRecord("mfx", { name: "Delay", devices: { mfx: MOD_DELAY } });
  const refused = fxToRecord(preset, base.bytes, [base.bytes], units);
  assert.equal(refused.ok, false);
  assert.match(refused.reason, /M_mod_delay steht in dieser Firmware in keinem Preset/);
  const made = fxToRecord(preset, base.bytes, [base.bytes, donor.bytes], units);
  assert.equal(made.ok, true, made.reason);
  const rec = new FxRecord(made.record, "mfx");
  assert.equal(rec.device("mfx"), MOD_DELAY);
  assert.equal(rec.name, "Short Delay");
  const wrongName = fxToRecord({ ...preset, stages: [{ ...preset.stages[0], params: { nope: 1 } }] }, donor.bytes, [], units);
  assert.match(wrongName.reason, /keinen Parameter nope/);
});

test("a version 1 file reads as v2", () => {
  const rec = makeRecord("ifx", { name: "Gate Filter", devices: { ifx1: 0x0a }, params: { ifx1: [1, 2, 3] } });
  const read = readFx(presetFile("ifx", rec.bytes), units);
  assert.equal(read.ok, true, read.reason);
  assert.deepEqual(read.preset, fxFromRecord(rec, "ifx", units));
});

test("the collection holds each entry's data and its v2 text; any damage, the wrong build or a bad index is refused", () => {
  const data = new Uint8Array(RECORD).fill(7);
  const mod = new Uint8Array(MOD_RECORD).fill(9);
  const file = buildCollection({ build: "hacktribe", entries: [
    { kind: "mfx", index: 0, data, text: fxText(shortDelay()) },
    { kind: "mod", index: 3, data: mod, text: "{}" },
  ] });
  assert.equal(file.length % 4, 0);
  const read = parseCollection(file, { counts: { ifx: 100, mfx: 32 } });
  assert.equal(read.ok, true, read.reason);
  assert.equal(read.build, "hacktribe");
  assert.deepEqual(read.entries.map(e => [e.kind, e.index, e.data.length]), [["mfx", 0, RECORD], ["mod", 3, MOD_RECORD]]);
  assert.equal(readFx(read.entries[0].text, units).ok, true);
  const flip = at => { const b = Uint8Array.from(file); b[at] ^= 1; return parseCollection(b).ok; };
  assert.equal(flip(HEADER_SIZE + 20), false, "a changed byte breaks the checksum");
  assert.equal(parseCollection(file.slice(0, -4)).ok, false, "a short file");
  const other = Uint8Array.from(file);
  new DataView(other.buffer).setUint32(16, 9, true);
  assert.equal(parseCollection(other).ok, false, "an unknown build");
  assert.match(parseCollection(file, { counts: { ifx: 100, mfx: 0 } }).reason, /Platz 1/);
  assert.throws(() => buildCollection({ build: "synth", entries: [] }));
  assert.throws(() => buildCollection({ build: "stock", entries: [{ kind: "mfx", index: 0, data: new Uint8Array(10), text: "" }] }));
});

test("an entry for the user's firmware: the preset over its slot, the modulation over its type, the rest of the bytes kept", async () => {
  const vsb = await makeFirmwareWithArrays([
    { kind: "mfx", slot: 1, record: makeRecord("mfx", { name: "Mod Delay", devices: { mfx: MOD_DELAY } }) },
  ]);
  const made = collectionEntry(shortDelay(), vsb, 0, units);
  assert.equal(made.ok, true, made.reason);
  const at = recordOf(vsb, "mfx", 1);
  const before = vsb.slice(at.file, at.file + RECORD);
  const rec = new FxRecord(made.entry.data, "mfx");
  assert.equal(rec.name, "Short Delay");
  assert.equal(rec.paramAt("mfx", 0), 122);
  const changed = [...made.entry.data].filter((b, i) => b !== before[i]).length;
  assert.ok(changed > 0 && changed < 64, `only the values the preset sets change: ${changed} bytes`);
  const table = locateModTable(vsb);
  const type = modFromType({ ...readModType(vsb, table.file, 3), depth: 77 });
  const mod = collectionEntry(type, vsb, 3, units);
  assert.equal(mod.ok, true, mod.reason);
  assert.equal(readModType(mod.entry.data, 0, 0).depth, 77);
  assert.equal(collectionEntry(shortDelay(), vsb, 200, units).ok, false);
});

test("a modulation type reads back with negative strengths, and out of range values are refused", () => {
  const type = { kind: "mod", name: "Wobble", depth: 64, speed: 40, curve: 6, slots: [{ source: 1, target: 3, lo: -20, hi: 30, follow: 1 }, ...Array.from({ length: 4 }, () => ({ source: 2, target: 0, lo: 0, hi: 0, follow: 0 }))] };
  const read = readFx(fxText(type), units);
  assert.equal(read.ok, true, read.reason);
  assert.equal(read.preset.slots[0].lo, -20);
  const bad = readFx(fxText({ ...type, slots: [{ ...type.slots[0], lo: -200 }] }), units);
  assert.equal(bad.ok, false);
});
