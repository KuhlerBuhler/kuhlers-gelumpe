import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { applyPatches, PATCH_FORMAT } from "../src/patch.mjs";
import { sha256 } from "../src/firmware.mjs";
import { field, typeOf } from "../src/map/index.mjs";
import { encodeAnimation, decodeAnimation, loadingAnimPatch, MAX_BYTES, FRAME_BYTES, LOADING_ANIM_ID } from "../src/loading-anim.mjs";
import { withLoadingAnim } from "../src/patcher.mjs";
import { makeFirmware } from "./helpers.mjs";

const SLOT = 0xc01a6000 - 0xc0000000 + 0x100;   // tools/patch/load_bar.py:ANIM_SLOT as a file offset
const FREE = 0x1a2100;
const frame = fill => new Uint8Array(FRAME_BYTES).fill(fill);
const small = () => encodeAnimation({ progress: [frame(0), frame(0x0f), frame(0xff)], loop: [frame(0x55)] }).bytes;

/** A stand-in for load-bar: one raw change, and the slot declared as its RAM, as the real patch does. */
async function loadBar(vsb) {
  return {
    format: PATCH_FORMAT, version: 1, id: "load-bar", builds: ["hacktribe", "stock"],
    changes: [{ file: FREE, bytes: "e12fff1e", expect: await sha256(vsb.subarray(FREE, FREE + 4)) }],
    ram: [{ at: "0xC01A6000", length: MAX_BYTES, what: "a custom loading animation", source: "tools/patch/load_bar.py:ANIM_SLOT" }],
  };
}

test("the map field of the animation is load_bar's slot, MAX_BYTES long", () => {
  const f = field("loadingAnim");
  assert.equal(f.where.offset, SLOT);
  assert.equal(typeOf(f).width, MAX_BYTES);
  const py = readFileSync(new URL("../tools/patch/load_bar.py", import.meta.url), "utf8");
  assert.match(py, /^ANIM_SLOT = 0xC01A6000\b/m);
  assert.match(py, /^ANIM_SLOT_END = 0xC01AA000\b/m);
});

test("the patch writes the file into the slot, the rest of the slot FF", () => {
  const bytes = small();
  const patch = loadingAnimPatch(bytes);
  assert.equal(patch.id, LOADING_ANIM_ID);
  assert.deepEqual(patch.builds, ["hacktribe", "stock"], "load-bar's builds, never the blue one");
  assert.equal(patch.changes.length, 1);
  assert.equal(patch.changes[0].field, "loadingAnim");
  const hex = patch.changes[0].bytes;
  assert.equal(hex.length, 2 * MAX_BYTES);
  assert.equal(hex.slice(0, 2 * bytes.length), Buffer.from(bytes).toString("hex"));
  assert.match(hex.slice(2 * bytes.length), /^(ff)+$/);
});

test("the patch refuses a file the firmware would reject", () => {
  const bad = small();
  bad[0] = 0x58;
  assert.throws(() => loadingAnimPatch(bad), /wrong magic/);
  assert.throws(() => loadingAnimPatch(new Uint8Array(4)), /shorter than the header/);
  const big = new Uint8Array(MAX_BYTES + 1);
  big.set(small());
  new DataView(big.buffer).setUint32(12, MAX_BYTES + 1, true);
  assert.throws(() => loadingAnimPatch(big), /more than 16384/);
});

test("with load-bar in the copy the animation lands in the slot and is allowed at start", async () => {
  const vsb = await makeFirmware();
  const first = await applyPatches(vsb, [await loadBar(vsb)]);
  assert.equal(first.ok, true, first.reasons.join(" "));
  const res = await withLoadingAnim(first, small());
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal(res.bytes[FREE], 0xe1, "load-bar's own change stays");
  const back = decodeAnimation(res.bytes.subarray(SLOT, SLOT + MAX_BYTES));
  assert.deepEqual(back.progress.map(f => f[0]), [0, 0x0f, 0xff]);
  assert.deepEqual(res.allow, [[SLOT, MAX_BYTES]], "the slot is data the start reads");
  assert.deepEqual([...new Set(res.spans.map(s => s.patch))], ["load-bar", LOADING_ANIM_ID]);
  for (let i = 0; i < vsb.length; i++) {
    if (i === FREE) { i += 3; continue; }
    if (i === SLOT) { i += MAX_BYTES - 1; continue; }
    if (vsb[i] !== res.bytes[i]) assert.fail(`byte 0x${i.toString(16)} changed outside the slot`);
  }
});

test("without load-bar, or without an own animation, the slot is left alone", async () => {
  const vsb = await makeFirmware();
  const other = { ...(await loadBar(vsb)), id: "other", ram: [] };
  const without = await applyPatches(vsb, [other]);
  const res = await withLoadingAnim(without, small());
  assert.equal(res, without, "no load-bar, nothing reads the slot: nothing is written");
  const withBar = await applyPatches(vsb, [await loadBar(vsb)]);
  assert.equal(await withLoadingAnim(withBar, null), withBar, "the default: no own file, Blechy stays");
  const failed = { ok: false, reasons: ["x"], spans: [], allow: [], allowCode: [], dependencies: [] };
  assert.equal(await withLoadingAnim(failed, small()), failed);
});

test("an animation the firmware would reject is not written", async () => {
  const vsb = await makeFirmware();
  const first = await applyPatches(vsb, [await loadBar(vsb)]);
  const bad = small();
  bad[4] = 2;
  await assert.rejects(withLoadingAnim(first, bad), /version 2/);
});
