import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { CHAINS } from "../data/hooks.mjs";

// Set Init Pattern (docs/messungen/2026-10-28-init-pattern.md): INITIALIZE PATTERN copies the pattern Global byte 247 names.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const PATCH = read("data/patches/init-pattern.json");
const SET = read("data/patches/blech.json");
const CODE = 0x14fe00;               // file offset of 0xC014FD00
const CODE_END = 0x14ff00;           // 0xC014FE00, where the last-pattern code starts
const INIT_CALL = 0x36b34;           // 0xC0036A34, the call of the init function in INITIALIZE PATTERN

test("the init-pattern patch has the v1 format, copies nothing of the firmware and runs nothing at start", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.id, "init-pattern");
  assert.deepEqual(PATCH.builds, ["hacktribe", "stock"]);
  for (const change of PATCH.changes) assert.equal(change.copy, undefined);
  assert.equal(PATCH.startPhase, undefined, "the start's own fills of invalid patterns keep the firmware's call");
  assert.deepEqual(PATCH.ram, []);
});

test("one hooked call goes into our code, which ends before the last-pattern code", () => {
  const [code, hook] = PATCH.changes;
  assert.equal(code.file, CODE);
  assert.ok(code.file + fromHex(code.bytes).length <= CODE_END);
  assert.equal(hook.file, INIT_CALL);
  const word = Buffer.from(fromHex(hook.bytes)).readUInt32LE(0);
  assert.equal(word >>> 24, 0xeb);
  assert.equal(0xc0036a34 + 8 + (((word & 0xffffff) << 8) >> 8) * 4, 0xc014fd00);
});

test("its hook is in the register and the BLECH set carries it", () => {
  const sites = Object.values(CHAINS).flat().flatMap(stage => stage.sites);
  for (const hook of PATCH.hooks) assert.ok(CHAINS[hook.chain] && sites.includes(Number(hook.site)), hook.site);
  assert.ok(SET.patches.includes("data/patches/init-pattern.json"));
});
