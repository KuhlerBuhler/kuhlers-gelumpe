import { test } from "node:test";
import assert from "node:assert/strict";
import { bunzip2 } from "../src/bzip2.mjs";
import { expected, fixture, sha } from "./fixtures/bsdiff/data.mjs";

// The streams are written by Python's bz2 from made-up data (test/fixtures/bsdiff/make.py).
for (const [name, want] of Object.entries(expected.bzip2)) {
  test(`bzip2: ${name} decodes to what bz2 compressed`, () => {
    const out = bunzip2(fixture(`./bzip2/${name}.bz2`));
    assert.equal(out.length, want.length);
    assert.equal(sha(out), want.sha256);
  });
}

test("bzip2: a stream that is not bzip2 is refused", () => {
  assert.throws(() => bunzip2(new Uint8Array([0x50, 0x4b, 3, 4, 0, 0])), /header/);
  assert.throws(() => bunzip2(new Uint8Array(0)), /header/);
});

test("bzip2: a cut-off stream is refused", () => {
  const stream = fixture("./bzip2/runs.bz2");
  for (const cut of [5, 20, stream.length - 3]) assert.throws(() => bunzip2(stream.subarray(0, cut)), /bzip2/, `cut at ${cut}`);
});

test("bzip2: a flipped bit anywhere in the data is caught, by the format or by a checksum", () => {
  const stream = fixture("./bzip2/runs.bz2");
  let caught = 0;
  for (let at = 4; at < stream.length; at += 7) {
    const bad = stream.slice();
    bad[at] ^= 0x10;
    try { bunzip2(bad); } catch { caught++; }
  }
  assert.equal(caught, Math.ceil((stream.length - 4) / 7), "every damaged copy was refused");
});

test("bzip2: the output size is bounded", () => {
  assert.throws(() => bunzip2(fixture("./bzip2/zeros-2mib.bz2"), { maxSize: 1000 }), /larger than allowed/);
});
