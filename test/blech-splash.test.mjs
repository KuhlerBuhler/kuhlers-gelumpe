import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { applyPatches, fromHex } from "../src/patch.mjs";
import { field } from "../src/map/index.mjs";
import { makeFirmware } from "./helpers.mjs";

const load = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const splashA = load("assets/blechy/splash.json");
const SPLASH = field("splash").where.offset;

test("the Blech start image patch matches its bitmap and writes only the splash field", async () => {
  const bin = new Uint8Array(readFileSync(new URL("../assets/blechy/splash.bin", import.meta.url)));
  assert.deepEqual(fromHex(splashA.changes[0].bytes), bin);
  const vsb = await makeFirmware();
  const res = await applyPatches(vsb, [splashA]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.deepEqual(res.allow, [[SPLASH, 1024]]);
  assert.deepEqual(res.bytes.subarray(SPLASH, SPLASH + 1024), bin);
});

test("the Blech start image can be applied together with the code patches", () => {
  for (const name of ["mfx-switch", "splash-editor"]) {
    const code = load(`data/patches/${name}.json`);
    const spans = code.changes.map(c => c.file === undefined ? null : [c.file, (c.bytes?.length ?? c.copy.length * 2) / 2]).filter(Boolean);
    assert.ok(spans.length > 0);
    for (const [at, n] of spans) assert.ok(at + n <= SPLASH || at >= SPLASH + 1024, `${name} 0x${at.toString(16)} overlaps the splash field`);
  }
});
