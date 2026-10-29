import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { CHAINS } from "../data/hooks.mjs";

// Last pattern at power-on (idea 76, docs/messungen/2026-10-28-letztes-pattern.md): the selection notes its number in
// Global byte 248, the start function and the first selection after power-on take it.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const PATCH = read("data/patches/last-pattern.json");
const SET = read("data/patches/blech.json");
const CODE = 0x14ff00;               // file offset of 0xC014FE00
const CODE_END = 0x150000;           // 0xC014FF00
const BOOT_SITE = 0x2b040;           // 0xC002AF40, mov r1, #0 in the start function
const SELECT_SITE = 0x79ec8;         // 0xC0079DC8, mov r4, r0 in the pattern selection

const target = (change, at) => {
  const word = Buffer.from(fromHex(change.bytes)).readUInt32LE(0);
  assert.equal(word >>> 24, 0xeb, "branch with link");
  return at + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
};

test("the last-pattern patch has the v1 format and copies nothing of the firmware", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "last-pattern");
  assert.deepEqual(PATCH.builds, ["hacktribe", "stock"]);
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/);
    assert.equal(change.copy, undefined);
  }
  assert.deepEqual(PATCH.ram.map(r => [r.at, r.length]), [["0xC014FEFC", 4]], "the number lives in the Globals, which the firmware saves itself; only the setting word of LAST PATTERN is RAM of its own");
});

test("two hooked words call into our code, which fits its free run", () => {
  const [code, boot, select] = PATCH.changes;
  assert.equal(code.file, CODE);
  assert.ok(code.file + fromHex(code.bytes).length <= CODE_END - 4, "the last word is the setting word of LAST PATTERN");
  assert.equal(boot.file, BOOT_SITE);
  assert.equal(select.file, SELECT_SITE);
  for (const [change, at] of [[boot, 0xc002af40], [select, 0xc0079dc8]]) {
    const to = target(change, at);
    assert.ok(to >= 0xc014fe00 && to < 0xc014ff00, `${at.toString(16)} calls ${to.toString(16)}`);
  }
  assert.deepEqual(PATCH.startPhase.map(s => s.file), [BOOT_SITE, SELECT_SITE, CODE], "the first pattern and its selection run at start");
});

test("its hooks are in the register and the BLECH set carries it", () => {
  const sites = Object.values(CHAINS).flat().flatMap(stage => stage.sites);
  for (const hook of PATCH.hooks) {
    assert.ok(CHAINS[hook.chain], hook.chain);
    assert.ok(sites.includes(Number(hook.site)), hook.site);
  }
  assert.ok(SET.patches.includes("data/patches/last-pattern.json"));
});
