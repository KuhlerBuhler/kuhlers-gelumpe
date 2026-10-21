import { test } from "node:test";
import assert from "node:assert/strict";
import { BLOCKS, TABLES, field, byteSpans, offsetOf } from "../src/map/index.mjs";
import { identify } from "../src/firmware.mjs";
import { exportModTypes } from "../src/export.mjs";
import { locateModTable, readModType, readModTypes, writeModType, modFieldSpans, MOD_FIELDS, SLOT_FIELDS, SLOT_COUNT } from "../src/modtable.mjs";
import { lintModType, lintModTypes } from "../src/modtable-rules.mjs";
import { converter } from "../src/map/convert.mjs";
import { makeFirmware, putModTable } from "./helpers.mjs";

const READ = TABLES.get("table.modType").file;
const KORG = TABLES.get("table.modTypeStock").file;
const WORDS = [0x98e3c, 0x99598];
const ram = file => file - 0x100 + 0xc0000000;

/** A firmware as Hacktribe builds it: both copies in the image, the code pointing at one. */
async function image({ readers = READ, copies = [READ, KORG] } = {}) {
  const bytes = await makeFirmware();
  const view = new DataView(bytes.buffer);
  for (const at of WORDS) view.setUint32(at, 0, true);
  for (const file of copies) bytes.fill(0, file, file + 72 * 0x58);
  for (const file of copies) putModTable(bytes, file, { readers: [] });
  for (const at of WORDS) view.setUint32(at, ram(readers) + 4, true);
  return bytes;
}

test("the map names the copy Hacktribe reads and keeps Korg's copy as its own table", () => {
  assert.equal(READ, 0x1a00fc);
  assert.equal(KORG, 0xd82ec);
  assert.equal(TABLES.get("table.modType").stride, 0x58);
  assert.equal(TABLES.get("table.modType").count, 72);
});

test("every byte of an entry from +0x14 on has a field, the slots sit eight bytes apart", () => {
  const owned = new Set();
  for (const f of BLOCKS.get("modType").fields) for (const [start, end] of byteSpans(f)) for (let at = start; at < end; at++) owned.add(at);
  const gaps = [];
  for (let at = 0x14; at < 0x58; at++) if (!owned.has(at)) gaps.push(at.toString(16));
  assert.deepEqual(gaps, []);
  const slot = (name, k) => offsetOf(field(`modType.slot.${name}`), [k]);
  assert.deepEqual([slot("source", 0), slot("target", 1), slot("lo", 2), slot("hi", 4), slot("follow", 4)], [0x2c, 0x35, 0x3f, 0x50, 0x51]);
  assert.equal(offsetOf(field("modType.slot6"), []), 0x54);
});

test("the copy is found by the pointer in the code: Hacktribe's second copy, Korg's first one, one that moved", async () => {
  const hacktribe = locateModTable(await image());
  assert.deepEqual([hacktribe.ok, hacktribe.file, hacktribe.place, hacktribe.readers, hacktribe.ram], [true, READ, "table.modType", WORDS, 0xc019fffc]);
  const stock = locateModTable(await image({ readers: KORG }));
  assert.deepEqual([stock.ok, stock.file, stock.place], [true, KORG, "table.modTypeStock"]);
  const moved = await image({ readers: 0x1b0000, copies: [READ, KORG, 0x1b0000] });
  const found = locateModTable(moved);
  assert.deepEqual([found.ok, found.file, found.place], [true, 0x1b0000, "other"]);
});

test("the unread copy is not located, whatever its bytes say", async () => {
  const bytes = await image();
  assert.notEqual(locateModTable(bytes).file, KORG);
  // The dead copy edited to garbage does not change which copy is read.
  bytes.fill(0xff, KORG, KORG + 72 * 0x58);
  assert.equal(locateModTable(bytes).file, READ);
});

test("no pointer, two pointers, a pointer at bytes that are no table, a word in the DSP stream or off alignment: nothing is located", async () => {
  const none = await image();
  for (const at of WORDS) new DataView(none.buffer).setUint32(at, 0, true);
  const a = locateModTable(none);
  assert.equal(a.ok, false);
  assert.match(a.reasons[0], /nicht zu finden/);

  const two = await image();
  new DataView(two.buffer).setUint32(WORDS[1], ram(KORG) + 4, true);
  const b = locateModTable(two);
  assert.equal(b.ok, false);
  assert.match(b.reasons[0], /mehrfach drin/);

  const junk = await image();
  junk.fill(0xff, READ, READ + 72 * 0x58);
  assert.equal(locateModTable(junk).ok, false, "a pointer at 0xff is no table");

  const dsp = await image({ readers: KORG });
  for (const at of WORDS) new DataView(dsp.buffer).setUint32(at, 0, true);
  new DataView(dsp.buffer).setUint32(0xfb480, ram(READ) + 4, true);
  assert.equal(locateModTable(dsp).ok, false, "a word in the DSP stream is no code pointer");

  const odd = await image();
  for (const at of WORDS) new DataView(odd.buffer).setUint32(at, 0, true);
  const view = new DataView(odd.buffer);
  view.setUint32(0x98e3d, ram(READ) + 4, true);
  assert.equal(locateModTable(odd).ok, false, "an unaligned word is no literal");
});

test("a table that is no table is rejected by its entries: empty name, a name with a control byte, target 6, depth 128", async () => {
  const cases = [
    (b, e) => { b[e + 4] = 0; },
    (b, e) => { b[e + 6] = 0x07; },
    (b, e) => { b[e + 25] = 6; },
    (b, e) => { b[e + 26] = 128; },
    (b, e) => { b[e + 27] = 128; },
    (b, e) => { b[e + 7] = 0; b[e + 9] = 0x41; },
    (b, e) => { b[e + 0x1d] = 2; },
    (b, e) => { b[e + 0x1e] = 2; },
    (b, e) => { b[e + 0x24] = 0x9c; },
  ];
  for (const [n, bad] of cases.entries()) {
    const bytes = await image();
    bad(bytes, READ + 71 * 0x58);
    assert.equal(locateModTable(bytes).ok, false, `case ${n}`);
  }
});

test("a structure with a name, one entry before the table and a pointer of its own is no shifted table", async () => {
  const bytes = await image({ copies: [READ, 0x1b0000] });
  const before = READ - 0x58;
  bytes.fill(0, before, READ);
  bytes.set(Array.from("A SYSTEM HEADER..", c => c.charCodeAt(0)).slice(0, 16), before + 4);
  bytes[before + 0x24] = 0x9c;
  new DataView(bytes.buffer).setUint32(0x50ec8, ram(before) + 4, true);
  const found = locateModTable(bytes);
  assert.deepEqual([found.ok, found.file], [true, READ]);
});

test("identify finds the table through the pointer and gives its reasons when there is none", async () => {
  const id = await identify(await image());
  assert.equal(id.known, true, id.reasons.join(" "));
  const stock = await identify(await image({ readers: KORG }));
  assert.equal(stock.known, true, stock.reasons.join(" "));
  const none = await image();
  for (const at of WORDS) new DataView(none.buffer).setUint32(at, 0, true);
  const bad = await identify(none);
  assert.equal(bad.known, false);
  assert.match(bad.reasons.join(" "), /Tabelle mit den Modulationen/);
});

const EMPTY = { source: 0, target: 0, lo: 0, hi: 0, follow: 0 };

test("an entry reads as name, target label, depth, speed, curve and five slots; the rest of the entry is not part of it", async () => {
  const bytes = await image();
  assert.deepEqual(readModType(bytes, READ, 0), { name: "EG+ Filter", target: 3, depth: 20, speed: 100, curve: 2, slots: Array(5).fill(EMPTY) });
  assert.deepEqual(readModType(bytes, READ, 7), { name: "Type 8", target: 1, depth: 27, speed: 93, curve: 2, slots: Array(5).fill(EMPTY) });
  assert.equal(readModTypes(bytes, READ).length, 72);
  assert.deepEqual(Object.keys(MOD_FIELDS), ["name", "depth", "speed", "curve"], "the target is a label, not an editable field");
  assert.deepEqual(Object.keys(SLOT_FIELDS), ["source", "target", "lo", "hi", "follow"]);
  assert.equal(SLOT_COUNT, 5);
  assert.throws(() => readModType(bytes, READ, 72), RangeError);
});

test("a slot reads from its eight bytes, the strengths signed", async () => {
  const bytes = await image();
  const e = READ + 9 * 0x58;
  bytes.set([1, 3, 0x7a, 0xc1, 0x3f, 1], e + 0x2c + 8 * 2);      // slot 2: LFO, Filter, cache, -63, 63, follows
  assert.deepEqual(readModType(bytes, READ, 9).slots[2], { source: 1, target: 3, lo: -63, hi: 63, follow: 1 });
  assert.deepEqual(readModType(bytes, READ, 9).slots[1], EMPTY);
});

test("writing touches the fields of the editor and nothing else of the entry", async () => {
  const bytes = await image();
  const entry = 5 * 0x58;
  bytes.fill(0xa5, READ + entry + 20, READ + entry + 25);       // bytes nobody understands
  bytes.fill(0xa5, READ + entry + 29, READ + entry + 0x58);
  const before = Uint8Array.from(bytes);
  const slots = Object.assign([], { 1: { source: 1, target: 8, lo: -20, hi: 40, follow: 0 }, 4: { target: 10 } });
  writeModType(bytes, READ, 5, { name: "Mein Typ", depth: 127, speed: 0, curve: 6, slots });
  const now = readModType(bytes, READ, 5);
  assert.deepEqual([now.name, now.depth, now.speed, now.curve], ["Mein Typ", 127, 0, 6]);
  assert.equal(now.target, readModType(before, READ, 5).target, "the label stays as it was");
  assert.deepEqual(now.slots[1], { source: 1, target: 8, lo: -20, hi: 40, follow: 0 });
  assert.deepEqual(now.slots[4], { source: 0xa5, target: 10, lo: 0xa5 - 256, hi: 0xa5 - 256, follow: 0xa5 }, "an untouched field of a slot stays");
  assert.deepEqual(now.slots[0], readModType(before, READ, 5).slots[0]);
  const spans = new Set(modFieldSpans(READ, 5).flatMap(([at, n]) => Array.from({ length: n }, (_, k) => at + k)));
  for (let i = 0; i < bytes.length; i++) if (!spans.has(i)) assert.equal(bytes[i], before[i], `0x${i.toString(16)} stayed`);
  // The bytes a slot does not carry (cache and the two spares) are outside the spans.
  for (let k = 0; k < 5; k++) for (const off of [2, 6, 7]) assert.equal(spans.has(READ + entry + 0x2c + 8 * k + off), false, `slot ${k} +${off}`);
  // A shorter name pads with NULs, it does not leave the tail of the old one.
  writeModType(bytes, READ, 5, { name: "Hi" });
  assert.equal(readModType(bytes, READ, 5).name, "Hi");
  assert.deepEqual(Array.from(bytes.subarray(READ + entry + 6, READ + entry + 20)), new Array(14).fill(0));
});

test("the field spans are the four fields and the five fields of five slots, and not the target label", () => {
  const spans = modFieldSpans(READ, 0);
  assert.equal(spans.length, 4 + 5 * 5);
  assert.equal(spans.some(([at]) => at === READ + 0x19), false);
});

test("the slot choices say what the measurements say", () => {
  assert.deepEqual(converter("modSlotSource").choices.map(c => c.label), ["Hüllkurve", "LFO", "Aus"]);
  const t = converter("modSlotTarget").choices;
  assert.deepEqual([t[0], t[1], t[2], t[3], t[8], t[9], t[10]].map(c => c.label), ["Kein Ziel", "Pitch", "OSC", "Filter", "Level", "Pan", "IFX"]);
  assert.equal(t.length, 11);
  assert.deepEqual(converter("modCurve").choices.map(c => c.label), ["Sägezahn fallend", "Rechteck", "Dreieck", "Sample and Hold", "Zufall", "Rechteck einpolig", "Sinus"]);
});

test("a value the field does not take is refused and leaves the entry as it was", async () => {
  const bytes = await image();
  const before = Uint8Array.from(bytes);
  for (const values of [{ depth: 128 }, { speed: -1 }, { target: 3 }, { curve: 256 }, { name: "x".repeat(17) }, { name: "Ümlaut" }, { name: "" },
    { name: "Gut", depth: 200 }, { colour: 1 },
    { slots: [{ target: 11 }] }, { slots: [{ source: 3 }] }, { slots: [{ lo: -64 }] }, { slots: [{ hi: 64 }] }, { slots: [{ follow: 2 }] },
    { slots: [{ colour: 1 }] }, { slots: Array(6).fill({}) }, { name: "Gut", slots: [{ target: 1 }, { hi: 99 }] }]) {
    assert.throws(() => writeModType(bytes, READ, 3, values), undefined, JSON.stringify(values));
    assert.deepEqual(bytes, before, JSON.stringify(values));
  }
});

test("export: one changed default depth goes to the copy that is read, byte for byte, and nowhere else", async () => {
  const vsb = await image();
  const types = readModTypes(vsb, READ);
  types[12] = { ...types[12], depth: 99 };
  const res = await exportModTypes(vsb, types);
  assert.equal(res.ok, true, res.reasons?.join(" "));
  assert.deepEqual([res.changed, res.file, res.place], [1, READ, "table.modType"]);
  const at = READ + 12 * 0x58 + 26;
  assert.deepEqual(res.allow, [[at, 1]]);
  const diff = [...res.bytes.keys()].filter(i => res.bytes[i] !== vsb[i]);
  assert.deepEqual(diff, [at]);
  assert.equal(res.bytes[at], 99);
  assert.equal(vsb[at], 20 + 12, "the input is not touched");
  for (let i = 0; i < 72 * 0x58; i++) assert.equal(res.bytes[KORG + i], vsb[KORG + i], "Korg's copy stays");
});

test("export on a firmware that reads Korg's copy writes Korg's copy", async () => {
  const vsb = await image({ readers: KORG });
  const types = readModTypes(vsb, KORG);
  types[0] = { ...types[0], name: "Mein EG", speed: 5 };
  const res = await exportModTypes(vsb, types);
  assert.equal(res.ok, true, res.reasons?.join(" "));
  assert.equal(res.file, KORG);
  assert.equal(readModType(res.bytes, KORG, 0).name, "Mein EG");
  assert.equal(readModType(res.bytes, READ, 0).name, "EG+ Filter", "the dead copy stays");
});

test("export: adjacent changed bytes are one allowed run, an unchanged list changes nothing", async () => {
  const vsb = await image();
  const types = readModTypes(vsb, READ);
  types[2] = { ...types[2], depth: 1, speed: 2 };
  const res = await exportModTypes(vsb, types);
  assert.deepEqual(res.allow, [[READ + 2 * 0x58 + 26, 2]]);
  const same = await exportModTypes(vsb, readModTypes(vsb, READ));
  assert.deepEqual([same.ok, same.changed, same.allow], [true, 0, []]);
});

test("export is refused for a value out of range, with the number of the type, and when no copy is read", async () => {
  const vsb = await image();
  const types = readModTypes(vsb, READ);
  types[40] = { ...types[40], depth: 500 };
  const bad = await exportModTypes(vsb, types);
  assert.equal(bad.ok, false);
  assert.match(bad.reasons[0], /Modulationsart 41/);
  assert.equal(bad.bytes, undefined);

  const none = await image();
  for (const at of WORDS) new DataView(none.buffer).setUint32(at, 0, true);
  const res = await exportModTypes(none, types);
  assert.equal(res.ok, false);
  assert.match(res.reasons[0], /nicht zu finden/);
  await assert.rejects(exportModTypes(vsb, types.slice(1)), TypeError);
});

test("export: slot edits go to the copy that is read, byte for byte, nothing else and not the spare bytes of a slot", async () => {
  const vsb = await image();
  const types = readModTypes(vsb, READ);
  types[3] = { ...types[3], curve: 6, slots: types[3].slots.map((s, k) => (k === 1 ? { source: 1, target: 3, lo: -10, hi: 20, follow: 1 } : s)) };
  const res = await exportModTypes(vsb, types);
  assert.equal(res.ok, true, res.reasons?.join(" "));
  assert.equal(res.changed, 1);
  const entry = READ + 3 * 0x58;
  const slot = entry + 0x2c + 8;
  assert.deepEqual(res.allow, [[entry + 0x1c, 1], [slot, 2], [slot + 3, 3]], "the cache byte of the slot stays out of the runs");
  const diff = [...res.bytes.keys()].filter(i => res.bytes[i] !== vsb[i]);
  assert.deepEqual(diff, [entry + 0x1c, slot, slot + 1, slot + 3, slot + 4, slot + 5]);
  assert.deepEqual(readModType(res.bytes, READ, 3).slots[1], { source: 1, target: 3, lo: -10, hi: 20, follow: 1 });
  assert.equal(res.bytes[slot + 2], vsb[slot + 2], "the cache byte is not written");
});

test("export refuses a changed target label and a slot value out of range", async () => {
  const vsb = await image();
  const types = readModTypes(vsb, READ);
  types[1] = { ...types[1], target: 0 };
  const label = await exportModTypes(vsb, types);
  assert.equal(label.ok, false);
  assert.match(label.reasons[0], /Modulationsart 2.*Etikett/);
  const bad = readModTypes(vsb, READ);
  bad[7] = { ...bad[7], slots: bad[7].slots.map((s, k) => (k === 2 ? { ...s, hi: 90 } : s)) };
  const res = await exportModTypes(vsb, bad);
  assert.equal(res.ok, false);
  assert.match(res.reasons[0], /Modulationsart 8/);
});

const slot = over => ({ ...EMPTY, ...over });
const type = over => ({ name: "T", target: 0, depth: 10, speed: 10, curve: 2, slots: Array.from({ length: 5 }, () => slot({})), ...over });
const codes = list => list.map(f => f.code).sort();

test("rules: every finding is a warning, because none of it was heard", () => {
  const worst = type({ curve: 9, slots: [slot({ source: 1, target: 5, lo: -5, hi: 5 }), slot({ source: 1, target: 5, lo: 1, hi: 5 }), slot({ target: 3 }), slot({}), slot({})] });
  const found = lintModType(worst);
  assert.ok(found.length >= 4);
  assert.deepEqual([...new Set(found.map(f => f.severity))], ["warn"]);
  for (const f of found) assert.match(f.message, /\S{3}.{20}/);
});

test("rules: a curve outside the seven measured ones, a code with an open meaning, a slot with a target and no effect, a strength that ignores its lower value", () => {
  const now = type({ curve: 8, slots: [slot({ source: 1, target: 6, lo: 5, hi: 9 }), slot({ source: 1, target: 1, lo: -5, hi: 30 }), slot({ source: 1, target: 3 }), slot({ source: 2, target: 3, lo: 1, hi: 9 }), slot({})] });
  const found = lintModType(now);
  assert.deepEqual(codes(found), ["mod-curve-unmeasured", "mod-slot-silent", "mod-slot-silent", "mod-strength-lo-ignored", "mod-target-unclear"]);
  assert.match(found.find(f => f.code === "mod-curve-unmeasured").message, /8.*hinter eine Tabelle/);
  assert.match(found.find(f => f.code === "mod-target-unclear").message, /Code 6/);
  assert.deepEqual(found.filter(f => f.code === "mod-slot-silent").map(f => f.where), ["Slot 3", "Slot 4"]);
  assert.match(lintModType(type({ curve: 7 }))[0].message, /wie Kurve 4/);
});

test("rules: only what differs from the file is reported, so the file's own values do not count", () => {
  const was = type({ curve: 9, slots: [slot({ source: 1, target: 6, lo: -5, hi: 9 }), slot({}), slot({}), slot({}), slot({})] });
  assert.deepEqual(lintModType(was, was), []);
  assert.deepEqual(codes(lintModType({ ...was, name: "Neu" }, was)), []);
  const next = { ...was, slots: was.slots.map((s, k) => (k === 0 ? { ...s, hi: 20 } : s)) };
  assert.deepEqual(codes(lintModType(next, was)), ["mod-strength-lo-ignored"]);
});

test("rules: two slots on one target add up, and a changed curve with no LFO slot does nothing", () => {
  const was = type({ slots: [slot({ source: 0, target: 1, lo: 0, hi: 63 }), slot({}), slot({}), slot({}), slot({})] });
  const two = { ...was, slots: was.slots.map((s, k) => (k === 1 ? slot({ source: 0, target: 1, lo: 0, hi: 20 }) : s)) };
  assert.deepEqual(codes(lintModType(two, was)), ["mod-slots-add"]);
  assert.match(lintModType(two, was)[0].message, /Slots 1 und 2.*Doppelte/);
  assert.deepEqual(codes(lintModType({ ...was, curve: 5 }, was)), ["mod-curve-unused"]);
  const lfo = { ...was, slots: was.slots.map((s, k) => (k === 0 ? { ...s, source: 1 } : s)) };
  assert.deepEqual(lintModType({ ...lfo, curve: 5 }, lfo), []);
});

test("rules: a clean edit has no finding, lintModTypes names the type", () => {
  const was = [type({}), type({})];
  const now = [type({}), type({ slots: [slot({ source: 1, target: 4, lo: 0, hi: 30 }), slot({}), slot({}), slot({}), slot({})] })];
  assert.deepEqual(lintModTypes(now, was).map(f => [f.type, f.code]), [[1, "mod-target-unclear"]]);
  assert.deepEqual(lintModTypes(was, was), []);
});
