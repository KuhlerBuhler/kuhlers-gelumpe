#!/usr/bin/env node
/**
 * Adds FX presets to a copy of a SYSTEM.VSB the way the editor does (src/presets.mjs): each new one is a copy of an
 * existing preset, the menu length goes up in every place it lives.
 *
 *   node tools/preset-add.mjs --vsb SYSTEM.VSB --out NEW.VSB [--ifx N] [--mfx N] [--from SLOT]
 *
 * N is how many to add (`max` fills the table). The source preset is slot --from (1-based, default 1).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { addPreset, presetRoom } from "../src/presets.mjs";

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith("--") ? [...acc, [a.slice(2), all[i + 1]]] : acc), []));
if (!args.vsb || !args.out) {
  console.error("usage: preset-add.mjs --vsb SYSTEM.VSB --out NEW.VSB [--ifx N|max] [--mfx N|max] [--from SLOT]");
  process.exit(2);
}
let bytes = new Uint8Array(readFileSync(args.vsb));
const from = Number(args.from ?? 1);
for (const kind of ["ifx", "mfx"]) {
  if (args[kind] === undefined) continue;
  const room = presetRoom(bytes, kind);
  const want = args[kind] === "max" ? room.capacity - room.count : Number(args[kind]);
  for (let i = 0; i < want; i++) {
    const added = addPreset(bytes, kind, from, { overwrite: "overwrite" in args });
    if (!added.ok) { console.error(`${kind}: ${added.reasons.join(" ")}`); process.exit(1); }
    bytes = added.bytes;
  }
  console.log(`${kind}: menu length ${room.count} -> ${presetRoom(bytes, kind).count} (capacity ${room.capacity})`);
}
writeFileSync(args.out, bytes);
