import { test } from "node:test";
import assert from "node:assert/strict";
import { applyPatches, buildsOf, selectFor, splashPatch, splashToPixels, pixelsToSplash, PATCH_FORMAT, toHex, SPLASH_W, SPLASH_H } from "../src/patch.mjs";
import { identifyBase, sha256 } from "../src/firmware.mjs";
import { field } from "../src/map/index.mjs";
import { asStock, makeFirmware } from "./helpers.mjs";

const SPLASH = field("splash").where.offset;
const FREE = 0x1a2100;              // no map field there; in the measured image a run of 0xFF

function checker() {
  const px = new Uint8Array(SPLASH_W * SPLASH_H);
  for (let y = 0; y < SPLASH_H; y++) for (let x = 0; x < SPLASH_W; x++) px[y * SPLASH_W + x] = (x + y) & 1;
  return px;
}

test("a start image round-trips through the bitmap format, bit 7 the top row of a page", () => {
  const px = new Uint8Array(SPLASH_W * SPLASH_H);
  px[0] = 1;                       // top left
  px[9 * SPLASH_W + 3] = 1;        // row 9 is page 1, second row
  const bytes = pixelsToSplash(px);
  assert.equal(bytes.length, 1024);
  assert.equal(bytes[0], 0x80);
  assert.equal(bytes[SPLASH_W + 3], 0x40);
  assert.deepEqual(splashToPixels(bytes), px);
  assert.throws(() => pixelsToSplash(new Uint8Array(10)), RangeError);
});

test("the start-image patch writes only the splash field and reports it as allowed data", async () => {
  const vsb = await makeFirmware();
  const res = await applyPatches(vsb, [splashPatch(checker())]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  const diff = [];
  for (let i = 0; i < vsb.length; i++) if (vsb[i] !== res.bytes[i]) diff.push(i);
  assert.ok(diff.length > 0 && diff.every(i => i >= SPLASH && i < SPLASH + 1024));
  assert.deepEqual(res.allow, [[SPLASH, 1024]]);
  assert.deepEqual(splashToPixels(res.bytes.subarray(SPLASH, SPLASH + 1024)), checker());
});

test("a raw change applies only over the bytes it expects", async () => {
  const vsb = await makeFirmware();
  const patch = expect => ({ format: PATCH_FORMAT, version: 1, id: "raw", changes: [{ file: FREE, bytes: "e12fff1e", expect }] });
  const good = await applyPatches(vsb, [patch(await sha256(vsb.subarray(FREE, FREE + 4)))]);
  assert.equal(good.ok, true, good.reasons.join(" "));
  assert.equal(toHex(good.bytes.subarray(FREE, FREE + 4)), "e12fff1e");
  assert.deepEqual(good.allow, [], "raw changes are never allowed at start");
  const bad = await applyPatches(vsb, [patch("00".repeat(32))]);
  assert.equal(bad.ok, false);
  assert.match(bad.reasons[0], /andere Bytes/);
  assert.equal((await applyPatches(vsb, [{ format: PATCH_FORMAT, version: 1, id: "raw", changes: [{ file: FREE, bytes: "00" }] }])).ok, false,
    "no expect, no change");
});

test("patches are refused when they overlap, leave the image or touch the header", async () => {
  const vsb = await makeFirmware();
  const one = splashPatch(checker());
  const two = { ...splashPatch(checker()), id: "splash2" };
  const res = await applyPatches(vsb, [one, two]);
  assert.equal(res.ok, false);
  assert.match(res.reasons.join(" "), /überschneidet sich mit splash/);
  const raw = file => ({ format: PATCH_FORMAT, version: 1, id: "raw", changes: [{ file, bytes: "00", expect: "00" }] });
  for (const file of [0x10, 0x200100]) assert.match((await applyPatches(vsb, [raw(file)])).reasons[0], /außerhalb/);
});

test("only writable firmware fields can be patched, with exactly their width", async () => {
  const vsb = await makeFirmware();
  const fieldPatch = (id, bytes) => ({ format: PATCH_FORMAT, version: 1, id: "f", changes: [{ field: id, bytes }] });
  assert.match((await applyPatches(vsb, [fieldPatch("crc16", "00".repeat(512))])).reasons[0], /not a firmware field/);
  assert.match((await applyPatches(vsb, [fieldPatch("splash", "00")])).reasons[0], /takes 1024 bytes/);
  assert.match((await applyPatches(vsb, [{ id: "x" }])).reasons[0], /kein Patch/);
});

test("a base that is not the measured firmware is refused before anything is written", async () => {
  const res = await applyPatches(new Uint8Array(100), [splashPatch(checker())]);
  assert.equal(res.ok, false);
  assert.equal(res.bytes, undefined);
});

// ---- builds: Hacktribe's 2.02 and Korg's own ------------------------------------------------------------------------
const rawAt = (id, bytes, expect, builds) => ({ format: PATCH_FORMAT, version: 1, id, ...(builds ? { builds } : {}), changes: [{ file: FREE, bytes, expect }] });

test("a patch is for Hacktribe's 2.02 unless it says builds, and Korg's own 2.02 is refused for it", async () => {
  const hack = await makeFirmware();
  const stock = asStock(hack);
  const was = await sha256(hack.subarray(FREE, FREE + 4));
  assert.deepEqual(buildsOf(rawAt("a", "e12fff1e", was)), ["hacktribe"]);
  assert.equal((await applyPatches(hack, [rawAt("a", "e12fff1e", was)])).ok, true);
  const refused = await applyPatches(stock, [rawAt("a", "e12fff1e", was)]);
  assert.equal(refused.ok, false);
  assert.match(refused.reasons[0], /a: ist nicht für Korgs Original 2\.02 gemacht/);
  const marked = rawAt("a", "e12fff1e", was, ["hacktribe", "stock"]);
  const done = await applyPatches(stock, [marked]);
  assert.equal(done.ok, true, done.reasons.join(" "));
  assert.equal(toHex(done.bytes.subarray(FREE, FREE + 4)), "e12fff1e");
});

test("variants of one id are chosen by the base firmware, and a base without a variant refuses the whole set", async () => {
  const hack = await makeFirmware();
  const stock = asStock(hack);
  const was = await sha256(hack.subarray(FREE, FREE + 4));
  const forHack = rawAt("folder", "11111111", was, ["hacktribe"]);
  const forStock = rawAt("folder", "22222222", was, ["stock"]);
  const both = rawAt("both", "33333333", await sha256(hack.subarray(FREE + 8, FREE + 12)), ["hacktribe", "stock"]);
  both.changes[0].file = FREE + 8;
  const set = [forHack, forStock, both];
  const onHack = await applyPatches(hack, set);
  assert.equal(onHack.ok, true, onHack.reasons.join(" "));
  assert.deepEqual([toHex(onHack.bytes.subarray(FREE, FREE + 4)), toHex(onHack.bytes.subarray(FREE + 8, FREE + 12))], ["11111111", "33333333"]);
  assert.deepEqual(onHack.spans.map(s => s.patch), ["folder", "both"]);
  const onStock = await applyPatches(stock, set);
  assert.equal(onStock.ok, true, onStock.reasons.join(" "));
  assert.equal(toHex(onStock.bytes.subarray(FREE, FREE + 4)), "22222222");
  assert.deepEqual(selectFor(set, "stock").patches, [forStock, both]);
  const alone = await applyPatches(stock, [forHack, both]);
  assert.equal(alone.ok, false);
  assert.match(alone.reasons.join(" "), /folder: ist nicht für Korgs Original 2\.02 gemacht/);
  assert.equal(alone.bytes, undefined);
});

test("Korg's own 2.02 is a base only with its init pattern, and its size has to fit", async () => {
  const stock = asStock(await makeFirmware());
  assert.deepEqual((await identifyBase(stock)).build, "stock");
  assert.equal((await identifyBase(stock)).ok, true);
  const noPattern = Uint8Array.from(stock);
  noPattern.fill(0, 0xd0058, 0xd0058 + 4);
  assert.equal((await identifyBase(noPattern)).ok, false);
  assert.equal((await identifyBase(new Uint8Array(10))).build, null);
  assert.equal((await applyPatches(noPattern, [rawAt("a", "00", "00", ["stock"])])).ok, false);
});
