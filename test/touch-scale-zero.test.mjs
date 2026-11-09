import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { converter } from "../src/map/convert.mjs";
import global from "../data/map/global.mjs";

// TOUCH SCALE RANGE 0 (docs/messungen/2026-10-30-touch-scale-null.md): the page's clamp takes 0, the X mapping plays the key note.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const RED = read("data/patches/touch-scale-zero.json");
const BLUE = read("data/patches/touch-scale-zero-synth.json");
const file = addr => addr - 0xc0000000 + 0x100;
const words = hex => {
  const bytes = fromHex(hex);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
  return Array.from({ length: bytes.length / 4 }, (_, i) => view.getUint32(4 * i, true));
};

const MAPPING = [0xe5947014, 0xe1d433b0, 0xe0170790, 0xe20050ff, 0xe2877001, 0xe20770ff, 0xe0070793, 0xe1a073a7, 0x01a07005, 0xe1a01005, 0xe1a00007];

for (const [name, patch, builds, clamp, mapping] of [
  ["red", RED, ["hacktribe", "stock"], 0xc007a940, 0xc0060654],
  ["blue", BLUE, ["synth"], 0xc006d2c4, 0xc005710c],
]) {
  test(`the ${name} patch is two instruction runs, with no hook, no start phase and no RAM`, () => {
    assert.equal(patch.format, PATCH_FORMAT);
    assert.equal(patch.id, "touch-scale-zero");
    assert.deepEqual(patch.builds, builds);
    assert.equal(patch.hooks, undefined);
    assert.equal(patch.startPhase, undefined);
    assert.deepEqual(patch.ram, []);
    assert.equal(patch.changes.length, 2);
  });

  test(`the ${name} patch lets the page go to 0 and sets the step to a full octave for range 0`, () => {
    const menu = patch.changes.find(c => c.file === file(clamp));
    assert.deepEqual(words(menu.bytes), [0xd3a01000], "movle r1, #0");
    const map = patch.changes.find(c => c.file === file(mapping));
    assert.deepEqual(words(map.bytes), MAPPING);
  });
}

test("the new mapping gives Korg's step for ranges 1 to 4 and a full octave for 0", () => {
  // The firmware: slots = (steps * range + 1) & 0xff, step = ((x * slots) << 9) >>> 16. The patch: >>> 7, and steps for range 0.
  for (let steps = 1; steps <= 16; steps++) {
    for (let range = 0; range <= 255; range++) {
      for (let x = 0; x <= 127; x++) {
        const slots = (steps * range + 1) & 0xff;
        const korg = ((x * slots) << 9) >>> 16;
        const ours = (steps * range) === 0 ? steps : (x * slots) >>> 7;
        if (range === 0) assert.equal(ours, steps);
        else assert.equal(ours, korg, `steps ${steps}, range ${range}, x ${x}`);
      }
    }
  }
});

test("both BLECH sets carry the patch", () => {
  assert.ok(read("data/patches/blech.json").patches.includes("data/patches/touch-scale-zero.json"));
  assert.ok(read("data/patches/blech-synth.json").patches.includes("data/patches/touch-scale-zero-synth.json"));
});

test("the app takes range 0", () => {
  const field = global.fields.find(f => f.id === "global.touchScaleRange");
  assert.deepEqual(field.range, [0, 4]);
  assert.equal(field.evidence, "measure:2026-10-30/touch-scale-null");
  assert.equal(converter("octaves").format(1), "1 Oktave");
  assert.equal(converter("octaves").format(4), "4 Oktaven");
  assert.match(converter("octaves").format(0), /^0 /);
});
