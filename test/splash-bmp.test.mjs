import { test } from "node:test";
import assert from "node:assert/strict";
import { toMono, grayOf, encodeBmp, decodeBmp, SPLASH_W, SPLASH_H } from "../src/splash-bmp.mjs";

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

// A marker picture: pixel 0,0 and 127,63 drawn, so a mirrored or flipped read shows.
const marker = () => { const px = new Uint8Array(N); px[0] = 1; px[N - 1] = 1; px[5 * 128 + 9] = 1; return px; };
const topDown = b => {
  const out = b.slice();
  new DataView(out.buffer).setInt32(22, -64, true);
  for (let y = 0; y < 64; y++) out.set(b.subarray(62 + (63 - y) * 16, 62 + (64 - y) * 16), 62 + y * 16);
  return out;
};

test("decodeBmp reads back what encodeBmp writes, and what the device's import reads", () => {
  const px = Uint8Array.from({ length: N }, (_, i) => ((i % 128) * 7 + Math.floor(i / 128)) % 3 === 0 ? 1 : 0);
  assert.deepEqual(decodeBmp(encodeBmp(px)), px);
  assert.deepEqual(decodeBmp(encodeBmp(marker())), readLikeTheDevice(encodeBmp(marker())));
  assert.deepEqual(decodeBmp(encodeBmp(marker())), marker(), "not mirrored, not flipped");
});

test("decodeBmp takes rows from the top with height -64, a swapped palette and trailing bytes", () => {
  assert.deepEqual(decodeBmp(topDown(encodeBmp(marker()))), marker());
  const swapped = encodeBmp(marker());
  swapped.set([0, 0, 0, 0, 0xff, 0xff, 0xff, 0], 54);
  for (let i = 62; i < swapped.length; i++) swapped[i] ^= 0xff;
  assert.deepEqual(decodeBmp(swapped), marker(), "the darker entry is drawn, whatever its index");
  const longer = new Uint8Array(1086 + 10);
  longer.set(encodeBmp(marker()));
  assert.deepEqual(decodeBmp(longer), marker());
});

test("decodeBmp refuses what SPLASH IMPORT refuses, with a reason", () => {
  const good = encodeBmp(marker());
  const bad = (edit) => { const b = good.slice(); edit(b, new DataView(b.buffer)); return decodeBmp(b); };
  assert.equal(typeof bad((b, v) => v.setUint16(28, 24, true)), "string", "24 bit");
  assert.equal(typeof bad((b, v) => v.setInt32(22, 32, true)), "string", "128 x 32");
  assert.equal(typeof bad((b, v) => v.setInt32(18, 64, true)), "string", "64 wide");
  assert.equal(typeof bad((b, v) => v.setUint32(30, 1, true)), "string", "compressed");
  assert.equal(typeof bad(b => { b[0] = 0x58; }), "string", "no BM");
  assert.equal(typeof bad(b => { b[26] = 2; }), "string", "two planes");
  assert.equal(typeof bad((b, v) => v.setUint32(10, 0x204, true)), "string", "pixels after 0x200");
  assert.equal(typeof bad((b, v) => v.setUint32(10, 50, true)), "string", "pixels inside the header");
  assert.equal(typeof bad((b, v) => v.setUint32(14, 60, true)), "string", "palette runs into the pixels");
  assert.equal(typeof decodeBmp(good.subarray(0, 1085)), "string", "cut short");
  assert.equal(typeof decodeBmp(good.subarray(0, 40)), "string", "shorter than the header");
  assert.equal(typeof decodeBmp(undefined), "string");
});
