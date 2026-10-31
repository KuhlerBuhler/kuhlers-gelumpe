import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { decodeGif } from "../src/gif.mjs";

// LZW as GIF writes it, for fixtures built here. Images stay small, so the table never fills.
function lzw(indices, minSize) {
  const clear = 1 << minSize, out = [];
  let size = minSize + 1, next = clear + 2, acc = 0, bits = 0;
  const put = code => {
    acc |= code << bits; bits += size;
    while (bits >= 8) { out.push(acc & 0xff); acc >>>= 8; bits -= 8; }
  };
  const dict = new Map();
  put(clear);
  let w = indices[0];
  for (const k of indices.slice(1)) {
    const key = w * 256 + k;
    if (dict.has(key)) { w = dict.get(key); continue; }
    put(w);
    dict.set(key, next++);
    if (next - 1 === 1 << size && size < 12) size++;
    w = k;
  }
  put(w);
  put(clear + 1);
  if (bits) out.push(acc & 0xff);
  const blocks = [];
  for (let i = 0; i < out.length; i += 255) blocks.push(Math.min(255, out.length - i), ...out.slice(i, i + 255));
  return [minSize, ...blocks, 0];
}

const u16 = n => [n & 0xff, n >> 8];

/** frames: { x, y, w, h, idx, disposal, transparent, delay, interlace, colors } */
function gif({ width, height, colors, frames, version = "89a" }) {
  const bytes = [..."GIF" + version].map(c => c.charCodeAt(0));
  const depth = Math.log2(colors.length / 3) - 1;
  bytes.push(...u16(width), ...u16(height), 0x80 | depth, 0, 0, ...colors);
  for (const f of frames) {
    if (f.disposal !== undefined || f.transparent !== undefined || f.delay) {
      const t = f.transparent ?? -1;
      bytes.push(0x21, 0xf9, 4, (f.disposal ?? 0) << 2 | (t >= 0 ? 1 : 0), ...u16((f.delay ?? 0) / 10), Math.max(t, 0), 0);
    }
    let idx = f.idx;
    if (f.interlace) {
      idx = [];
      for (const [start, step] of [[0, 8], [4, 8], [2, 4], [1, 2]]) {
        for (let y = start; y < f.h; y += step) idx.push(...f.idx.slice(y * f.w, (y + 1) * f.w));
      }
    }
    const local = f.colors ? 0x80 | (Math.log2(f.colors.length / 3) - 1) : 0;
    bytes.push(0x2c, ...u16(f.x), ...u16(f.y), ...u16(f.w), ...u16(f.h), local | (f.interlace ? 0x40 : 0), ...(f.colors ?? []));
    bytes.push(...lzw(idx, Math.max(2, depth + 1)));
  }
  bytes.push(0x3b);
  return Uint8Array.from(bytes);
}

const WHITE = [255, 255, 255], RED = [255, 0, 0], BLUE = [0, 0, 255], BLACK = [0, 0, 0];
const PALETTE = [...WHITE, ...RED, ...BLUE, ...BLACK];
const NONE = [0, 0, 0, 0];

/** Pixel for pixel against a picture written as one letter per pixel: W R B K, . for transparent. */
function same(rgba, width, rows, what) {
  const color = { W: [...WHITE, 255], R: [...RED, 255], B: [...BLUE, 255], K: [...BLACK, 255], ".": NONE };
  assert.equal(rows.length * width * 4, rgba.length, what);
  rows.forEach((row, y) => [...row].forEach((ch, x) => {
    assert.deepEqual([...rgba.subarray(4 * (y * width + x), 4 * (y * width + x) + 4)], color[ch], `${what} at ${x},${y}`);
  }));
}

test("the classic 10 x 10 sample decodes to its known picture", () => {
  // The sample image of "What's in a GIF" (Matthew Flickinger), encoded by another tool.
  const hex = "4749463839610a000a00910000ffffffff00000000ff00000021f90400000000002c000000000a000a000002168c2d99872a1cdc33a00275ec95faa8de608c04914c01003b";
  const g = decodeGif(Uint8Array.from(Buffer.from(hex, "hex")));
  assert.equal(g.frames.length, 1);
  same(g.frames[0].rgba, 10, [
    "RRRRRBBBBB", "RRRRRBBBBB", "RRRRRBBBBB", "RRRWWWWBBB", "RRRWWWWBBB",
    "BBBWWWWRRR", "BBBWWWWRRR", "BBBBBRRRRR", "BBBBBRRRRR", "BBBBBRRRRR",
  ], "sample");
});

test("several frames from ffmpeg: sub-rectangles over the frame before", () => {
  const g = decodeGif(readFileSync(new URL("fixtures/gif/ffmpeg-moving.gif", import.meta.url)));
  assert.equal(g.width, 12);
  assert.equal(g.height, 8);
  assert.equal(g.frames.length, 3);
  assert.deepEqual(g.frames.map(f => f.delay), [100, 100, 100]);
  // ffmpeg's rgb8 palette: white is 252 252 255, red 252 0 0.
  const W = [252, 252, 255, 255], R = [252, 0, 0, 255], B = [0, 0, 255, 255];
  [1, 5, 8].forEach((bx, k) => {
    for (let y = 0; y < 8; y++) {
      for (let x = 0; x < 12; x++) {
        const want = bx <= x && x < bx + 3 && y >= 2 && y < 5 ? R : x === 10 ? B : W;
        assert.deepEqual([...g.frames[k].rgba.subarray(4 * (y * 12 + x), 4 * (y * 12 + x) + 4)], want, `frame ${k} at ${x},${y}`);
      }
    }
  });
});

test("several frames with local color tables, delays and loops", () => {
  const bytes = gif({
    width: 4, height: 2, colors: PALETTE, frames: [
      { x: 0, y: 0, w: 4, h: 2, idx: [1, 1, 2, 2, 0, 0, 3, 3], delay: 50 },
      { x: 1, y: 0, w: 2, h: 1, idx: [0, 1], delay: 120, colors: [...BLUE, ...BLACK, ...RED, ...WHITE] },
    ],
  });
  const g = decodeGif(bytes);
  assert.deepEqual(g.frames.map(f => f.delay), [50, 120]);
  same(g.frames[0].rgba, 4, ["RRBB", "WWKK"], "frame 0");
  same(g.frames[1].rgba, 4, ["RBKB", "WWKK"], "frame 1");
});

test("transparency and disposal 2: the rectangle is cleared after the frame", () => {
  const bytes = gif({
    width: 4, height: 3, colors: PALETTE, frames: [
      { x: 0, y: 0, w: 4, h: 3, idx: Array(12).fill(0), disposal: 1 },
      { x: 1, y: 1, w: 2, h: 2, idx: [1, 3, 3, 1], transparent: 3, disposal: 2 },
      { x: 0, y: 0, w: 1, h: 1, idx: [2], disposal: 0 },
    ],
  });
  const g = decodeGif(bytes);
  same(g.frames[0].rgba, 4, ["WWWW", "WWWW", "WWWW"], "frame 0");
  same(g.frames[1].rgba, 4, ["WWWW", "WRWW", "WWRW"], "frame 1, transparent shows white");
  same(g.frames[2].rgba, 4, ["BWWW", "W..W", "W..W"], "frame 2, rectangle cleared");
});

test("disposal 3 restores the canvas from before the frame", () => {
  const bytes = gif({
    width: 3, height: 1, colors: PALETTE, frames: [
      { x: 0, y: 0, w: 3, h: 1, idx: [1, 1, 1] },
      { x: 1, y: 0, w: 1, h: 1, idx: [2], disposal: 3 },
      { x: 2, y: 0, w: 1, h: 1, idx: [3] },
    ],
  });
  const g = decodeGif(bytes);
  same(g.frames[1].rgba, 3, ["RBR"], "frame 1");
  same(g.frames[2].rgba, 3, ["RRK"], "frame 2");
});

test("an interlaced frame comes out in row order", () => {
  const rows = ["RRWWB", "WRRWB", "WWRRB", "BWWRR", "KBWWR", "KKBWW", "WKKBW", "WWKKB", "BWWKK", "RBWWK", "KRBWW"];
  const letter = { W: 0, R: 1, B: 2, K: 3 };
  const idx = rows.flatMap(r => [...r].map(c => letter[c]));
  const bytes = gif({ width: 5, height: 11, colors: PALETTE, version: "87a", frames: [{ x: 0, y: 0, w: 5, h: 11, idx, interlace: true }] });
  assert.equal(bytes[4], 0x37);
  same(decodeGif(bytes).frames[0].rgba, 5, rows, "interlaced");
});

test("a longer frame forces wider codes", () => {
  const w = 40, h = 30;
  const idx = Array.from({ length: w * h }, (_, i) => (i * 7 + (i >> 5)) % 4);
  const g = decodeGif(gif({ width: w, height: h, colors: PALETTE, frames: [{ x: 0, y: 0, w, h, idx }] }));
  for (let i = 0; i < w * h; i++) assert.deepEqual([...g.frames[0].rgba.subarray(4 * i, 4 * i + 3)], PALETTE.slice(3 * idx[i], 3 * idx[i] + 3));
});

test("not a GIF is refused", () => {
  assert.throws(() => decodeGif(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0, 0])), /not a GIF/);
});
