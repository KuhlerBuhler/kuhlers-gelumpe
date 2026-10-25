import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { field, POINTER_TABLES } from "../src/map/index.mjs";
import { ramToFile, RAM_BASE } from "../src/map/address.mjs";
import { locatePresets, recordOf, presetRoom, addPreset, nameAt, RECORD, RESERVE } from "../src/presets.mjs";
import { VsbImage } from "../src/image.mjs";
import { readUnits } from "../src/node.mjs";
import { exportPresets } from "../src/export.mjs";
import { makeFirmwareWithArrays, makeRecord } from "./helpers.mjs";

readUnits();

const word = (bytes, ram, value) => new DataView(bytes.buffer).setUint32(ramToFile(ram), value, true);
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const NAME = ["Punch", "Overdrive", "Distortion", "Decimator"];

/**
 * An image with the structure of Korg's own build and none of its bytes: two getters, two pointer arrays of 100 whose
 * records are scattered, menu lengths, and records that name a unit the map knows (a Punch is device 0x01 in stage 1).
 * `patched` makes it what the BLECH patch preset-tables leaves: arrays of 128, clamps of 127, extra entries aliasing entry 0.
 */
function image({ ifx = 4, mfx = 3, patched = false, scattered = true } = {}) {
  const bytes = new Uint8Array(0x200100).fill(0xff);
  const arrays = { ifx: patched ? 0xc017c000 : 0xc00ee000, mfx: patched ? 0xc017c200 : 0xc00ee200 };
  const base = { ifx: 0xc00a8000, mfx: 0xc00c0000 };
  const slots = patched ? 128 : 100;
  for (const kind of ["ifx", "mfx"]) {
    const g = POINTER_TABLES.get(`presets.${kind}`).getter;
    word(bytes, g.literal, arrays[kind]);
    word(bytes, g.clamp, 0x23a00000 | (slots - 1));
    for (let i = 0; i < slots; i++) {
      const own = i < 100 ? base[kind] + (scattered ? (i * 7 % 100) : i) * RECORD : arrays[kind];     // beyond 100 alias entry 0 (set below)
      word(bytes, arrays[kind] + 4 * i, own);
    }
    if (patched) for (let i = 100; i < 128; i++) word(bytes, arrays[kind] + 4 * i, new DataView(bytes.buffer).getUint32(ramToFile(arrays[kind]), true));
    for (let i = 0; i < 100; i++) {
      const at = ramToFile(base[kind] + (scattered ? (i * 7 % 100) : i) * RECORD);
      bytes.fill(0, at, at + RECORD);
      const name = i < (kind === "ifx" ? ifx : mfx) ? `${kind === "ifx" ? NAME[i % 4] : "Mod Delay"} ${i}`.slice(0, 15) : "";
      for (let k = 0; k < name.length; k++) bytes[at + 1 + k] = name.charCodeAt(k);
      if (name) { bytes[at + 0x12a] = kind === "ifx" ? 0x01 : 0x01; bytes[at + 0x20b] = i; }
    }
  }
  for (const s of field("menu.ifxCount").sites) bytes[s.file] = s.value === "count" ? ifx : ifx - 1;
  new DataView(bytes.buffer).setUint32(0x98184, 0xe3a02000 | ifx, true);
  const f = field("menu.mfxCount");
  new DataView(bytes.buffer).setUint32(f.where.offset, f.instruction.expected & 0xffffff00 | mfx, true);
  return bytes;
}

test("the getters' literal and clamp say where the pointers are and how many there can be", () => {
  const stock = locatePresets(image());
  assert.deepEqual(stock, { ifx: { array: 0xc00ee000, capacity: 100 }, mfx: { array: 0xc00ee200, capacity: 100 } });
  const patched = locatePresets(image({ patched: true }));
  assert.equal(patched.ifx.capacity, 128);
  assert.equal(locatePresets(new Uint8Array(10)), null);
  assert.equal(locatePresets(new Uint8Array(0x200100)), null, "an image without getters is not one we know");
});

test("a record is found by its pointer, in a scattered pool as in a contiguous table", () => {
  for (const scattered of [true, false]) {
    const bytes = image({ scattered });
    const r = recordOf(bytes, "ifx", 2);
    assert.equal(nameAt(bytes, r.file), "Overdrive 1");
    assert.equal(recordOf(bytes, "ifx", 101), null, "an unpatched image has 100 slots");
  }
  assert.equal(recordOf(image({ patched: true }), "ifx", 101) !== null, true);
});

test("the list of an image shows what the menu offers and the preset past it, and not an array entry that points at an earlier record", () => {
  const unpatched = new VsbImage(image());
  assert.deepEqual(unpatched.list("ifx").map(x => x.slot), [1, 2, 3, 4]);
  const patched = new VsbImage(image({ patched: true }));
  assert.deepEqual(patched.list("ifx").map(x => x.slot), [1, 2, 3, 4], "28 aliases of entry 1 are no presets");
  assert.deepEqual(patched.list("mfx").map(x => x.slot), [1, 2, 3]);
});

test("a preset is added as a copy of an existing record: bytes the same but the name, menu length up in every place", () => {
  const before = image();
  const added = addPreset(before, "ifx", 2);
  assert.equal(added.ok, true, added.reasons.join(" "));
  assert.equal(added.slot, 5);
  assert.equal(added.name, "Overdrive 1 5");
  const copy = added.bytes.subarray(added.file, added.file + RECORD);
  const source = before.subarray(recordOf(before, "ifx", 2).file, recordOf(before, "ifx", 2).file + RECORD);
  assert.deepEqual(copy.subarray(16), source.subarray(16));
  assert.equal(copy[0], source[0]);
  assert.equal(presetRoom(added.bytes, "ifx").count, 5);
  assert.equal(presetRoom(added.bytes, "ifx").agreed, true);
  assert.equal(new DataView(added.bytes.buffer).getUint32(0x98184, true) & 0xff, 5, "the row length of the knob memory moves with it");
  assert.equal(before.every((b, i) => b === added.bytes[i] || i >= added.file && i < added.file + RECORD
    || field("menu.ifxCount").sites.some(s => s.file === i) || i === 0x98184), true, "nothing else changed");
  // the master menu is one byte
  const master = addPreset(before, "mfx", 1);
  assert.equal(master.ok, true, master.reasons.join(" "));
  assert.equal(presetRoom(master.bytes, "mfx").count, 4);
  assert.equal(presetRoom(master.bytes, "ifx").count, 4, "the other menu stays");
});

test("an unpatched image takes presets up to its 100 slots and then says why not", () => {
  let bytes = image({ ifx: 99 });
  const one = addPreset(bytes, "ifx", 1);
  assert.equal(one.ok, true, one.reasons.join(" "));
  const full = addPreset(one.bytes, "ifx", 1);
  assert.equal(full.ok, false);
  assert.match(full.reasons[0], /voll.*preset-tables/);
});

test("with the patch the table takes 128, and a slot beyond 100 gets a record of its own in the reserve", () => {
  let bytes = image({ ifx: 99, patched: true });
  const a = addPreset(bytes, "ifx", 3);
  assert.equal(a.slot, 100);
  bytes = a.bytes;
  const b = addPreset(bytes, "ifx", 3);
  assert.equal(b.ok, true, b.reasons.join(" "));
  assert.equal(b.slot, 101);
  assert.equal(b.file, ramToFile(RESERVE.ifx.ram), "the first slot past 100 is the first reserve record");
  assert.equal(recordOf(b.bytes, "ifx", 101).ram, RESERVE.ifx.ram, "its array entry points there now");
  assert.equal(recordOf(b.bytes, "ifx", 102).ram, recordOf(b.bytes, "ifx", 1).ram, "the next one still aliases entry 1");
  bytes = b.bytes;
  for (let slot = 102; slot <= 128; slot++) {
    const next = addPreset(bytes, "ifx", 1);
    assert.equal(next.ok, true, `${slot}: ${next.reasons.join(" ")}`);
    assert.equal(next.file, ramToFile(RESERVE.ifx.ram) + (slot - 101) * RECORD);
    bytes = next.bytes;
  }
  assert.equal(presetRoom(bytes, "ifx").count, 128);
  const over = addPreset(bytes, "ifx", 1);
  assert.equal(over.ok, false);
  assert.match(over.reasons[0], /voll: 128/);
  assert.equal(new VsbImage(bytes).list("ifx").length, 128);
  assert.equal(new Set(Array.from({ length: 128 }, (_, i) => recordOf(bytes, "ifx", i + 1).ram)).size, 128, "128 records of their own");
});

test("a record behind the menu length that holds a preset is not overwritten unless asked", () => {
  const bytes = image({ ifx: 3 });
  const hidden = recordOf(bytes, "ifx", 4);
  Uint8Array.from("Hidden", c => c.charCodeAt(0)).forEach((c, i) => { bytes[hidden.file + 1 + i] = c; });
  const refused = addPreset(bytes, "ifx", 1);
  assert.equal(refused.ok, false);
  assert.match(refused.reasons[0], /Hidden/);
  assert.equal(addPreset(bytes, "ifx", 1, { overwrite: true }).ok, true);
});

test("a source beyond the menu, a menu whose sites disagree and an unknown image are refused", () => {
  assert.equal(addPreset(image(), "ifx", 5).ok, false);
  const split = image();
  split[field("menu.ifxCount").sites[0].file] = 9;
  assert.equal(addPreset(split, "ifx", 1).ok, false);
  assert.equal(addPreset(new Uint8Array(0x200100), "ifx", 1).ok, false);
});

const hacktribeLike = () => makeFirmwareWithArrays([
  { kind: "ifx", slot: 1, record: makeRecord("ifx", { name: "Punch", devices: { ifx1: 1 } }) },
  { kind: "mfx", slot: 1, record: makeRecord("mfx", { name: "Mod Delay", devices: { mfx: 1 } }) },
]);

test("an edited firmware is exported when only presets and menu lengths changed, and the changed runs come back for the check", async () => {
  const original = await hacktribeLike();
  assert.equal(presetRoom(original, "ifx").count, 52);
  const added = addPreset(original, "ifx", 1);
  assert.equal(added.ok, true, added.reasons.join(" "));
  const res = await exportPresets(original, added.bytes);
  assert.equal(res.ok, true, res.reasons?.join(" "));
  assert.ok(res.allow.length > 0 && res.allow.every(([file, length]) => file >= added.file && file + length <= added.file + RECORD), "data runs lie in the new record");
  assert.equal(res.allowCode.reduce((sum, [, length]) => sum + length, 0), 13 + 1, "the 13 places of the insert length and the row length");
  assert.equal(res.changed, res.allow.reduce((sum, [, length]) => sum + length, 0) + 14);
  const stray = Uint8Array.from(added.bytes);
  stray[0x1000] ^= 1;
  const refused = await exportPresets(original, stray);
  assert.equal(refused.ok, false);
  assert.match(refused.reasons[0], /0x1000 liegt außerhalb der Presets/);
  const broken = Uint8Array.from(added.bytes);
  broken[field("menu.ifxCount").sites[1].file] = 7;
  assert.equal((await exportPresets(original, broken)).ok, false, "menu length places that disagree");
});

test("the map and the patch agree on where the arrays and the reserve are", () => {
  for (const [file, build] of [["data/patches/preset-tables.json", "hacktribe"], ["data/patches/preset-tables-stock.json", "stock"]]) {
    const patch = read(file);
    assert.deepEqual(patch.builds, [build]);
    for (const kind of ["ifx", "mfx"]) {
      const t = POINTER_TABLES.get(`presets.${kind}`);
      const blech = t.arrays.find(a => a.build === "blech");
      assert.ok(patch.changes.some(c => c.file === ramToFile(blech.ram) && c.copy?.file === ramToFile(t.arrays.find(a => a.build === build).ram)), `${kind}: the array is copied from the ${build} array`);
      assert.ok(patch.changes.some(c => c.file === ramToFile(t.getter.literal) && Buffer.from(c.bytes, "hex").readUInt32LE() === blech.ram), `${kind}: the getter's literal`);
      const room = patch.ram.find(r => Number(r.at) === t.reserve.ram);
      assert.equal(room.length, t.reserve.slots * RECORD, `${kind}: room for the reserve records`);
      assert.equal(t.reserve.first, 101);
    }
    assert.equal(patch.ram.find(r => /knob memory/.test(r.what)).length, 16 * 128);
  }
});

test("the patch applies to the user's firmware and gives it room for 128 presets (when one is given)", { skip: process.env.E2_VSB && process.env.E2_STOCK_VSB ? false : "set E2_VSB and E2_STOCK_VSB" }, async () => {
  const { applyPatches } = await import("../src/patch.mjs");
  const set = read("data/patches/blech.json").patches.map(read);
  for (const [path, build] of [[process.env.E2_VSB, "hacktribe"], [process.env.E2_STOCK_VSB, "stock"]]) {
    const vsb = new Uint8Array(readFileSync(path));
    const before = presetRoom(vsb, "ifx");
    const applied = await applyPatches(vsb, set);
    assert.equal(applied.ok, true, `${build}: ${applied.reasons.join(" ")}`);
    const after = presetRoom(applied.bytes, "ifx");
    const catalog = set.find(p => p.id === "fx-catalog").presets;
    assert.deepEqual([after.capacity, after.count, after.patched], [128, before.count + catalog.filter(p => p.kind === "ifx").length, true], build);
    const mfx = [presetRoom(vsb, "mfx").count, presetRoom(applied.bytes, "mfx").count];
    assert.equal(mfx[1], mfx[0] + catalog.filter(p => p.kind === "mfx").length, `${build}: the catalog's master effects behind the firmware's`);
    const again = await applyPatches(applied.bytes, set.filter(p => p.id === "fx-catalog"));
    assert.deepEqual([again.ok, presetRoom(again.bytes, "ifx").count], [true, after.count], `${build}: applied twice, nothing is added`);
    for (const kind of ["ifx", "mfx"]) {
      for (let slot = 1; slot <= presetRoom(vsb, kind).count; slot++) {
        const a = recordOf(vsb, kind, slot), b = recordOf(applied.bytes, kind, slot);
        assert.equal(a.file, b.file, `${build} ${kind} ${slot}: the factory records stay where they are`);
      }
    }
  }
});

test("the build constants of the patch builder are the map's", { skip: existsSync(new URL("../tools/patch/preset_tables.py", import.meta.url)) ? false : "no builder" }, () => {
  const source = readFileSync(new URL("../tools/patch/preset_tables.py", import.meta.url), "utf8");
  const hex = name => Number(source.match(new RegExp(`^${name}\\s*=\\s*(0x[0-9A-Fa-f]+)`, "m"))[1]);
  assert.equal(hex("RES_IFX"), POINTER_TABLES.get("presets.ifx").reserve.ram);
  assert.equal(hex("RES_MFX"), POINTER_TABLES.get("presets.mfx").reserve.ram);
  assert.equal(hex("ARRAY_IFX"), POINTER_TABLES.get("presets.ifx").arrays.find(a => a.build === "blech").ram);
  assert.equal(hex("ARRAY_MFX"), POINTER_TABLES.get("presets.mfx").arrays.find(a => a.build === "blech").ram);
  assert.ok(RAM_BASE === 0xc0000000);
});

test("Korg's own 2.02: its 200 records are exactly the runs the map lists, each slot has a record of its own (when one is given)", { skip: process.env.E2_STOCK_VSB ? false : "set E2_STOCK_VSB" }, async () => {
  const { stockRecordRuns } = await import("../src/plan.mjs");
  const bytes = new Uint8Array(readFileSync(process.env.E2_STOCK_VSB));
  const where = locatePresets(bytes);
  const found = [];
  for (const kind of ["ifx", "mfx"]) for (let slot = 1; slot <= where[kind].capacity; slot++) found.push(recordOf(bytes, kind, slot).ram);
  assert.equal(new Set(found).size, 200, "no two slots share a record");
  assert.deepEqual([...found].sort((a, b) => a - b), stockRecordRuns(), "the map's runs are the records, no more and no fewer");
});
