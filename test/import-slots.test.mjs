import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { CHAINS } from "../data/hooks.mjs";

// IMPORT SAMPLE onto the factory slots (docs/messungen/2026-11-16-import-werks-slots.md): the destination selector wraps at
// the first slot the import takes instead of at 501.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const HACK = read("data/patches/import-slots.json");
const STOCK = read("data/patches/import-slots-stock.json");
const SITE = 0x6a23c + 0x100;          // file offset of 0xC006A23C, the selector's range test
const WAS = "7d0f51e31f1e81d2031081d2020000dafa0f51e31f1e41a2031041a2";

// the range test, run on the selector's new value as the firmware would
function wrap(bytes, value) {
  const w = [...Array(7)].map((_, i) => Buffer.from(fromHex(bytes)).readUInt32LE(i * 4));
  const imm = word => { const rot = ((word >>> 8) & 0xf) * 2, v = word & 0xff; return ((v >>> rot) | (v << (32 - rot))) >>> 0; };
  const sub = imm(w[0]), lowest = sub + imm(w[1]), span = imm(w[2]) + imm(w[3]);
  assert.equal(imm(w[4]), 1000);
  assert.equal(imm(w[5]) + imm(w[6]), span);
  if (value < lowest) value += span;
  if (value >= 1000) value -= span;
  return value;
}

test("both variants have the v1 format, replace the seven measured instructions and declare no RAM", () => {
  for (const [patch, build] of [[HACK, "hacktribe"], [STOCK, "stock"]]) {
    assert.equal(patch.format, PATCH_FORMAT);
    assert.equal(patch.id, "import-slots");
    assert.deepEqual(patch.builds, [build]);
    assert.deepEqual(patch.ram, []);
    assert.equal(patch.changes.length, 1);
    const [change] = patch.changes;
    assert.equal(change.file, SITE);
    assert.equal(fromHex(change.bytes).length, WAS.length / 2);
    assert.equal(change.expect, createHash("sha256").update(Buffer.from(WAS, "hex")).digest("hex"));
  }
});

test("the selector runs from the first importable number to 999 and wraps at both ends", () => {
  for (const [patch, lowest] of [[HACK, 275], [STOCK, 19]]) {
    const bytes = patch.changes[0].bytes;
    assert.equal(wrap(bytes, lowest), lowest);
    assert.equal(wrap(bytes, 999), 999);
    assert.equal(wrap(bytes, lowest - 1), 999, "one below the lowest number is 999");
    assert.equal(wrap(bytes, 1000), lowest, "one above 999 is the lowest number");
    assert.equal(wrap(bytes, 501), 501, "the user slots stay where they were");
  }
});

test("its hook is in the register and the BLECH set carries both variants", () => {
  const sites = Object.values(CHAINS).flat().flatMap(stage => stage.sites);
  for (const patch of [HACK, STOCK]) for (const hook of patch.hooks) assert.ok(CHAINS[hook.chain] && sites.includes(Number(hook.site)), hook.site);
  const set = read("data/patches/blech.json").patches;
  assert.ok(set.includes("data/patches/import-slots.json") && set.includes("data/patches/import-slots-stock.json"));
});
