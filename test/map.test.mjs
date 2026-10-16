import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import {
  FIELDS, BLOCKS, TABLES, instances, offsetOf, byteSpans, typeOf, readRaw, writeRaw, applies, conditionOffset,
} from "../src/map/index.mjs";
import { generate } from "../tools/units-to-map.mjs";
import { CONVERTERS } from "../src/map/convert.mjs";
import FINDINGS from "../data/findings.mjs";
import ranges from "../data/map/fx-ranges.mjs";
import { VSB_CHECKS, PATTERN_CHECKS } from "./factory-checks.mjs";
import * as layout from "../src/layout.mjs";
import { REC, TABLE, TABLES as LAYOUT_TABLES, IFX_COUNT_FILE, IFX_LAST_INDEX_FILE, MFX_COUNT_RAM, MAP, RECORD_SIZE } from "../src/layout.mjs";

const SOURCES = new Set(["korg-spec", "measured", "derived", "unknown"]);
const TRANSPORTS = new Set(["pattern-sysex", "e2sallpat", "e2spat", "global-sysex", "ram", "firmware", "cc"]);
const EDIT = new Set([undefined, "plain", "expert", "readonly"]);
const FIRMWARE_BLOCKS = new Set(["firmware"]);
const frozen = JSON.parse(readFileSync(new URL("./fixtures/known-offsets.json", import.meta.url), "utf8"));
const frozenFindings = JSON.parse(readFileSync(new URL("./fixtures/known-findings.json", import.meta.url), "utf8"));

/** The fixed forms evidence may take. A bare pointer at a document is not one of them. */
function checkEvidence(where, source, evidence) {
  if (source === "unknown") return;
  assert.ok(evidence, `${where}: source ${source} needs evidence`);
  const m = /^(measure|factory-check|korg-spec|derived):(.+)$/.exec(evidence);
  assert.ok(m, `${where}: evidence "${evidence}" has no recognised form`);
  const [, kind, rest] = m;
  if (kind === "measure") {
    const mm = /^(\d{4}-\d{2}-\d{2})\/([a-z0-9-]+)$/.exec(rest);
    assert.ok(mm, `${where}: measure evidence must read measure:<date>/<name>, got ${evidence}`);
    const file = new URL(`../docs/messungen/${mm[1]}-${mm[2]}.md`, import.meta.url);
    assert.ok(existsSync(file), `${where}: no measurement at docs/messungen/${mm[1]}-${mm[2]}.md`);
  }
  if (kind === "factory-check") {
    assert.ok(rest in VSB_CHECKS || rest in PATTERN_CHECKS, `${where}: no factory check called ${rest}`);
  }
  if (kind === "measure" || kind === "factory-check") {
    assert.ok(source === "measured", `${where}: ${kind} evidence belongs to source measured, not ${source}`);
  }
  if (kind === "korg-spec") assert.equal(source, "korg-spec", `${where}: korg-spec evidence with source ${source}`);
  if (kind === "derived") assert.equal(source, "derived", `${where}: derived evidence with source ${source}`);
}

test("every field is complete", () => {
  for (const f of FIELDS.values()) {
    assert.ok(f.label?.de && f.label?.en, `${f.id}: label in both languages`);
    assert.ok(f.area, `${f.id}: no area`);
    assert.ok(Boolean(f.where) !== Boolean(f.sites), `${f.id}: exactly one of where and sites`);
    assert.ok(SOURCES.has(f.source), `${f.id}: source ${f.source}`);
    assert.ok(EDIT.has(f.edit), `${f.id}: edit ${f.edit}`);
    assert.ok(Array.isArray(f.transport), `${f.id}: transport is a list`);
    for (const t of f.transport) assert.ok(TRANSPORTS.has(t), `${f.id}: unknown transport ${t}`);
    typeOf(f);
    if (FIRMWARE_BLOCKS.has(f.block)) assert.ok(f.firmware, `${f.id}: lives in the firmware, needs a firmware version`);
  }
});

test("ids are unique across blocks", () => {
  // The loader throws on a duplicate; reaching here with all fields loaded is the check.
  const ids = [...FIELDS.keys()];
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(ids.length > 600);
});

test("every converter a field names exists", () => {
  for (const f of FIELDS.values()) {
    if (f.convert) assert.ok(CONVERTERS[f.convert], `${f.id}: converter ${f.convert} does not exist`);
  }
});

// A converter only searches its own domain. A field range wider than that
// would let toRaw clamp a value silently into a wrong but legal byte.
test("every field's range lies inside its converter's domain", () => {
  for (const f of FIELDS.values()) {
    if (!f.convert || !f.range) continue;
    const c = CONVERTERS[f.convert];
    assert.ok(f.range[0] >= c.domain[0] && f.range[1] <= c.domain[1],
      `${f.id}: range ${f.range} is wider than ${f.convert} (${c.domain})`);
  }
});

test("a field nobody understands is only editable in expert mode", () => {
  for (const f of FIELDS.values()) {
    if (f.source === "unknown") assert.equal(f.edit, "expert", `${f.id}: unknown but not expert`);
  }
});

test("repeat levels are positive whole numbers", () => {
  for (const f of FIELDS.values()) {
    for (const level of f.repeat || []) {
      assert.ok(Number.isInteger(level.count) && level.count > 0, `${f.id}: count ${level.count}`);
      assert.ok(Number.isInteger(level.stride) && level.stride > 0, `${f.id}: stride ${level.stride}`);
    }
  }
});

test("a condition points at the unit byte of the same stage", () => {
  const device = FIELDS.get("fx.stage.device");
  const deviceBytes = new Set(instances(device).map(ix => offsetOf(device, ix)));
  for (const f of FIELDS.values()) {
    if (!f.when) continue;
    for (const ix of instances(f)) {
      const cond = conditionOffset(f, ix);
      assert.ok(deviceBytes.has(cond), `${f.id} ${ix}: condition byte ${cond} is no unit byte`);
      const at = offsetOf(f, ix);
      assert.ok(at > cond && at < cond + device.repeat[0].stride, `${f.id} ${ix}: parameter outside its stage`);
    }
  }
});

test("tables lie inside the firmware and do not overlap each other or its fields", () => {
  const size = BLOCKS.get("firmware").size;
  const spans = [];
  for (const t of TABLES.values()) {
    assert.ok(BLOCKS.has(t.block), `${t.id}: no block ${t.block}`);
    const entry = t.length ?? BLOCKS.get(t.block).size;
    assert.ok(t.stride >= entry, `${t.id}: entries overlap (stride ${t.stride} < ${entry})`);
    spans.push([t.file, t.file + (t.count - 1) * t.stride + entry, t.id]);
  }
  for (const f of BLOCKS.get("firmware").fields) for (const [a, b] of byteSpans(f)) spans.push([a, b, f.id]);
  for (const [a, b, id] of spans) assert.ok(a >= 0 && b <= size, `${id}: outside the image`);
  spans.sort((x, y) => x[0] - y[0]);
  for (let i = 1; i < spans.length; i++) {
    assert.ok(spans[i][0] >= spans[i - 1][1], `${spans[i - 1][2]} and ${spans[i][2]} overlap`);
  }
});

test("the generated unit parameters match units.json and the record map", () => {
  const onDisk = readFileSync(new URL("../data/map/fx-params.mjs", import.meta.url), "utf8");
  assert.equal(generate().out, onDisk, "run node tools/units-to-map.mjs");
});

test("every range fits its type", () => {
  for (const f of FIELDS.values()) {
    if (!f.range) continue;
    const t = typeOf(f);
    assert.equal(t.kind, "int", `${f.id}: a range on a ${t.name} field`);
    assert.ok(f.range[0] >= t.min && f.range[1] <= t.max, `${f.id}: range ${f.range} does not fit ${t.name}`);
    assert.ok(f.range[0] <= f.range[1], `${f.id}: range is upside down`);
  }
});

test("every instance of every field lies inside its block", () => {
  for (const f of FIELDS.values()) {
    const size = BLOCKS.get(f.block).size;
    for (const [start, end] of byteSpans(f)) {
      assert.ok(start >= 0 && end <= size, `${f.id}: bytes ${start} to ${end} fall outside ${f.block} (${size})`);
    }
  }
});

test("no two fields claim the same bytes", () => {
  for (const block of BLOCKS.values()) {
    const owner = new Map();
    for (const field of block.fields) {
      const all = field.sites ? [null] : instances(field);
      byteSpans(field).forEach(([start, end], i) => {
        const f = { id: field.id, when: field.when, cond: field.when ? conditionOffset(field, all[i]) : null };
        for (let b = start; b < end; b++) {
          const prev = owner.get(b) || [];
          for (const other of prev) {
            // Two parameters of different units share a byte; which one it is
            // depends on the unit byte of that very instance.
            const exclusive = f.when && other.when && f.cond === other.cond && f.when.equals !== other.when.equals;
            assert.ok(exclusive, `${block.name} byte ${b}: claimed by ${other.id} and ${f.id}`);
          }
          prev.push(f);
          owner.set(b, prev);
        }
      });
    }
  }
});

test("evidence has a fixed form and points at something that exists", () => {
  for (const f of FIELDS.values()) checkEvidence(f.id, f.source, f.evidence);
  for (const t of TABLES.values()) {
    assert.ok(t.firmware, `${t.id}: a table in the firmware needs a firmware version`);
    checkEvidence(t.id, t.source, t.evidence);
  }
});

test("findings follow the same rules", () => {
  const ids = new Set();
  for (const f of FINDINGS) {
    assert.ok(!ids.has(f.id), `finding ${f.id} twice`);
    ids.add(f.id);
    assert.ok(SOURCES.has(f.source), `${f.id}: source ${f.source}`);
    checkEvidence(f.id, f.source, f.evidence);
  }
});

test("a bare document reference is not evidence", () => {
  assert.throws(() => checkEvidence("x", "measured", "docs/research.md"));
  assert.throws(() => checkEvidence("x", "measured", "measure:2026-09-17/does-not-exist"));
  assert.throws(() => checkEvidence("x", "measured", "measure:yesterday"));
  assert.throws(() => checkEvidence("x", "measured", "factory-check:nothing-like-this"));
  assert.throws(() => checkEvidence("x", "derived", "measure:2026-09-17/osc-pitch"));
});

// Frozen before layout.mjs became a view on the map. Comparing the map with
// layout.mjs now would compare the map with itself.
test("the map covers every offset known before it existed", () => {
  const rec = frozen.record;
  assert.equal(FIELDS.get("fx.name").where.offset, rec.name);
  assert.equal(typeOf(FIELDS.get("fx.name")).width, rec.nameWidth);
  const row = FIELDS.get("fx.map.source");
  assert.equal(row.where.offset, rec.map);
  assert.equal(row.repeat[0].count, rec.mapEntries);
  assert.equal(row.repeat[0].stride, rec.mapEntrySize);
  for (const [k, at] of Object.entries(rec.mapFields)) {
    assert.equal(FIELDS.get(`fx.map.${k}`).where.offset - rec.map, at, `map field ${k}`);
  }
  const device = FIELDS.get("fx.stage.device");
  device.repeat[0].names.forEach((name, i) => {
    assert.equal(offsetOf(device, [i]), rec.stages[name].device, `${name} device`);
  });
  assert.equal(offsetOf(FIELDS.get("fx.ifx.0x0a.dry_wet"), [0]), rec.stages.ifx1.params);
  assert.equal(offsetOf(FIELDS.get("fx.ifx.0x0a.dry_wet"), [1]), rec.stages.ifx2.params);
  assert.equal(FIELDS.get("fx.mfx.0x3b.dry_wet").where.offset, rec.stages.mfx.params);
  assert.equal(BLOCKS.get("fxRecord").size, frozen.recordSize);

  const ram = f => f - 0x100 + 0xc0000000;
  assert.equal(ram(TABLES.get("table.mfx").file), frozen.tables.mfx.ram);
  assert.equal(ram(TABLES.get("table.ifx").file), frozen.tables.ifx.ram);
  assert.equal(TABLES.get("table.mfx").count, frozen.tables.mfx.slots);
  for (const [id, key] of [["table.groove", "grooveTemplates"], ["table.modType", "modulationTypes"]]) {
    const t = TABLES.get(id);
    assert.deepEqual({ file: t.file, ram: ram(t.file), stride: t.stride, count: t.count }, frozen.tables[key], id);
  }
  assert.equal(FIELDS.get("crc16").where.offset, frozen.tables.crc16.file);
  assert.equal(FIELDS.get("splash").where.offset, frozen.tables.splashBitmap.file);
  assert.equal(TABLES.get("table.initPattern").file, frozen.tables.initPattern.file);
  assert.equal(ram(FIELDS.get("menu.mfxCount").where.offset), frozen.mfxCountRam);
  const sites = FIELDS.get("menu.ifxCount").sites;
  assert.deepEqual(sites.filter(s => s.value === "count").map(s => s.file), frozen.ifxCountFile);
  assert.deepEqual(sites.filter(s => s.value === "count - 1").map(s => s.file), frozen.ifxLastIndexFile);
});

test("layout.mjs, now a view, still says what it said before", () => {
  assert.equal(RECORD_SIZE, frozen.recordSize);
  assert.deepEqual(REC.stage, frozen.record.stages);
  assert.deepEqual(MAP, frozen.record.mapFields);
  assert.equal(REC.name, frozen.record.name);
  assert.equal(TABLE.mfx.ram, frozen.tables.mfx.ram);
  assert.equal(TABLE.ifx.ram, frozen.tables.ifx.ram);
  assert.deepEqual(LAYOUT_TABLES.grooveTemplates, frozen.tables.grooveTemplates);
  assert.deepEqual(LAYOUT_TABLES.crc16, frozen.tables.crc16);
  assert.deepEqual(IFX_COUNT_FILE, frozen.ifxCountFile);
  assert.deepEqual(IFX_LAST_INDEX_FILE, frozen.ifxLastIndexFile);
  assert.equal(MFX_COUNT_RAM, frozen.mfxCountRam);
});

test("a field writes exactly its own bytes and reads back what it wrote", () => {
  const bytes = new Uint8Array(0x4000).fill(0xa5);
  const cutoff = FIELDS.get("part.cutoff");
  writeRaw(bytes, cutoff, [3], 90);
  const changed = [...bytes.keys()].filter(i => bytes[i] !== 0xa5);
  assert.deepEqual(changed, [0x800 + 3 * 0x330 + 13]);
  assert.equal(readRaw(bytes, cutoff, [3]), 90);

  const pan = FIELDS.get("part.pan");
  writeRaw(bytes, pan, [0], -20);
  assert.equal(bytes[0x800 + 25], 236);
  assert.equal(readRaw(bytes, pan, [0]), -20);

  assert.throws(() => writeRaw(bytes, cutoff, [3], 128), /outside/);
  assert.throws(() => writeRaw(bytes, cutoff, [16], 1), /out of range/);
  assert.throws(() => writeRaw(bytes, FIELDS.get("pattern.magic"), [], new Uint8Array(4)), /read only/);
});

test("a multi-site field writes every site, and a disagreement is visible", () => {
  const image = new Uint8Array(0x200000);
  const f = FIELDS.get("menu.ifxCount");
  writeRaw(image, f, [], 61);
  for (const s of f.sites) assert.equal(image[s.file], s.value === "count" ? 61 : 60);
  assert.deepEqual(readRaw(image, f), { value: 61, agreed: true, values: f.sites.map(s => (s.value === "count" ? 61 : 60)) });
  image[f.sites[3].file] = 59;
  assert.equal(readRaw(image, f).agreed, false);
});

test("a unit parameter only means something when its unit sits in the stage", () => {
  const record = new Uint8Array(0x20c);
  const f = FIELDS.get("fx.ifx.0x0a.dry_wet");
  record[0x12a] = 0x0a;
  record[0x174] = 0x06;
  assert.equal(applies(record, f, [0]), true);
  assert.equal(applies(record, f, [1]), false);
  writeRaw(record, f, [0], 50);
  assert.throws(() => writeRaw(record, f, [1], 50), /not in this stage/);
  assert.equal(record[0x174 + 0x0b], 0);
  assert.throws(() => applies(record, f, [2]), /out of range/);
});

test("fields are frozen through and through", () => {
  const f = FIELDS.get("fx.ifx.0x0a.dry_wet");
  assert.throws(() => { "use strict"; f.range[1] = 255; });
});

test("repeats expand to every combination", () => {
  assert.equal(instances(FIELDS.get("step.note")).length, 16 * 64 * 4);
  assert.equal(offsetOf(FIELDS.get("step.note"), [15, 63, 3]), 0x800 + 15 * 0x330 + 0x30 + 63 * 12 + 4 + 3);
});

// The linter's messages quote these notes; a change in wording or value
// would otherwise go unnoticed. The one deliberate change is the ring
// modulator in stage one, heard as silent after this fixture was taken.
test("the behaviour knowledge moved into the findings unchanged", () => {
  const json = v => JSON.parse(JSON.stringify(v));
  for (const key of ["STAGE2", "FACTORY_CHAINS", "MFX_MUTE", "REFUTED", "PLAY_ROW_RESYNCS", "OFF_AT", "LOUDNESS", "MFX_DEVICE_RANGE", "SOURCES", "CHAINS"]) {
    assert.deepEqual(json(layout[key]), frozenFindings[key], key);
  }
  const solo = json(layout.STAGE1_NEEDS_SOLO);
  assert.deepEqual(solo["9"], frozenFindings.STAGE1_NEEDS_SOLO["9"]);
  assert.deepEqual(Object.keys(solo).sort(), ["22", "9"]);
  assert.equal(solo["22"].verdict, "silent");
});

test("every known device carries measured evidence", async () => {
  const { default: devices } = await import("../data/devices.mjs");
  assert.ok(devices.length > 0);
  for (const d of devices) {
    assert.equal(d.version.length, 2);
    checkEvidence(`device ${d.version.join(".")}`, "measured", d.evidence);
  }
  const ins = FIELDS.get("menu.mfxCount").instruction;
  checkEvidence("menu.mfxCount instruction", "measured", ins.evidence);
});

test("the DSP table ranges line up with the unit list and say where they came from", () => {
  checkEvidence("fx-ranges", "derived", ranges.evidence);
  assert.match(ranges.evidence, /^derived:vsb-table\/0x[0-9A-F]{8}$/);
  const units = JSON.parse(readFileSync(new URL("../data/units.json", import.meta.url), "utf8"));
  for (const [id, list] of Object.entries(ranges.units)) {
    const entry = units.ifx_device[id] ?? units.mfx_device[id];
    assert.ok(entry, `${id}: no such unit in units.json`);
    assert.equal(list.length, entry.params.length, `${id} ${entry.unit}: parameter count differs from units.json`);
    for (const [min, max] of list) {
      assert.ok(Number.isInteger(min) && Number.isInteger(max) && min <= max, `${id}: span ${min} to ${max}`);
      assert.ok(max - min <= 127, `${id}: span ${min} to ${max} does not fit a 7-bit byte`);
    }
  }
});

test("a parameter with a table range names its evidence, and a negative minimum is shifted", () => {
  let shifted = 0;
  for (const f of FIELDS.values()) {
    if (!f.rangeEvidence) continue;
    checkEvidence(f.id, "derived", f.rangeEvidence);
    const [min, max] = ranges.units[f.id.split(".")[2]][f.paramIndex];
    assert.deepEqual(f.range, min < 0 ? [0, max - min] : [0, max], f.id);
    if (min < 0) {
      assert.equal(f.convert, `fxShift${-min}`, f.id);
      shifted++;
    }
  }
  assert.ok(shifted > 50, `${shifted} shifted parameters`);
});

test("a parameter with a choice list from the DSP text functions names its evidence and fits the list", () => {
  const named = [...FIELDS.values()].filter(f => f.choiceEvidence);
  assert.ok(named.length > 0);
  for (const f of named) {
    checkEvidence(f.id, "derived", f.choiceEvidence);
    const c = CONVERTERS[f.convert];
    assert.equal(f.range[0], 0, f.id);
    const names = c.choices ? c.choices.length : c.domain[1] + 1;
    assert.ok(f.range[1] <= names - 1, `${f.id}: range ${f.range} runs past the ${names} names`);
  }
});
