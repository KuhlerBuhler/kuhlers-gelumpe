// Catalog effects as records of a firmware, for tools/emu/blue_fx_probe.py. Blue repeats fx-append by hand because
// src/presets.mjs knows only the Sampler's places.  Usage: node tools/emu/blue_fx_records.mjs red|blue FILE.VSB > out.json
import { readFileSync } from "node:fs";
import { appendPresets } from "../../src/fx-append.mjs";
import { recordOf, RECORD } from "../../src/presets.mjs";
import { fxToRecord } from "../../src/fx-v2.mjs";
import { parseUnits } from "../../src/units.mjs";

const BLUE = { ifx: { array: 0xc009898c, count: 38 }, mfx: { array: 0xc0099d88, count: 32 } };
const [which, path] = process.argv.slice(2);
const vsb = new Uint8Array(readFileSync(path));
const patch = JSON.parse(readFileSync(new URL("../../data/patches/fx-catalog.json", import.meta.url), "utf8"));
const hex = b => Buffer.from(b).toString("hex");
let rows;
if (which === "red") {
  const r = appendPresets(vsb, patch);
  if (!r.ok) throw new Error(r.reasons.join("; "));
  rows = r.added.map(a => { const at = recordOf(r.bytes, a.kind, a.slot); return { ...a, record: hex(r.bytes.subarray(at.file, at.file + RECORD)) }; });
} else {
  const view = new DataView(vsb.buffer, vsb.byteOffset, vsb.byteLength);
  const file = ram => ram - 0xc0000000 + 0x100;
  const records = kind => Array.from({ length: 100 }, (_, i) => view.getUint32(file(BLUE[kind].array) + 4 * i, true)).map(p => vsb.slice(file(p), file(p) + RECORD));
  const units = parseUnits(patch.units ?? {});
  const next = { ifx: BLUE.ifx.count, mfx: BLUE.mfx.count };
  rows = patch.presets.map(p => {
    const all = records(p.kind);
    const made = fxToRecord(p, all[0], all, units);
    if (!made.ok) throw new Error(`${p.name}: ${made.reason}`);
    next[p.kind] += 1;
    return { kind: p.kind, slot: next[p.kind], name: p.name, record: hex(made.record) };
  });
}
process.stdout.write(JSON.stringify(rows));
