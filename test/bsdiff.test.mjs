import { test } from "node:test";
import assert from "node:assert/strict";
import { applyBsdiff, parseBsdiff } from "../src/bsdiff.mjs";
import { edited, expected, fixture, oldFile, sha, SIZE } from "./fixtures/bsdiff/data.mjs";

// The patch is written by bsdiff4 from made-up data (test/fixtures/bsdiff/make.py), like Hacktribe's.
const patch = () => fixture("./patch/edit.patch");

test("bsdiff: the made-up old file and its edit are the ones the patch was made from", () => {
  const old = oldFile();
  assert.equal(sha(old), expected.patch.old);
  assert.equal(sha(edited(old)), expected.patch.new);
});

test("bsdiff: a bsdiff4 patch turns the old file into the new one, byte for byte", () => {
  const out = applyBsdiff(oldFile(), patch());
  assert.equal(out.length, SIZE);
  assert.equal(sha(out), expected.patch.new);
  assert.deepEqual(out, edited(oldFile()));
});

test("bsdiff: the header says how large the result is", () => {
  assert.deepEqual(Object.keys(parseBsdiff(patch())), ["ctrlLength", "diffLength", "newSize"]);
  assert.equal(parseBsdiff(patch()).newSize, SIZE);
});

test("bsdiff: a file without the BSDIFF40 head, or too short, is named", () => {
  const bad = patch();
  bad[0] = 0x58;
  assert.throws(() => parseBsdiff(bad), /BSDIFF40/);
  assert.throws(() => parseBsdiff(new Uint8Array(10)), /zu kurz/);
});

test("bsdiff: a cut-off patch and a damaged part are refused", () => {
  assert.throws(() => applyBsdiff(oldFile(), patch().subarray(0, 100)), /abgeschnitten/);
  const bad = patch().slice();
  bad[bad.length - 5] ^= 0xff;                      // inside the extra stream
  assert.throws(() => applyBsdiff(oldFile(), bad), /beschädigt/);
});

test("bsdiff: a patch that announces more than allowed is refused before anything is built", () => {
  assert.throws(() => applyBsdiff(oldFile(), patch(), { maxNewSize: 1000 }), /größere Datei/);
});

test("bsdiff: applied to another file it still runs and the checksum tells the difference", () => {
  const other = oldFile();
  other[1000] ^= 1;
  assert.notEqual(sha(applyBsdiff(other, patch())), expected.patch.new);
});
