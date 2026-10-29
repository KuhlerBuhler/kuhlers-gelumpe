import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { CHAINS } from "../data/hooks.mjs";

// Stereo on one pad (docs/messungen/2026-10-29-stereo-ein-pad.md): a stereo sample never pairs its part with the next one.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const PATCH = read("data/patches/stereo-pad.json");
const SET = read("data/patches/blech.json");
const CODE = 0x150000;               // file offset of 0xC014FF00, behind the last-pattern code
const CODE_END = 0x1500fc;           // 0xC014FFFC, the setting word
const SITES = [[0x7df08, 0xe], [0x414ec, 0xe], [0x99f2c, 0x0]];   // 0xC007DE08, 0xC00413EC, 0xC0099E2C and the condition of their call

test("the stereo-pad patch has the v1 format, copies nothing of the firmware and declares its start-phase code", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.id, "stereo-pad");
  assert.deepEqual(PATCH.builds, ["hacktribe", "stock"]);
  for (const change of PATCH.changes) assert.equal(change.copy, undefined);
  assert.deepEqual(PATCH.startPhase.map(s => s.file), [0x7df08, CODE]);
  assert.deepEqual(PATCH.ram.map(r => [r.at, r.length]), [["0xC014FFFC", 4]]);
});

test("three instructions call into our code, which ends where the run of free bytes ends", () => {
  const [code, ...calls] = PATCH.changes;
  assert.equal(code.file, CODE);
  assert.ok(code.file + fromHex(code.bytes).length <= CODE_END);
  assert.deepEqual(calls.map(c => c.file), SITES.map(([file]) => file));
  for (const [i, call] of calls.entries()) {
    const word = Buffer.from(fromHex(call.bytes)).readUInt32LE(0);
    assert.equal(word >>> 28, SITES[i][1]);
    assert.equal((word >>> 24) & 0xf, 0xb);
    const site = 0xc0000000 + call.file - 0x100;
    const to = site + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    assert.ok(to >= 0xc014ff00 && to < 0xc014fffc, `${site.toString(16)} calls ${to.toString(16)}`);
  }
});

test("its hooks are in the register and the BLECH set carries it", () => {
  const sites = Object.values(CHAINS).flat().flatMap(stage => stage.sites);
  for (const hook of PATCH.hooks) assert.ok(CHAINS[hook.chain] && sites.includes(Number(hook.site)), hook.site);
  assert.ok(SET.patches.includes("data/patches/stereo-pad.json"));
});
