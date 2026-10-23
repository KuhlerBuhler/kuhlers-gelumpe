import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { FX_CATALOG } from "../data/fx/catalog.mjs";
import { APPEND_FORMAT, appendPresets } from "../src/fx-append.mjs";

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
