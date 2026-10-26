import { test } from "node:test";
import assert from "node:assert/strict";
import { crc32Combine, crc32Join } from "../src/crc-combine.mjs";
import { crc32 } from "../src/script/blob.mjs";

const bytes = n => Uint8Array.from({ length: n }, (_, i) => (i * 131 + (i >> 3)) & 255);

test("the CRC of two pieces equals the CRC of the whole, at every split", () => {
  const whole = bytes(2000);
  for (const at of [0, 1, 7, 255, 1000, 1999, 2000]) {
    assert.equal(crc32Combine(crc32(whole.subarray(0, at)), crc32(whole.subarray(at)), whole.length - at), crc32(whole), `split at ${at}`);
  }
});

test("many pieces of uneven size join to the CRC of the file, also at the sizes of a sample file", () => {
  const whole = bytes(300_000);
  const cuts = [0, 4096, 4097, 70_000, 262_144 + 4096, 299_999, 300_000];
  const pieces = cuts.slice(1).map((end, i) => ({ crc: crc32(whole.subarray(cuts[i], end)), length: end - cuts[i] }));
  assert.equal(crc32Join(pieces), crc32(whole));
});
