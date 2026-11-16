import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PATCH_FORMAT, fromHex } from "../src/patch.mjs";

// SOFTWARE UPDATE refuses a SYSTEM.VSB that is not 0x200100 bytes or not read whole (docs/messungen/2026-11-13-update-schutz.md).
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const file = addr => addr - 0xc0000000 + 0x100;
const CODE = 0xc014ee00;
const target = (site, hex) => {
  const bytes = fromHex(hex);
  const word = new DataView(bytes.buffer, bytes.byteOffset, 4).getUint32(0, true);
  assert.equal(word >>> 24, 0xeb, "bl");
  return (site + 8 + (((word & 0xffffff) << 8) >> 6)) >>> 0;
};

for (const [name, path, builds, sites] of [
  ["red", "data/patches/update-guard.json", ["hacktribe", "stock"], [0xc00309e0, 0xc003a968, 0xc003a9fc, 0xc003ad4c, 0xc003ae24]],
  ["blue", "data/patches/update-guard-synth.json", ["synth"], [0xc002d7c8, 0xc00353b4, 0xc0035448, 0xc003579c, 0xc0035874]],
]) {
  const patch = read(path);

  test(`the ${name} patch routes all five f_read calls of SOFTWARE UPDATE to ug_read`, () => {
    assert.equal(patch.format, PATCH_FORMAT);
    assert.equal(patch.id, "update-guard");
    assert.deepEqual(patch.builds, builds);
    assert.deepEqual(patch.ram, []);
    assert.equal(patch.changes[0].file, file(CODE));
    assert.ok(fromHex(patch.changes[0].bytes).length <= 0x100);
    assert.deepEqual(patch.changes.slice(1).map(c => c.file), sites.map(file));
    for (const [i, site] of sites.entries()) assert.equal(target(site, patch.changes[i + 1].bytes), CODE, `site 0x${site.toString(16)}`);
    assert.deepEqual(patch.hooks.map(h => Number(h.site)), sites);
    assert.ok(patch.hooks.every(h => h.chain === "update-read" && h.kind === "call"));
  });
}

test("both BLECH sets carry the patch", () => {
  assert.ok(read("data/patches/blech.json").patches.includes("data/patches/update-guard.json"));
  assert.ok(read("data/patches/blech-synth.json").patches.includes("data/patches/update-guard-synth.json"));
});
