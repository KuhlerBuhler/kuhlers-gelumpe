import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { converter } from "../src/map/convert.mjs";
import pattern from "../data/map/pattern.mjs";

// BEAT 8 (docs/messungen/2026-10-29-beat-achtel.md): a fifth entry in the divider table, the menu to 4, the export lengths.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const RED = read("data/patches/beat-eighth.json");
const BLUE = read("data/patches/beat-eighth-synth.json");
const file = addr => addr - 0xc0000000 + 0x100;
const DATA = file(0xc014fc00);
const VERSION = file(0xc014fcf0);       // the version text of blech-version starts here

for (const [name, patch, builds] of [["red", RED, ["hacktribe", "stock"]], ["blue", BLUE, ["synth"]]]) {
  test(`the ${name} patch is data and instruction words only, with no hook, no start phase and no RAM`, () => {
    assert.equal(patch.format, PATCH_FORMAT);
    assert.equal(patch.id, "beat-eighth");
    assert.deepEqual(patch.builds, builds);
    assert.equal(patch.hooks, undefined);
    assert.equal(patch.startPhase, undefined);
    assert.deepEqual(patch.ram, []);
  });

  test(`the ${name} patch writes 12 behind the divider table and keeps its own data in front of the version text`, () => {
    const divider = name === "red" ? file(0xc00e2de0) : file(0xc00c95b8);
    const entry = patch.changes.find(c => c.file === divider);
    assert.equal(entry?.bytes, "0c");
    for (const c of patch.changes.filter(c => c.file >= DATA && c.file < VERSION)) {
      const length = c.copy ? c.copy.length : fromHex(c.bytes).length;
      assert.ok(c.file + length <= DATA + 0x10, `0x${c.file.toString(16)}`);
    }
    const text = patch.changes.find(c => c.file === DATA);
    assert.equal(Buffer.from(fromHex(text.bytes)).toString("latin1"), "\\\\8\0");
    assert.deepEqual(patch.changes.filter(c => c.copy).map(c => [c.file - DATA, c.over[0].bytes]), [[4, "02"], [8, "10"]]);
  });
}

test("both BLECH sets carry the patch", () => {
  assert.ok(read("data/patches/blech.json").patches.includes("data/patches/beat-eighth.json"));
  assert.ok(read("data/patches/blech-synth.json").patches.includes("data/patches/beat-eighth-synth.json"));
});

test("the app takes BEAT 4 and calls it 8tel", () => {
  const beat = pattern.fields.find(f => f.id === "pattern.beat");
  assert.deepEqual(beat.range, [0, 4]);
  assert.equal(converter("beat").format(4), "8tel");
  assert.equal(converter("beat").format(0), "16tel");
});
