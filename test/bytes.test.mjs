import { test } from "node:test";
import assert from "node:assert/strict";
import { syxEnc, syxDec, u32le, readU32le, readName } from "../src/bytes.mjs";

test("packing survives every length up to three blocks", () => {
  for (let n = 0; n <= 24; n++) {
    const input = Array.from({ length: n }, (_, i) => (i * 37 + 3) & 0xff);
    assert.deepEqual(syxDec(syxEnc(input)).slice(0, n), input, `length ${n}`);
  }
});

test("high bits land in the leading byte, least significant first", () => {
  assert.deepEqual(syxEnc([0x80, 0x01]), [0b01, 0x00, 0x01]);
  assert.deepEqual(syxEnc([0x01, 0x80]), [0b10, 0x01, 0x00]);
});

test("a length with a remainder of six keeps its last block", () => {
  // The reference encoder drops it. 524 is such a length, and 524 is the
  // size of an effect record.
  for (const n of [6, 13, 20, 524]) {
    const input = Array.from({ length: n }, (_, i) => i & 0xff);
    assert.equal(syxDec(syxEnc(input)).length >= n, true, `length ${n} came back short`);
    assert.deepEqual(syxDec(syxEnc(input)).slice(0, n), input);
  }
});

test("little endian words", () => {
  assert.deepEqual(u32le(0xc00b4f30), [0x30, 0x4f, 0x0b, 0xc0]);
  assert.equal(readU32le(u32le(0xc00b4f30)), 0xc00b4f30);
});

test("names stop at the first NUL", () => {
  assert.equal(readName(Uint8Array.from([0x41, 0x42, 0x00, 0x43])), "AB");
});

test("a full pattern packs in well under a second", () => {
  // Patterns are 16 KB and flash reads are larger, so the packing has to
  // stay linear.
  const input = Uint8Array.from({ length: 0x4000 * 8 }, (_, i) => (i * 31) & 0xff);
  const t = performance.now();
  const back = syxDec(syxEnc(input));
  const ms = performance.now() - t;
  assert.deepEqual(back.slice(0, input.length), Array.from(input));
  assert.ok(ms < 500, `128 KB took ${ms.toFixed(0)} ms`);
});
