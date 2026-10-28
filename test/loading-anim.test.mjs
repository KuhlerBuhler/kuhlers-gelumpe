import { test } from "node:test";
import assert from "node:assert/strict";
import {
  encodeAnimation, decodeAnimation, validateAnimation, thinAnimation, costPerFrame, pixelsToFrame, frameToPixels,
  progressIndex, MAX_BYTES, FRAME_BYTES,
} from "../src/loading-anim.mjs";

// A block 16 columns wide and all 8 pages high, at a place that never overlaps the one before.
function sprite(k) {
  const f = new Uint8Array(FRAME_BYTES);
  const x0 = (k * 24) % 112;
  for (let p = 0; p < 8; p++) f.fill(0x5a + k, p * 128 + x0, p * 128 + x0 + 16);
  return f;
}

function spinner(j) {
  const f = new Uint8Array(FRAME_BYTES);
  f[7 * 128 + 120 + j] = 0xff;
  f[7 * 128 + 100] = j;
  return f;
}

test("every progress and loop picture comes back as it went in", () => {
  const frames = { progress: Array.from({ length: 12 }, (_, k) => sprite(k)), loop: [0, 1, 2, 3].map(spinner) };
  const { bytes, size } = encodeAnimation(frames);
  assert.equal(size, bytes.length);
  assert.equal(validateAnimation(bytes), null);
  const back = decodeAnimation(bytes);
  assert.equal(back.progress.length, 12);
  assert.equal(back.loop.length, 4);
  frames.progress.forEach((f, k) => assert.deepEqual(back.progress[k], f, `progress ${k}`));
  frames.loop.forEach((f, j) => assert.deepEqual(back.loop[j], f, `loop ${j}`));
});

test("a single picture without loop is header plus 1024 bytes", () => {
  const { bytes } = encodeAnimation({ progress: [sprite(0)] });
  assert.equal(bytes.length, 16 + FRAME_BYTES);
  assert.deepEqual(decodeAnimation(bytes), { progress: [sprite(0)], loop: [], loopFrom: 0 });
});

test("runs are split at 64 bytes and bridge a single unchanged byte", () => {
  const a = new Uint8Array(FRAME_BYTES), b = new Uint8Array(FRAME_BYTES);
  b.fill(1, 0, 100);
  b[101] = 1;
  b[200] = 1;                                     // two equal bytes before it: a new run
  const { bytes } = encodeAnimation({ progress: [a, b] });
  // runs: 0..63, 64..101 (bridging 100), 200
  assert.equal(bytes.length, 16 + FRAME_BYTES + 2 + 2 + (2 + 64) + (2 + 38) + (2 + 1));
  assert.deepEqual(decodeAnimation(bytes).progress[1], b);
});

test("every picture inverted goes over the limit and is rejected", () => {
  const black = new Uint8Array(FRAME_BYTES), white = new Uint8Array(FRAME_BYTES).fill(0xff);
  const { bytes, size } = encodeAnimation({ progress: Array.from({ length: 20 }, (_, k) => (k % 2 ? white : black)) });
  assert.ok(size > MAX_BYTES, `${size}`);
  assert.match(validateAnimation(bytes), /more than 16384/);
  assert.throws(() => decodeAnimation(bytes), /more than 16384/);
});

test("exactly MAX_BYTES is accepted", () => {
  const progress = Array.from({ length: 80 }, (_, k) => sprite(k));
  while (encodeAnimation({ progress }).size > MAX_BYTES - 600) progress.pop();
  // A last picture changing one stretch of `len` bytes adds 2 (table) + 2 (count) + its runs.
  let hit = null;
  for (let len = 1; len <= 1024 && !hit; len++) {
    const last = progress.at(-1).slice();
    for (let i = 0; i < len; i++) last[i] ^= 0xff;
    const out = encodeAnimation({ progress: [...progress, last] });
    if (out.size === MAX_BYTES) hit = out;
  }
  assert.ok(hit, "no length hits the limit exactly");
  assert.equal(validateAnimation(hit.bytes), null);
  assert.equal(decodeAnimation(hit.bytes).progress.length, progress.length + 1);
});

function good() {
  return encodeAnimation({ progress: [sprite(0), sprite(1), sprite(2)], loop: [spinner(0)] }).bytes;
}

test("bad magic and version are rejected", () => {
  const b = good();
  b[0] = 0x58;
  assert.equal(validateAnimation(b), "wrong magic");
  const c = good();
  c[4] = 2;
  assert.equal(validateAnimation(c), "version 2");
});

test("a run that writes at offset 1024 or beyond is rejected", () => {
  const b = good();
  const v = new DataView(b.buffer);
  const list = v.getUint16(v.getUint16(10, true), true);
  v.setUint16(list + 2, 1020 | (7 << 10), true);       // 8 bytes from 1020: the last one at 1027
  assert.match(validateAnimation(b), /past byte 1023/);
});

test("a truncated list is rejected", () => {
  const b = good();
  const cut = b.slice(0, b.length - 3);
  new DataView(cut.buffer).setUint32(12, cut.length, true);
  assert.match(validateAnimation(cut), /outside the file/);
  assert.equal(validateAnimation(b.slice(0, b.length - 3)), "the file is shorter than its size");
  const v = new DataView(b.buffer);
  v.setUint16(v.getUint16(10, true), b.length - 1, true);   // a list starting on the last byte
  assert.match(validateAnimation(b), /outside the file/);
});

test("a list table past the end is rejected", () => {
  const b = good();
  new DataView(b.buffer).setUint16(8, 5000, true);
  assert.equal(validateAnimation(b), "list table outside the file");
});

test("thinning keeps every second progress picture and the last, and roughly halves the size", () => {
  const progress = Array.from({ length: 41 }, (_, k) => sprite(k));
  const thin = thinAnimation({ progress, loop: [spinner(1)] });
  assert.equal(thin.progress.length, 21);
  assert.equal(thin.progress.at(-1), progress.at(-1));
  assert.equal(thin.loop.length, 1);
  const before = encodeAnimation({ progress }).size, after = encodeAnimation(thinAnimation({ progress })).size;
  const ratio = after / before;
  assert.ok(ratio > 0.45 && ratio < 0.65, `${before} -> ${after}`);
});

test("cost per picture adds up to the file size", () => {
  const frames = { progress: [sprite(0), sprite(1), sprite(1)], loop: [spinner(2)] };
  const cost = costPerFrame(frames);
  assert.deepEqual(cost.map(c => `${c.kind}${c.index}`), ["progress0", "progress1", "progress2", "loop0"]);
  assert.equal(cost[2].bytes, 4);                   // no change: table entry and an empty count
  assert.equal(16 + cost.reduce((s, c) => s + c.bytes, 0), encodeAnimation(frames).size);
});

test("pixels to a picture: bit 0 on top, lit where nothing is drawn", () => {
  const px = new Uint8Array(128 * 64);
  px[0] = 1;                                         // x 0, y 0 drawn
  px[9 * 128 + 3] = 1;                               // x 3, y 9 drawn
  const f = pixelsToFrame(px);
  assert.equal(f[0], 0xfe);
  assert.equal(f[128 + 3], 0xfd);
  assert.equal(f[5], 0xff);
  assert.deepEqual(frameToPixels(f), px);
});

test("the encoder refuses pictures of the wrong size", () => {
  assert.throws(() => encodeAnimation({ progress: [new Uint8Array(10)] }), /1024 bytes/);
  assert.throws(() => encodeAnimation({ progress: [] }), /at least one/);
});

test("the picture for a progress in permille, the last one only when done", () => {
  assert.equal(progressIndex(101, 0), 0);
  assert.equal(progressIndex(101, 999), 99);
  assert.equal(progressIndex(101, 1000), 100);
  assert.equal(progressIndex(12, 500), 5);
  assert.equal(progressIndex(1, 700), 0);
});

test("loop from a percent: byte 5, the loop lists taken against the picture of that percent", () => {
  const progress = Array.from({ length: 11 }, (_, k) => sprite(k));
  const loop = [0, 1, 2].map(j => { const f = progress[5].slice(); f[1000 + j] = 0xee; return f; });
  const { bytes } = encodeAnimation({ progress, loop, loopFrom: 50 });
  assert.equal(bytes[5], 50);
  assert.equal(validateAnimation(bytes), null);
  const back = decodeAnimation(bytes);
  assert.equal(back.loopFrom, 50);
  loop.forEach((f, j) => assert.deepEqual(back.loop[j], f, `loop ${j}`));
  // each loop list is the few bytes that differ from picture 5, not the whole way from picture 0
  assert.ok(bytes.length < encodeAnimation({ progress, loop }).size);
  assert.equal(decodeAnimation(good()).loopFrom, 0);
});

test("loop from above 100 percent is refused and rejected", () => {
  assert.throws(() => encodeAnimation({ progress: [sprite(0)], loopFrom: 101 }), /0 to 100/);
  const b = good();
  b[5] = 101;
  assert.equal(validateAnimation(b), "loop from 101 percent");
});
