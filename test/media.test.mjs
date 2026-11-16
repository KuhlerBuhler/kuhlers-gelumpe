import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { encodeBmp } from "../src/splash-bmp.mjs";
import { encodeAnimation, decodeAnimation, frameToPixels } from "../src/loading-anim.mjs";
import { frameOfPixels } from "../src/script/gif.mjs";
import { MEDIA_FOLDER, MEDIA_MAX_FILES, DRAWN_IS_SET, listMedia, mediaName, mediaNameBytes, readMediaPicture } from "../src/script/media.mjs";

const N = 128 * 64;
const blechy = new Uint8Array(readFileSync(new URL("../assets/blechy/loading.blla", import.meta.url)));
const marker = () => { const px = new Uint8Array(N); px[0] = 1; px[N - 1] = 1; px[5 * 128 + 9] = 1; return px; };
const pic = seed => Uint8Array.from({ length: 1024 }, (_, i) => ((i * seed) >> 3) & 255);
const small = () => encodeAnimation({ progress: [pic(1), pic(2), pic(3)], loop: [pic(5), pic(7)] }).bytes;
const u16 = (b, at) => b[at] | (b[at + 1] << 8);
const slots = () => new Int32Array(1024).fill(-7);

test("a .bmp reads as one picture in the layout of frameOfPixels, the darker entry drawn", () => {
  const s = slots();
  assert.equal(readMediaPicture(encodeBmp(marker()), 0, 0, s), 1);
  const want = frameOfPixels(marker());
  assert.deepEqual(Array.from(s), Array.from(DRAWN_IS_SET ? want : want.map(b => b ^ 0xff)));
  assert.equal(s[0], DRAWN_IS_SET ? 1 : 0xfe, "pixel 0,0 is bit 0 of slot 0");
  assert.equal(s[7 * 128 + 127], DRAWN_IS_SET ? 0x80 : 0x7f, "pixel 127,63 is bit 7 of the last slot");
  const after = slots();
  assert.equal(readMediaPicture(encodeBmp(marker()), 0, 1, after), 0, "past the one picture");
  assert.ok(after.every(v => v === -7), "the slots stay");
});

test("a broken or missing .bmp is -1", () => {
  const b = encodeBmp(marker());
  const deep = b.slice(); new DataView(deep.buffer).setUint16(28, 24, true);
  const half = b.slice(); new DataView(half.buffer).setInt32(22, 32, true);
  for (const [bytes, why] of [[deep, "24 bit"], [half, "128 x 32"], [b.subarray(0, 600), "cut short"], [undefined, "missing"], [blechy, "a .blla"]]) {
    const s = slots();
    assert.equal(readMediaPicture(bytes, 0, 0, s), -1, why);
    assert.ok(s.every(v => v === -7), `${why}: the slots stay`);
  }
});

test("every picture of Blechy's loading.blla is decodeAnimation's, progress first, then the loop", () => {
  const { progress, loop } = decodeAnimation(blechy);
  const all = [...progress, ...loop];
  assert.ok(all.length > 1);
  all.forEach((f, k) => {
    const s = slots();
    assert.equal(readMediaPicture(blechy, 1, k, s), all.length, `picture ${k}`);
    assert.deepEqual(Array.from(s), Array.from(frameOfPixels(frameToPixels(f))).map(b => (DRAWN_IS_SET ? b : b ^ 0xff)), `picture ${k}`);
  });
  const s = slots();
  assert.equal(readMediaPicture(blechy, 1, all.length, s), 0);
  assert.ok(s.every(v => v === -7));
});

test("a small .blla with 3 progress and 2 loop pictures gives 5, the loop over its base", () => {
  const bytes = small();
  const want = [pic(1), pic(2), pic(3), pic(5), pic(7)];
  want.forEach((f, k) => {
    const s = slots();
    assert.equal(readMediaPicture(bytes, 1, k, s), 5);
    assert.deepEqual(Array.from(s), Array.from(f).map(b => (DRAWN_IS_SET ? b ^ 0xff : b)), `picture ${k}`);
  });
  assert.equal(readMediaPicture(bytes, 1, 5, slots()), 0);
  assert.equal(readMediaPicture(bytes, 0, 0, slots()), -1, "not a .bmp");
});

test("a .blla with a run past byte 1023 or its table behind the size is -1 for every picture", () => {
  const run = small();
  const list = u16(run, u16(run, 10));         // the first list
  const head = 1023 | (1 << 10);               // offset 1023, two bytes
  run[list + 2] = head & 255; run[list + 3] = head >> 8;
  const table = small();
  const size = u16(table, 12);
  table[10] = size & 255; table[11] = size >> 8;
  for (const [bytes, why] of [[run, "run past 1023"], [table, "table behind the size"], [small().subarray(0, 900), "cut short"]]) {
    for (let k = 0; k < 5; k++) assert.equal(readMediaPicture(bytes, 1, k, slots()), -1, `${why}, picture ${k}`);
  }
});

test("the list takes only files right in Media/ that end in the kind's ending, in card order, at most 64", () => {
  const f = name => [MEDIA_FOLDER + name, new Uint8Array(1)];
  const card = new Map([
    f("b.bmp"), f("loading.blla"), f("A.BMP"), f(".hidden.bmp"), f(".bmp"), f("sub/c.bmp"), f("x.bmpx"),
    ["KORG/blechtribe/splash.bmp", new Uint8Array(1)], ["korg/BLECHTRIBE/media/low.bmp", new Uint8Array(1)],
    f(`${"n".repeat(28)}.bmp`), f(`${"m".repeat(27)}.bmp`), f("anim.BLLA"),
  ]);
  assert.deepEqual(listMedia(card, 0).map(e => e.name), ["b", "A", "low", `${"m".repeat(15)}..`]);
  assert.deepEqual(listMedia(card, 1), [{ path: MEDIA_FOLDER + "loading.blla", name: "loading" }, { path: MEDIA_FOLDER + "anim.BLLA", name: "anim" }]);
  const many = new Map(Array.from({ length: 70 }, (_, i) => f(`p${i}.bmp`)));
  const list = listMedia(many, 0);
  assert.equal(list.length, MEDIA_MAX_FILES);
  assert.equal(list.at(-1).name, "p63");
  assert.deepEqual(listMedia(new Map(), 1), []);
});

test("a name is cut to 15 characters and .. beyond 17, and goes out one byte a character", () => {
  assert.equal(mediaName("seventeen-chars-x.bmp", 0), "seventeen-chars-x");
  assert.equal(mediaName("eighteen-chars-xyz.blla", 1), "eighteen-chars-..");
  assert.deepEqual(Array.from(mediaNameBytes("Ab.é€")), [65, 98, 46, 0xe9, 0x3f]);
});
