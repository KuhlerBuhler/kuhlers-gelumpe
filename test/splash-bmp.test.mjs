import { test } from "node:test";
import assert from "node:assert/strict";
import { toMono, grayOf, encodeBmp, SPLASH_W, SPLASH_H } from "../src/splash-bmp.mjs";

const N = SPLASH_W * SPLASH_H;

// What the firmware's import does with the file (tools/patch/splash_editor.py, splash_import): header checks,
// the darker palette entry is drawn, rows from the bottom when the height is positive.
function readLikeTheDevice(b) {
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength);
  assert.equal(String.fromCharCode(b[0], b[1]), "BM");
  assert.equal(v.getInt32(18, true), 128);
  assert.equal(v.getInt32(22, true), 64);
  assert.equal(v.getUint16(26, true), 1);
  assert.equal(v.getUint16(28, true), 1);
  assert.equal(v.getUint32(30, true), 0);
  const off = v.getUint32(10, true);
  const pal = 14 + v.getUint32(14, true);
  assert.ok(pal + 8 <= off && off <= 0x200);
  const bright = i => b[pal + 4 * i] + b[pal + 4 * i + 1] + b[pal + 4 * i + 2];
  const ink = bright(1) < bright(0) ? 1 : 0;
  assert.equal(b.length, off + 1024);
  const px = new Uint8Array(N);
  for (let y = 0; y < 64; y++) {
    for (let x = 0; x < 128; x++) {
      const bit = (b[off + (63 - y) * 16 + (x >> 3)] >> (7 - (x & 7))) & 1;
      px[y * 128 + x] = bit === ink ? 1 : 0;
    }
  }
  return px;
}

test("the file is what the device's import reads, pixel for pixel", () => {
  const px = Uint8Array.from({ length: N }, (_, i) => ((i % 128) + 3 * Math.floor(i / 128)) % 5 === 0 ? 1 : 0);
  assert.deepEqual(readLikeTheDevice(encodeBmp(px)), px);
});

test("dark is drawn, the threshold and invert decide", () => {
  const gray = Uint8Array.from({ length: N }, (_, i) => (i % 128 < 64 ? 20 : 230));
  const px = toMono(gray);
  assert.equal(px[0], 1);
  assert.equal(px[127], 0);
  assert.deepEqual(toMono(gray, { invert: true }), px.map(p => 1 - p));
  assert.equal(toMono(gray, { threshold: 10 })[0], 0);
});

test("dithering turns mid grey into a pattern of about half the pixels", () => {
  const drawn = toMono(new Uint8Array(N).fill(128), { dither: true }).reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(drawn - N / 2) < N * 0.05, `${drawn} of ${N}`);
  assert.equal(toMono(new Uint8Array(N).fill(128)).reduce((a, b) => a + b, 0), 0, "without dithering 128 is not below the threshold");
});

test("transparent pixels count as white", () => {
  assert.deepEqual([...grayOf(Uint8Array.of(0, 0, 0, 0, 0, 0, 0, 255))], [255, 0]);
});

test("a wrong size is refused", () => {
  assert.throws(() => encodeBmp(new Uint8Array(10)));
  assert.throws(() => toMono(new Uint8Array(10)));
});
