import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PATCH_FORMAT } from "../src/patch.mjs";
import { checkHooks } from "../src/hooks.mjs";

// Idle insert effect (docs/messungen/2026-10-18-ifx-ruht.md).
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/ifx-idle.json");
const SET = read("../data/patches/blech.json").patches.map(p => read(`../${p}`)).filter(p => !(p.builds.length === 1 && p.builds[0] === "stock"));
const LITERAL = 0x89e90;            // file offset of 0xC0089D90, where the LED manager's timer takes its tick from

test("the idle insert effect has the v1 format, replaces only the timer literal besides its code, and declares its RAM", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "ifx-idle");
  assert.deepEqual(PATCH.builds, ["hacktribe", "stock"]);
  assert.equal(PATCH.changes.length, 2);
  const literal = PATCH.changes.find(c => c.file === LITERAL);
  assert.ok(literal, "the timer literal is one of the changes");
  const target = Buffer.from(literal.bytes, "hex").readUInt32LE(0);
  assert.ok(target >= 0xc018c000 && target < 0xc018c800, "the literal points into the patch's code");
  assert.deepEqual(PATCH.ram.map(r => [r.at, r.length]), [["0xC018CF00", 0x40]]);
});

test("the idle insert effect is out of the BLECH set for now (it sets Punch and never resets it), and fits back in without a hook conflict", () => {
  assert.ok(!SET.some(p => p.id === "ifx-idle"));
  assert.ok(!read("../data/patches/blech-synth.json").patches.some(p => p.includes("ifx-idle")), "the blue set leaves it out too");
  const result = checkHooks([...SET, PATCH]);
  assert.equal(result.ok, true, result.reasons.join(" "));
});
