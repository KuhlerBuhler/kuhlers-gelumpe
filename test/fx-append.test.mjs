import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { FX_CATALOG } from "../data/fx/catalog.mjs";
import { APPEND_FORMAT, appendPresets } from "../src/fx-append.mjs";
import { addPreset, menuLength, recordOf, RECORD } from "../src/presets.mjs";
import { FxRecord } from "../src/record.mjs";
import { makeFirmwareWithArrays, makeRecord } from "./helpers.mjs";

const patch = JSON.parse(readFileSync(new URL("../data/patches/fx-catalog.json", import.meta.url), "utf8"));

test("data/patches/fx-catalog.json carries the catalog's insert and master effects as they are (node tools/fx-catalog-patch.mjs)", () => {
  assert.equal(patch.format, APPEND_FORMAT);
  const effects = FX_CATALOG.filter(p => p.kind === "ifx" || p.kind === "mfx").map(({ description, ...p }) => p);
  assert.deepEqual(patch.presets, JSON.parse(JSON.stringify(effects)));
  const used = new Set(effects.flatMap(p => p.stages.map(s => `${s.stage === "mfx" ? "mfx" : "ifx"}:${s.unit}`)));
  const carried = new Set(["ifx", "mfx"].flatMap(k => Object.keys(patch.units[`${k}_device`]).map(id => `${k}:${Number(id)}`)));
  assert.deepEqual([...carried].sort(), [...used].sort(), "the parameter lists of exactly the units the effects use");
});

test("an image whose preset tables are not known is refused, nothing is written", () => {
  const res = appendPresets(new Uint8Array(0x200100), patch);
  assert.equal(res.ok, false);
  assert.match(res.reasons[0], /Preset-Tabellen/);
});

test("the catalog starts at the slot behind Korg's 2.02 presets, Hacktribe's own inserts first", () => {
  assert.deepEqual(patch.first, { ifx: 39, mfx: 33 });
  const remakes = patch.presets.filter(p => p.hacktribe).map(p => p.name);
  assert.deepEqual(remakes, ["Lag", "KP2 Comp", "LP Drive", "LP Drive Res", "HP Drive", "HP Res Drive", "BP Drive", "BP Drive Res", "9/32 Delay", "3/32 Delay", "1/12 Delay"]);
  assert.deepEqual(patch.presets.filter(p => p.kind === "ifx").slice(0, 11).map(p => p.name), remakes, "on slots 39 to 49, as on Hacktribe");
});

describe("a fixed order (`first`)", () => {
  const base = () => makeFirmwareWithArrays([{ kind: "ifx", slot: 1, record: makeRecord("ifx", { name: "Werk", devices: { ifx1: 24, ifx2: 0 } }) }], { patched: true });
  const pick = (bytes, ...names) => ({ ...patch, first: { ifx: menuLength(bytes, "ifx").value + 1, mfx: 33 }, presets: names.map(n => patch.presets.find(p => p.name === n)) });
  const name = (bytes, slot) => new FxRecord(bytes.slice(recordOf(bytes, "ifx", slot).file, recordOf(bytes, "ifx", slot).file + RECORD), "ifx").name;

  test("a file with the catalog of an older release in another order ends up as a fresh one", async () => {
    const bytes = await base();
    const at = menuLength(bytes, "ifx").value + 1;
    const fresh = appendPresets(bytes, pick(bytes, "Lag", "1/6 Delay", "1/24 Delay"));
    assert.equal(fresh.ok, true, fresh.reasons.join(" "));
    const older = appendPresets(bytes, { ...pick(bytes, "1/6 Delay", "1/24 Delay"), first: undefined });
    assert.equal(name(older.bytes, at), "1/6 Delay");
    const updated = appendPresets(older.bytes, pick(bytes, "Lag", "1/6 Delay", "1/24 Delay"));
    assert.equal(updated.ok, true, updated.reasons.join(" "));
    assert.deepEqual([at, at + 1, at + 2].map(s => name(updated.bytes, s)), ["Lag", "1/6 Delay", "1/24 Delay"]);
    assert.deepEqual(updated.bytes, fresh.bytes);
  });

  test("a slot with a preset that is not the patch's ends the fixed order, nothing of it is written over", async () => {
    const bytes = await base();
    const own = addPreset(bytes, "ifx", 1);
    assert.equal(own.ok, true, own.reasons.join(" "));
    const res = appendPresets(own.bytes, pick(bytes, "Lag", "1/6 Delay"));
    assert.equal(res.ok, true, res.reasons.join(" "));
    assert.deepEqual([own.slot, own.slot + 1, own.slot + 2].map(s => name(res.bytes, s)), [own.name, "Lag", "1/6 Delay"]);
  });
});
