import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parseSampleFile, parseRemote, entryFromWav, emptySampleFile } from "../src/sample-file.mjs";
import { wav, file, put32 } from "./support/sample-file.mjs";
import { applyPatches } from "../src/patch.mjs";
import { loadBlechSet, BLECH_SET_URL } from "../src/patcher.mjs";
import { emuPython } from "./support/emu.mjs";
import { run } from "./support/spawn.mjs";

test("the sample index can select an appended replacement while retaining unreachable old data", async () => {
  const original = file({ 500: "First", 501: "Second" });
  const replacement = entryFromWav(wav({ frames: 400 }), 500, "Replacement");
  const appended = new Uint8Array(original.length + replacement.length);
  appended.set(original);
  appended.set(replacement, original.length);
  const before = parseSampleFile(original);
  assert.deepEqual(parseSampleFile(appended).samples, before.samples, "an append alone keeps the old index usable");
  put32(appended, 16 + 500 * 4, original.length);
  const local = parseSampleFile(appended);
  const remote = await parseRemote(async (at, length) => appended.slice(at, at + length), appended.length);
  for (const parsed of [local, remote]) {
    assert.deepEqual(parsed.samples.map(s => [s.slot, s.name, s.problem]), [[500, "Replacement", null], [501, "Second", null]]);
    assert.equal(parsed.samples[0].offset, original.length);
    assert.equal(parsed.samples[1].offset, before.samples[1].offset);
  }
  assert.deepEqual(appended.slice(before.samples[0].offset, original.length), original.slice(before.samples[0].offset));
});

test("the remote parser follows unsigned 32-bit index offsets without allocating the full library", async () => {
  const entry = entryFromWav(wav({ frames: 400 }), 500, "Far away");
  for (const offset of [0x10000000, 0x40000000, 0x80000000, 0xFFFFFFFF - entry.length]) {
    const header = emptySampleFile();
    put32(header, 16 + 500 * 4, offset);
    const requested = [];
    const parsed = await parseRemote(async (at, length) => {
      requested.push(length);
      if (at === 0) return header.slice(0, length);
      assert.ok(at >= offset && at + length <= offset + entry.length);
      return entry.slice(at - offset, at - offset + length);
    }, offset + entry.length);
    assert.equal(parsed.samples[0].offset, offset);
    assert.equal(parsed.samples[0].name, "Far away");
    assert.equal(parsed.samples[0].problem, null);
    assert.ok(requested.every(n => n <= 4096));
  }
});

test("native and swap loaders follow the appended index entry instead of an unreachable earlier version", {
  skip: !process.env.E2_VSB && "E2_VSB not set",
}, async () => {
  const set = await loadBlechSet(async url => JSON.parse(readFileSync(new URL(`../${url}`, import.meta.url), "utf8")), BLECH_SET_URL);
  const directory = mkdtempSync(join(tmpdir(), "gelumpe-sample-persistence-"));
  try {
    for (const original of [process.env.E2_VSB, process.env.E2_STOCK_VSB].filter(Boolean)) {
      const patched = await applyPatches(new Uint8Array(readFileSync(original)), set.patches);
      assert.equal(patched.ok, true, patched.reasons?.join(" "));
      const path = join(directory, "patched.vsb");
      writeFileSync(path, patched.bytes);
      const result = await run(emuPython(), ["tools/emu/sample_persistence_cases.py", "--patched", path], { timeout: 120_000 });
      assert.ifError(result.error);
      assert.equal(result.status, 0, result.stderr || result.stdout);
      const report = JSON.parse(result.stdout);
      assert.equal(report.hardware_contact, false);
      assert.equal(report.checks.length, 4);
      assert.deepEqual(report.checks.filter(c => !c.ok), []);
      const writer = await run(emuPython(), ["tools/emu/sample_store_cases.py", "--patched", path], { timeout: 120_000 });
      assert.ifError(writer.error);
      assert.equal(writer.status, 0, writer.stderr || writer.stdout);
      const saved = JSON.parse(writer.stdout);
      assert.equal(saved.hardware_contact, false);
      assert.equal(saved.checks.length, 11);
      assert.deepEqual(saved.checks.filter(c => !c.ok), []);
      const capture = await run(emuPython(), ["tools/emu/sample_capture_cases.py", "--patched", path], { timeout: 60_000 });
      assert.ifError(capture.error);
      assert.equal(capture.status, 0, capture.stderr || capture.stdout);
      const recorded = JSON.parse(capture.stdout);
      assert.equal(recorded.hardware_contact, false);
      assert.equal(recorded.audio, false);
      assert.equal(recorded.dma, false);
      assert.equal(recorded.checks.length, 3);
      assert.deepEqual(recorded.checks.filter(c => !c.ok), []);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
