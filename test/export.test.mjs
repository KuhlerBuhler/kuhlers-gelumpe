import { test } from "node:test";
import assert from "node:assert/strict";
import { exportVsb, sessionChanges, recordChanges } from "../src/export.mjs";
import { VsbImage } from "../src/image.mjs";
import { tableEntry } from "../src/map/address.mjs";
import { field, readRaw, sitesOf } from "../src/map/index.mjs";
import { makeFirmware, makeRecord } from "./helpers.mjs";

const gate = () => makeRecord("ifx", { name: "Gate Filter", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64] } });

async function sitting() {
  const vsb = await makeFirmware([{ kind: "ifx", slot: 50, record: gate() }]);
  const before = new VsbImage(vsb).read("ifx", 50).bytes;
  const after = Uint8Array.from(before);
  after.set([0x47, 0x45, 0x4c], 1);                 // name starts "GEL"
  const history = [
    { edit: { kind: "fxRecord", table: "ifx", slot: 50, bytes: after }, backups: [{ addr: tableEntry("table.ifx", 49).ram, bytes: Uint8Array.from(before) }] },
    { edit: { kind: "sites", fieldId: "menu.ifxCount", value: 53 }, backups: [{ addr: 0, bytes: Uint8Array.of(52) }] },
    { edit: { kind: "patternSend", block: new Uint8Array(0x4000) }, backups: null },
  ];
  return { vsb, before, after, history };
}

test("the export changes exactly the bytes the sitting changed", async () => {
  const { vsb, history, before, after } = await sitting();
  const res = await exportVsb(vsb, history);
  assert.equal(res.ok, true, res.reasons?.join(" "));
  assert.deepEqual([res.applied, res.skipped], [2, 1]);
  const diff = [];
  for (let i = 0; i < vsb.length; i++) if (vsb[i] !== res.bytes[i]) diff.push(i);
  const rec = tableEntry("table.ifx", 49).file;
  const sites = sitesOf(field("menu.ifxCount"), 53).filter(s => vsb[s.offset] !== s.value).map(s => s.offset);
  const inRecord = [...after.keys()].filter(i => after[i] !== before[i]).map(i => rec + i);
  assert.deepEqual(diff, [...inRecord, ...sites].sort((a, b) => a - b));
  assert.equal(readRaw(res.bytes, field("menu.ifxCount")).value, 53);
  assert.notEqual(res.bytes, vsb, "a copy; the loaded file stays as it was");
});

test("an undone edit is not in the history and so not in the export", async () => {
  const { vsb, history } = await sitting();
  const res = await exportVsb(vsb, history.slice(1));
  assert.equal(new VsbImage(res.bytes).read("ifx", 50).name, "Gate Filter");
});

test("a copy that fails the firmware check is refused", async () => {
  const { vsb, history } = await sitting();
  const broken = Uint8Array.from(vsb);
  broken[tableEntry("table.groove", 0).file] = 0;   // the groove marker
  const res = await exportVsb(broken, history);
  assert.equal(res.ok, false);
  assert.match(res.reasons.join(" "), /Groove/);
});

test("the change list names fields, old and new values, and skips patterns", async () => {
  const { history, before, after } = await sitting();
  const list = sessionChanges(history);
  assert.deepEqual(list.map(c => [c.target, c.firmware]), [["IFX 50", true], ["Einträge im Insert-Menü", true], ["Pattern-Puffer", false]]);
  assert.deepEqual(list[0].fields.map(f => [f.field, f.old, f.new]), [["fx.name", "Gate Filter", "GELe Filter"]]);
  assert.deepEqual(list[1].fields.map(f => [f.old, f.new]), [["52", "53"]]);
  assert.deepEqual(recordChanges(before, before), []);
  const stray = Uint8Array.from(after);
  stray[0x200] ^= 0xff;
  assert.ok(recordChanges(before, stray).some(c => c.field !== "fx.name"), "a changed byte outside known fields is still listed");
});
