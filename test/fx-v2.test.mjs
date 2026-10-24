import { test } from "node:test";
import assert from "node:assert/strict";
import { readUnits } from "../src/node.mjs";
import { FxRecord } from "../src/record.mjs";
import { presetFile } from "../src/preset-file.mjs";
import { fxText, readFx, fxFromRecord, fxToRecord, modFromType } from "../src/fx-v2.mjs";
import { buildCollection, parseCollection, collectionEntry, factoryEntry, HEADER_SIZE, MOD_RECORD } from "../src/fx-collection.mjs";
import { locateModTable, readModType } from "../src/modtable.mjs";
import { recordOf, RECORD } from "../src/presets.mjs";
import { makeRecord, makeFirmwareWithArrays } from "./helpers.mjs";
import { REC } from "../src/layout.mjs";
import { FX_CATALOG } from "../data/fx/catalog.mjs";

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

test("a control row the slot does not have yet copies a used row of a donor, then gets its five known bytes", () => {
  const preset = shortDelay();
  const base = makeRecord("mfx", { name: "Echo", devices: { mfx: MOD_DELAY } });
  const donor = makeRecord("mfx", { name: "Delay", devices: { mfx: MOD_DELAY } });
  donor.map = [{ source: 66, chain: 2, param: 1, low: 0, high: 127 }];
  const at = REC.map + REC.mapEntrySize - 1;
  donor.bytes[at] = 0x5a;
  const made = fxToRecord(preset, base.bytes, [donor.bytes], units);
  assert.equal(made.ok, true, made.reason);
  const rec = new FxRecord(made.record, "mfx");
  assert.deepEqual(rec.map.map(({ index, ...r }) => r), preset.map);
  assert.equal(made.record[at], 0x5a, "the bytes nobody understands come from the donor's row");
  assert.equal(made.record[at + REC.mapEntrySize], 0x5a, "for every new row");
});

test("a building block the slot does not have comes from a donor record of the same firmware, never from zeros", () => {
  const preset = shortDelay();
  const base = makeRecord("mfx", { name: "Echo", devices: { mfx: TAPE_ECHO } });
  const donor = makeRecord("mfx", { name: "Delay", devices: { mfx: MOD_DELAY } });
  const empty = makeRecord("mfx", { name: "Empty" });
  const refused = fxToRecord(preset, base.bytes, [empty.bytes], units);
  assert.equal(refused.ok, false);
  assert.match(refused.reason, /in keinem Preset ein Baustein\. Ohne ein solches Preset lässt sich M_mod_delay nicht einsetzen/);
  const made = fxToRecord(preset, base.bytes, [base.bytes, donor.bytes], units);
  assert.equal(made.ok, true, made.reason);
  const rec = new FxRecord(made.record, "mfx");
  assert.equal(rec.device("mfx"), MOD_DELAY);
  assert.equal(rec.name, "Short Delay");
  const wrongName = fxToRecord({ ...preset, stages: [{ ...preset.stages[0], params: { nope: 1 } }] }, donor.bytes, [], units);
  assert.match(wrongName.reason, /keinen Parameter nope/);
});

test("a building block no record carries takes the stage block most records share, only the device byte changes", () => {
  const preset = shortDelay();
  const { device: at, params } = REC.stage.mfx;
  const block = (rec, b) => { rec.bytes.fill(b, at + 1, params); return rec.bytes; };
  const base = makeRecord("mfx", { name: "Echo", devices: { mfx: TAPE_ECHO } });
  block(base, 0x11);
  const records = [base.bytes, ...[0x36, 0x37, 0x38].map(mfx => block(makeRecord("mfx", { name: "Reverb", devices: { mfx } }), 0x40))];
  const made = fxToRecord(preset, base.bytes, records, units);
  assert.equal(made.ok, true, made.reason);
  assert.equal(made.record[at], MOD_DELAY);
  assert.deepEqual([...made.record.subarray(at + 1, params)], new Array(params - at - 1).fill(0x40));
  assert.equal(new FxRecord(made.record, "mfx").params(units, "mfx").find(p => p.name === "dry_wet").value, 122);
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
  // With the row every factory master preset has: the switch opens the input (rules: fx-on crossfade).
  const preset = { ...shortDelay(), map: [...shortDelay().map, { source: 65, chain: 7, param: 0, low: 0, high: 88 }] };
  const made = collectionEntry(preset, vsb, 0, units);
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

test("a factory preset moved to another place goes there byte for byte, with its v2 text; so does a modulation type", async () => {
  const vsb = await makeFirmwareWithArrays([
    { kind: "mfx", slot: 1, record: makeRecord("mfx", { name: "Mod Delay", devices: { mfx: MOD_DELAY } }) },
    { kind: "mfx", slot: 2, record: makeRecord("mfx", { name: "Tape Echo", devices: { mfx: TAPE_ECHO } }) },
  ]);
  const made = factoryEntry(vsb, "mfx", 1, 1, units);
  assert.equal(made.ok, true, made.reason);
  const from = recordOf(vsb, "mfx", 1);
  assert.deepEqual(made.entry.data, vsb.slice(from.file, from.file + RECORD), "the record of place 1, not rebuilt");
  assert.equal(made.entry.index, 1, "for place 2, 0-based");
  assert.equal(readFx(made.entry.text, units).preset.name, "Mod Delay");
  const table = locateModTable(vsb);
  const mod = factoryEntry(vsb, "mod", 2, 5, units);
  assert.equal(mod.ok, true, mod.reason);
  assert.deepEqual(mod.entry.data, vsb.slice(table.file + MOD_RECORD, table.file + 2 * MOD_RECORD), "type 2 is the second record");
  assert.equal(readFx(mod.entry.text, units).preset.name, readModType(vsb, table.file, 1).name);
  assert.equal(factoryEntry(vsb, "mfx", 250, 0, units).ok, false, "a place the firmware does not have");
});

test("a modulation type reads back with negative strengths, and out of range values are refused", () => {
  const type = { kind: "mod", name: "Wobble", depth: 64, speed: 40, curve: 6, slots: [{ source: 1, target: 3, lo: -20, hi: 30, follow: 1 }, ...Array.from({ length: 4 }, () => ({ source: 2, target: 0, lo: 0, hi: 0, follow: 0 }))] };
  const read = readFx(fxText(type), units);
  assert.equal(read.ok, true, read.reason);
  assert.equal(read.preset.slots[0].lo, -20);
  const bad = readFx(fxText({ ...type, slots: [{ ...type.slots[0], lo: -200 }] }), units);
  assert.equal(bad.ok, false);
});

test("the Türsteher stands before the card too: a block that crashes in stage 2 is refused, every catalog effect passes", async () => {
  const vsb = await makeFirmwareWithArrays([
    { kind: "mfx", slot: 1, record: makeRecord("mfx", { name: "Mod Delay", devices: { mfx: MOD_DELAY } }) },
    { kind: "ifx", slot: 1, record: makeRecord("ifx", { name: "Chorus", devices: { ifx1: 0x11, ifx2: 0x11 } }) },
  ], { patched: true });
  const crash = { kind: "ifx", name: "Absturz", map: [], stages: [
    { stage: "ifx1", unit: 0x11, unitName: "I_chorus", params: {} },
    { stage: "ifx2", unit: 0x02, unitName: "I_decimator", params: {} },
  ] };
  const made = collectionEntry(crash, vsb, 0, units);
  assert.equal(made.ok, false, "a decimator in stage 2 crashes the device (data/findings.mjs)");
  assert.match(made.reason, /Türsteher/);
  assert.match(made.reason, /freigeben/, "and it says how to let it through anyway");
  const freed = collectionEntry(crash, vsb, 0, units, { risky: true });
  assert.equal(freed.ok, true, `freed on purpose it goes into the file: ${freed.reason}`);
  for (const item of FX_CATALOG) {
    const entry = collectionEntry(item, vsb, 0, units);
    assert.equal(entry.ok, true, `${item.name}: ${entry.reason}`);
  }
});

test("a preset can say what it does and who made it, with an https link; a file without these keeps its text", () => {
  const plain = fxText(shortDelay());
  assert.doesNotMatch(plain, /creator|description/, "nothing added when nothing is set");
  const told = { ...shortDelay(), description: "Kurzes Echo.", creator: "Kuhler Buhler", creatorUrl: "https://www.instagram.com/kuhler_buhler/" };
  const read = readFx(fxText(told), units);
  assert.equal(read.ok, true, read.reason);
  assert.equal(read.preset.creatorUrl, "https://www.instagram.com/kuhler_buhler/");
  assert.equal(read.preset.description, "Kurzes Echo.");
  const sneaky = JSON.parse(fxText({ ...told, creatorUrl: "https://x.example/" }));
  sneaky.creatorUrl = "javascript:alert(1)";
  assert.match(readFx(JSON.stringify(sneaky), units).reason, /https/, "a link that is not https is refused");
});
