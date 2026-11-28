import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PATCH_FORMAT, fromHex } from "../src/patch.mjs";

// Keys close the value window (docs/hintergrund/display.md): the window's key handler closes on a press
// and posts the same press again; the filter keys keep the window.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const RED = read("data/patches/value-popup.json");
const BLUE = read("data/patches/value-popup-synth.json");
const file = addr => addr - 0xc0000000 + 0x100;
const words = hex => {
  const bytes = fromHex(hex);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
  return Array.from({ length: bytes.length / 4 }, (_, i) => view.getUint32(4 * i, true));
};
const branch = (at, w) => (at + 8 + (((w & 0xffffff) << 8) >> 6)) >>> 0;

const FILTERS = [0x12, 0x14, 0x16];
const CLOSE = 12, FORWARD = 17;

/** Runs the handler's head (words 0 to 11) for a key and a press (1) or release (0): "close", "forward" or "keep". */
function head(code, key, down) {
  const r = Array(16).fill(0);
  r[1] = key;
  r[2] = down;
  let n = false, z = false, c = false, v = false;
  const pass = cond => [z, !z, c, !c, n, !n, v, !v, c && !z, !c || z, n === v, n !== v, !z && n === v, z || n !== v, true][cond];
  for (let pc = 0, steps = 0; steps < 32; steps++) {
    if (pc === CLOSE) return "close";
    if (pc === FORWARD) return "forward";
    const w = code[pc];
    if (!pass(w >>> 28)) { pc++; continue; }
    if ((w & 0x0e000000) === 0x0a000000) { pc += (((w & 0xffffff) << 8) >> 8) + 2; continue; }
    if ((w & 0x0fff0000) === 0x08bd0000) { assert.ok(w & 0x8000, "a pop in the head returns"); return "keep"; }
    if ((w & 0x0fff0000) === 0x092d0000) { pc++; continue; }
    const op = (w >>> 21) & 15, rn = (w >>> 16) & 15, rd = (w >>> 12) & 15;
    assert.ok(w & 0x02000000 ? (w & 0xf00) === 0 : (w & 0xff0) === 0, `word ${pc}: an immediate or a plain register`);
    const b = w & 0x02000000 ? w & 0xff : r[w & 15];
    const a = r[rn];
    const res = { 2: (a - b) >>> 0, 8: (a & b) >>> 0, 9: (a ^ b) >>> 0, 10: (a - b) >>> 0, 13: b }[op];
    assert.ok(res !== undefined, `word ${pc}: opcode ${op}`);
    if (w & 0x00100000 || op === 8 || op === 9 || op === 10) {
      n = res >>> 31 === 1;
      z = res === 0;
      if (op === 10 || op === 2) { c = a >= b; v = (((a ^ b) & (a ^ res)) >>> 31) === 1; }
    }
    if (op !== 8 && op !== 9 && op !== 10) r[rd] = res;
    pc++;
  }
  throw new Error("the head does not end");
}

for (const [name, patch, builds, dial, places, exits, callbacks] of [
  ["red", RED, ["hacktribe", "stock"], [0xc006eb90, 39, 0xc0083e30, 0xc0087d5c], [[0xc006543c, 0xc0083e30, 0xc00839f0, 0xc0082788, 0xc069124c], [0xc0065498, 0xc0083e30, 0xc00839f0, 0xc0082788, 0xc069124c]],
    [[0xc0065434, 0xc006543c], [0xc0065438, 0xc0065498]], [0xc00653b8, 0xc00653cc]],
  ["blue", BLUE, ["synth"], [0xc0062030, 38, 0xc0074404, 0xc0077e50], [[0xc005b8b4, 0xc0074404, 0xc0073fec, 0xc0073010, 0xc056b52c]], [[0xc005b8b0, 0xc005b8b4]], [0xc005b870]],
]) {
  test(`the ${name} patch rewrites each key handler of the value window in place, with no hook, no start phase and no RAM`, () => {
    assert.equal(patch.format, PATCH_FORMAT);
    assert.equal(patch.id, "value-popup");
    assert.deepEqual(patch.builds, builds);
    assert.equal(patch.hooks, undefined);
    assert.equal(patch.startPhase, undefined);
    assert.deepEqual(patch.ram, []);
    assert.deepEqual(patch.changes.map(c => c.file), [...places, ...exits, dial, ...callbacks.map(at => [at])].map(([at]) => file(at)).sort((a, b) => a - b));
  });

  for (const [at, keys] of exits) {
    test(`the ${name} EXIT method of the value window at ${at.toString(16)} goes to the window's key handler`, () => {
      const code = words(patch.changes.find(c => c.file === file(at)).bytes);
      assert.equal(code.length, 1);
      assert.equal(code[0] >>> 24, 0xea, "b");
      assert.equal(branch(at, code[0]), keys);
    });
  }

  for (const at of callbacks) {
    test(`the ${name} callback of the value window at ${at.toString(16)} closes the window with Korg's close, as its EXIT method did`, () => {
      const code = words(patch.changes.find(c => c.file === file(at)).bytes);
      assert.equal(code.length, 1);
      assert.equal(code[0] >>> 24, 0xea, "b");
      assert.equal(branch(at, code[0]), dial[2]);
    });
  }

  test(`the ${name} encoder handler: the main dial closes a value window with Korg's close and goes to the screen`, () => {
    const [at, length, close, after] = dial;
    const code = words(patch.changes.find(c => c.file === file(at)).bytes);
    assert.equal(code.length, length, "same length as Korg's handler");
    assert.deepEqual(code.slice(0, 5), [0xe3510000, 0xe92d4038, 0xe5d03019, 0xe1a04000, 0xe1a05002], "Korg's entry");
    const placed = code.map((w, i) => [w, at + 4 * i]);
    const calls = placed.filter(([w]) => ((w >>> 24) & 15) === 0xb);
    assert.equal(calls.length, 1, "one call: the close");
    assert.equal(branch(calls[0][1], calls[0][0]), close);
    assert.ok(placed.some(([w, a]) => w >>> 24 === 0xea && branch(a, w) === after), "the screen's dial ends in Korg's tail");
    assert.ok(code.includes(0xe59cf01c), "the other encoders: ldr pc, [ip, #0x1c] to the window or the screen");
  });

  for (const [at, close, post, filter, object] of places) {
    test(`the ${name} handler at ${at.toString(16)} keeps Korg's close, post, filter call and its object`, () => {
      const code = words(patch.changes.find(c => c.file === file(at)).bytes);
      assert.equal(code.length, 23);
      assert.equal(code[0], 0xe92d4070, "push {r4, r5, r6, lr}");
      assert.equal(branch(at + 4 * CLOSE, code[CLOSE]), close);
      assert.equal(code[CLOSE] >>> 24, 0xeb, "bl");
      assert.deepEqual(code.slice(13, 16), [0xe1a00004, 0xe1a01005, 0xe8bd4070], "mov r0, r4; mov r1, r5; pop {r4, r5, r6, lr}");
      assert.equal(branch(at + 64, code[16]), post);
      assert.deepEqual(code.slice(17, 21), [0xe59f300c, 0xe1a01000, 0xe5930000, 0xe8bd4070]);
      assert.equal(branch(at + 84, code[21]), filter);
      assert.equal(code[22], object);
    });

    test(`the ${name} handler at ${at.toString(16)}: every key closes the window and is posted again, the filter keys keep it`, () => {
      const code = words(patch.changes.find(c => c.file === file(at)).bytes);
      for (let key = 0; key < 0x24; key++) {
        for (const down of [1, 0]) {
          const want = FILTERS.includes(key) ? (down ? "keep" : "forward") : "close";
          assert.equal(head(code, key, down), want, `key ${key.toString(16)}, ${down ? "press" : "release"}`);
        }
      }
    });
  }
}

test("both BLECH sets carry the patch", () => {
  assert.ok(read("data/patches/blech.json").patches.includes("data/patches/value-popup.json"));
  assert.ok(read("data/patches/blech-synth.json").patches.includes("data/patches/value-popup-synth.json"));
});
