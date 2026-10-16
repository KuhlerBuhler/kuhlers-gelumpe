import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import { DeviceSession } from "../src/session.mjs";
import { exportModTypes } from "../src/export.mjs";
import { locateModTable, readModType, readModTypes, writeModType } from "../src/modtable.mjs";
import { field, offsetOf, TABLES } from "../src/map/index.mjs";
import { CURRENT_PATTERN } from "../src/map/address.mjs";
import { readU32le } from "../src/bytes.mjs";
import { startEmulator, emuPython } from "./support/emu.mjs";
import { run as exec } from "./support/spawn.mjs";

const checker = fileURLToPath(new URL("../tools/emu/check.py", import.meta.url));

// The modulation table in the firmware, on the firmware: an edited default depth and speed show up on
// a part when the type is chosen with MOD. TYPE, and an edit of the copy the firmware does not read does not.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : false;
const MOD_TYPE_ENCODER = 3;
const EDITED = 12;         // default depth and speed edited in the copy that is read
const DEAD = 20;           // edited only in the copy that is not read
const UNTOUCHED = 30;
// measure:2026-10-15/modulation-stufe2: nine bytes per part from here, three speed outputs and the strengths of slots 0 to 5.
const PART_STATE = 0xc06924dd;
const SLOT_EDIT = { source: 1, target: 3, lo: 10, hi: 20, follow: 1 };
/** Strength of a slot at MOD. DEPTH d for 0 <= lo < hi (the measured rule, section 2). */
const strength = (s, d) => s.lo + (((s.hi - s.lo + 1) * (2 * d + 1)) >> 8);

let emu;
let dir;
let original;
let edited;
let found;
before(async () => {
  if (skip) return;
  original = new Uint8Array(readFileSync(vsb));
  found = locateModTable(original);
  assert.equal(found.ok, true, found.reasons?.join(" "));
  const types = readModTypes(original, found.file);
  // Values that differ from the table's own, so a result that merely repeats the table proves nothing.
  const other = v => (v === 77 ? 33 : 77);
  types[EDITED] = { ...types[EDITED], depth: other(types[EDITED].depth), speed: other(types[EDITED].speed), slots: types[EDITED].slots.map((sl, k) => (k === 2 ? SLOT_EDIT : sl)) };
  const res = await exportModTypes(original, types);
  assert.equal(res.ok, true, res.reasons?.join(" "));
  edited = res.bytes;
  const dead = TABLES.get("table.modTypeStock").file;
  writeModType(edited, dead, DEAD, { depth: other(readModType(edited, dead, DEAD).depth), speed: other(readModType(edited, dead, DEAD).speed) });
  dir = mkdtempSync(join(tmpdir(), "gelumpe-modtable-"));
  const path = join(dir, "SYSTEM.VSB");
  writeFileSync(path, edited);
  emu = await startEmulator(path);
});
after(async () => {
  await emu?.stop();
  if (dir) rmSync(dir, { recursive: true, force: true });
});

async function device() {
  const s = new DeviceSession({ port: emu.port });
  await s.connect();
  const u32 = async a => readU32le(await s.readRamBlock(a, 4));
  const part = async () => {
    const base = (await u32(CURRENT_PATTERN.at)) + CURRENT_PATTERN.header;
    const n = (await s.screen()).part;
    const get = async id => (await s.readRamBlock(base + offsetOf(field(id), [n]), 1))[0];
    const strengths = Array.from(await s.readRamBlock(PART_STATE + 9 * n + 3, 6), b => (b > 127 ? b - 256 : b));
    return { part: n, type: await get("part.modType"), depth: await get("part.modDepth"), speed: await get("part.modSpeed"), strengths };
  };
  /** Turn MOD. TYPE one step at a time until the selected part holds `type`; returns what the part then holds. */
  const choose = async type => {
    let now = await part();
    for (let guard = 0; now.type !== type && guard < 80; guard++) {
      await emu.input({ kind: "encoder", index: MOD_TYPE_ENCODER, delta: now.type < type ? 1 : -1 });
      await emu.settle(250);
      now = await part();
    }
    assert.equal(now.type, type, "MOD. TYPE reached the type");
    return now;
  };
  return { s, choose };
}

test("modulation table: the copy the firmware reads is the copy the map names", { skip }, () => {
  assert.equal(found.file, TABLES.get("table.modType").file);
  assert.equal(found.place, "table.modType");
});

test("modulation table: an edited default depth and speed come to the part with MOD. TYPE, an edit of the unread copy does not", { skip }, async () => {
  const { choose } = await device();
  const was = readModType(original, found.file, EDITED);
  const now = readModType(edited, found.file, EDITED);
  assert.notDeepEqual([now.depth, now.speed], [was.depth, was.speed], "the edit changes the table");
  const hit = await choose(EDITED);
  assert.deepEqual([hit.depth, hit.speed], [now.depth, now.speed], "the part holds the edited depth and speed");
  assert.deepEqual(now.slots[2], SLOT_EDIT, "the edit is in the table");
  const slotWas = readModType(original, found.file, EDITED).slots[2];
  assert.deepEqual([slotWas.lo, slotWas.hi], [0, 0], "slot 2 had no strength in the file");
  assert.equal(hit.strengths[2], strength(SLOT_EDIT, hit.depth), "the edited slot reaches the part with the strength the measured rule gives");
  assert.ok(hit.strengths[2] >= SLOT_EDIT.lo, "and it is not 0");
  assert.deepEqual(hit.strengths.slice(3), [0, 0, 0], "the slots after it, empty in the table, stay 0");

  const dead = TABLES.get("table.modTypeStock").file;
  const ignored = readModType(edited, dead, DEAD);
  const table = readModType(original, found.file, DEAD);
  assert.notDeepEqual([ignored.depth, ignored.speed], [table.depth, table.speed], "the unread copy differs from the read one");
  const miss = await choose(DEAD);
  assert.deepEqual([miss.depth, miss.speed], [table.depth, table.speed], "the part holds what the read copy says, not the other copy");

  const plain = readModType(original, found.file, UNTOUCHED);
  const same = await choose(UNTOUCHED);
  assert.deepEqual([same.depth, same.speed], [plain.depth, plain.speed], "a type nobody edited keeps its table values");
});

test("modulation table: the export passes the emulator check with exactly its changed bytes allowed", { skip }, async () => {
  const types = readModTypes(original, found.file);
  types[5] = { ...types[5], name: "Mein EG", depth: 77, speed: 33, curve: 6, slots: types[5].slots.map((sl, k) => (k === 1 ? { source: 1, target: 8, lo: -20, hi: 40, follow: 0 } : sl)) };
  types[40] = { ...types[40], slots: types[40].slots.map((sl, k) => (k === 3 ? { ...sl, target: 9 } : sl)) };
  const res = await exportModTypes(original, types);
  assert.equal(res.ok, true, res.reasons?.join(" "));
  const patched = join(dir, "export.VSB");
  writeFileSync(patched, res.bytes);
  const allow = res.allow.flatMap(([at, n]) => ["--allow", `0x${at.toString(16)}:${n}`]);
  const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
  const args = [checker, "--base", vsb, "--patched", patched, ...(flash.length ? ["--flash", ...flash] : []), ...allow];
  const check = await exec(emuPython(), args, { timeout: 900_000, maxBuffer: 4 * 1024 * 1024 });
  assert.equal(check.status, 0, check.stderr || check.stdout);
  const report = JSON.parse(check.stdout);
  assert.equal(report.ok, true, JSON.stringify(report.checks.filter(c => !c.ok)));
  assert.deepEqual(report.changed, res.allow.map(([at, n]) => [`0x${at.toString(16)}`, n]), "the check saw the changed bytes and no others");
});
