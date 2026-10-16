import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { applyPatches, selectFor } from "../src/patch.mjs";
import { BSDIFF_MAGIC, applyBsdiff, blocks, buildBsdiff, copyMatches, getOfft, parseBsdiff, putOfft, segments } from "../tools/patch/bsdiff.mjs";
import { COPY_FROM, COPY_TO, fixture } from "./support/patch-set.mjs";

const has = program => !spawnSync(program, ["--help"]).error;
const skip = has("bzip2") ? false : "no bzip2 program";

test("bsdiff numbers are sign and magnitude, little endian", () => {
  const b = new Uint8Array(8);
  for (const n of [0, 1, 255, 256, 2 ** 31, 0x200100, -1, -300, -(2 ** 33)]) {
    putOfft(b, 0, n);
    assert.equal(getOfft(b, 0), n);
  }
  putOfft(b, 0, -5);
  assert.deepEqual([...b], [5, 0, 0, 0, 0, 0, 0, 0x80]);
});

test("segments: equal bytes are copies, differing bytes literals, given matches win over the position", () => {
  const old = Uint8Array.from({ length: 200 }, (_, i) => (i * 7) & 0xff);
  const next = Uint8Array.from(old);
  next.set([1, 2, 3], 50);                      // a literal in the middle of an identical stretch
  next.set(old.subarray(150, 170), 100);       // a stretch copied from elsewhere
  next[199] ^= 0xff;                            // a literal at the very end
  const segs = segments(old, next, [{ at: 100, from: 150, length: 20 }]);
  assert.deepEqual(segs, [
    { copy: true, at: 0, from: 0, length: 50 },
    { copy: false, at: 50, length: 3 },
    { copy: true, at: 53, from: 53, length: 47 },
    { copy: true, at: 100, from: 150, length: 20 },
    { copy: true, at: 120, from: 120, length: 79 },
    { copy: false, at: 199, length: 1 },
  ]);
  const { ctrl, diff, extra } = blocks(next, segs);
  assert.equal(ctrl.length, 4 * 24);
  assert.ok(diff.every(b => b === 0));
  assert.deepEqual([...extra], [1, 2, 3, next[199]]);
});

test("segments refuse matches that are wrong, overlapping or outside", () => {
  const old = new Uint8Array(64).map((_, i) => i);
  const next = Uint8Array.from(old);
  assert.throws(() => segments(old, next, [{ at: 0, from: 8, length: 8 }]), /not a copy/);
  assert.throws(() => segments(old, next, [{ at: 0, from: 0, length: 8 }, { at: 4, from: 4, length: 8 }]), /overlap/);
  assert.throws(() => segments(old, next, [{ at: 60, from: 60, length: 8 }]), RangeError);
});

test("a literal at the start and an unchanged image both round-trip", { skip }, () => {
  const old = new Uint8Array(100).map((_, i) => i);
  const first = Uint8Array.from(old);
  first[0] = 0xee;
  assert.deepEqual(applyBsdiff(old, buildBsdiff(old, first)), first);
  const same = Uint8Array.from(old);
  const file = buildBsdiff(old, same);
  assert.deepEqual(applyBsdiff(old, file), same);
  assert.equal(parseBsdiff(file).extra.length, 0);
});

test("the file for a patch set rebuilds the patched image and stores only the patch's own bytes", { skip }, async () => {
  const { vsb, patches } = await fixture();
  const applied = await applyPatches(vsb, patches);
  assert.equal(applied.ok, true, applied.reasons.join(" "));
  const file = buildBsdiff(vsb, applied.bytes, copyMatches(patches, applied.spans));
  assert.equal(String.fromCharCode(...file.subarray(0, 8)), BSDIFF_MAGIC);
  assert.equal(getOfft(file, 24), applied.bytes.length);
  assert.deepEqual(applyBsdiff(vsb, file), applied.bytes);

  const { diff, extra } = parseBsdiff(file);
  assert.ok(diff.every(b => b === 0), "nothing of the old image is stored as a difference");
  // what the patches write that no old byte explains: 16 bytes of code, the 4 + 1 bytes of the copy's `over`, the splash
  const written = 16 + 4 + 1 + 1024;
  assert.ok(extra.length >= written - 8 && extra.length <= written + 32, `extra block ${extra.length}`);
  const source = Buffer.from(vsb.subarray(COPY_FROM, COPY_FROM + 256));
  for (let at = 0; at + 8 <= 64; at += 4) assert.equal(Buffer.from(extra).indexOf(source.subarray(at, at + 8)), -1, `the copy source at +${at} is in the extra block`);
});

test("copyMatches: a copy change matches everything the patch does not write over", async () => {
  const { patches } = await fixture();
  const spans = [{ file: 0x1a2200 }, { file: COPY_TO }, { file: 0 }];
  assert.deepEqual(copyMatches(patches, spans), [
    { at: COPY_TO, from: COPY_FROM, length: 8 },
    { at: COPY_TO + 12, from: COPY_FROM + 12, length: 28 },
    { at: COPY_TO + 41, from: COPY_FROM + 41, length: 23 },
  ]);
});

test("bspatch, when this system has it, builds the same image from the file", { skip: skip || (has("bspatch") ? false : "no bspatch program") }, async () => {
  const { vsb, patches } = await fixture();
  const applied = await applyPatches(vsb, patches);
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-bsdiff-"));
  const [oldPath, newPath, patchPath] = ["old.VSB", "new.VSB", "x.bsdiff"].map(n => join(dir, n));
  writeFileSync(oldPath, vsb);
  writeFileSync(patchPath, buildBsdiff(vsb, applied.bytes, copyMatches(patches, applied.spans)));
  const run = spawnSync("bspatch", [oldPath, newPath, patchPath], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(new Uint8Array(readFileSync(newPath)), applied.bytes);
});

test("a file that is not BSDIFF40, or whose control block overruns, is refused", { skip }, () => {
  assert.throws(() => parseBsdiff(new Uint8Array(40)), /not a BSDIFF40/);
  const old = new Uint8Array(32);
  const file = buildBsdiff(old, Uint8Array.from(old, () => 1));
  const cut = Uint8Array.from(file);
  putOfft(cut, 24, 1000);
  assert.throws(() => applyBsdiff(old, cut), /does not fill|corrupt/);
});

test("the BLECH set as bsdiff gives the same image as the set, with the user's firmware", { skip: skip || (process.env.E2_VSB ? false : "set E2_VSB") }, async () => {
  const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
  const patches = read("data/patches/blech.json").patches.map(read);
  const vsb = new Uint8Array(readFileSync(process.env.E2_VSB));
  const applied = await applyPatches(vsb, patches);
  assert.equal(applied.ok, true, applied.reasons.join(" "));
  const file = buildBsdiff(vsb, applied.bytes, copyMatches(selectFor(patches, "hacktribe").patches, applied.spans));
  assert.deepEqual(applyBsdiff(vsb, file), applied.bytes);
  assert.ok(parseBsdiff(file).diff.every(b => b === 0));
});
