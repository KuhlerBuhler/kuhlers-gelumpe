#!/usr/bin/env node
/**
 * Generate data/patches/fx-catalog.json from data/fx/catalog.mjs: the catalog's insert and master effects, appended
 * behind the firmware's presets when the BLECH set is applied (src/fx-append.mjs).
 *
 *   node tools/fx-catalog-patch.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { FX_CATALOG } from "../data/fx/catalog.mjs";
import { APPEND_FORMAT } from "../src/fx-append.mjs";

const ROOT = new URL("../", import.meta.url);
const units = JSON.parse(readFileSync(new URL("data/units.json", ROOT), "utf8"));

const presets = FX_CATALOG.filter(p => p.kind === "ifx" || p.kind === "mfx").map(({ description, ...p }) => p);
const used = { ifx_device: {}, mfx_device: {} };
for (const p of presets) {
  for (const s of p.stages) {
    const key = s.stage === "mfx" ? "mfx_device" : "ifx_device";
    const id = `0x${s.unit.toString(16).padStart(2, "0")}`;
    if (!units[key][id]) throw new Error(`${p.name}: unit ${id} is not in data/units.json`);
    used[key][id] = units[key][id];
  }
}

const patch = {
  format: APPEND_FORMAT,
  version: 1,
  id: "fx-catalog",
  name: "Effekte aus dem Katalog",
  builds: ["hacktribe", "stock"],
  notNeededOn: ["synth"],
  ram: [],
  presets,
  units: used,
};
writeFileSync(new URL("data/patches/fx-catalog.json", ROOT), JSON.stringify(patch, null, 1) + "\n");
console.log(`${presets.filter(p => p.kind === "ifx").length} insert, ${presets.filter(p => p.kind === "mfx").length} master`);
