import { test } from "node:test";
import assert from "node:assert/strict";
import { validateInputs, validateReport, checkArguments, footprint } from "../tools/patch/check_sets.mjs";

const spec = () => Object.fromEntries(["hacktribe", "stock", "synth"].map(b => [b, { path: `${b}.VSB`, sha256: "a".repeat(64) }]));
const core = ["header", "dsp_stream", "boot:normal", "kill_switch", "dsp_boot_once", "start_phase"];
const report = () => ({ ok: true, checks: core.map(id => ({ id, ok: true })) });
const progress = () => ({ total: 2, done: 2, fail: 0, groups: [{ id: "bootmap", total: 2, done: 2, fail: 0, state: "done" }] });

test("inputs require all three builds, valid hashes and paths", () => {
  assert.doesNotThrow(() => validateInputs(spec()));
  for (const build of Object.keys(spec())) {
    const missing = spec(); delete missing[build];
    assert.throws(() => validateInputs(missing), /three|build/i);
  }
  for (const field of ["path", "sha256"]) {
    const bad = spec(); bad.synth[field] = "";
    assert.throws(() => validateInputs(bad));
  }
  assert.throws(() => validateInputs({ ...spec(), extra: {} }));
});

test("a pass requires exit zero, complete core checks and completed task groups", () => {
  assert.doesNotThrow(() => validateReport(report(), 0, progress(), ["bootmap"]));
  assert.throws(() => validateReport(report(), 1, progress(), ["bootmap"]));
  for (const bad of [{ ok: true, checks: [] }, { ok: true }, { ok: false, checks: report().checks },
    { ok: true, checks: [{ id: "something", ok: true }] }]) {
    assert.throws(() => validateReport(bad, 0, progress(), ["bootmap"]));
  }
  for (const bad of [null, { ...progress(), done: 1 }, { ...progress(), fail: 1 },
    { ...progress(), groups: [] }, { ...progress(), groups: [{ ...progress().groups[0], done: 1 }] }]) {
    assert.throws(() => validateReport(report(), 0, bad, ["bootmap"]));
  }
  assert.throws(() => validateReport(report(), 0, progress(), ["bootmap", "menu_cases"]));
});

test("failed, skipped, duplicate and quick checks cannot pass", () => {
  for (const entry of [{ id: "quick", ok: true }, { id: "fault", ok: false },
    { id: "skipped", ok: true, skipped: true }, { id: "skip", ok: true, skip: "missing emulator" },
    { id: "kill_switch", ok: true }]) {
    assert.throws(() => validateReport({ ok: true, checks: [...report().checks, entry] }, 0, progress(), ["bootmap"]));
  }
});

test("check arguments contain only applyPatches exceptions and no quick flag", () => {
  const result = { allow: [[0x100, 4]], allowCode: [[0x200, 8]] };
  assert.deepEqual(checkArguments("base", "patched", result), ["--base", "base", "--patched", "patched", "--allow", "0x100:4", "--allow-code", "0x200:8"]);
  assert.throws(() => checkArguments("base", "base", result));
  assert.throws(() => checkArguments("base", "patched", { allow: [[0, -1]], allowCode: [] }));
});

test("footprint merges intervals and rejects non-FF original or undeclared RAM", () => {
  const raw = new Uint8Array(512).fill(255);
  const free = [{ start: 0xc0000000, end: 0xc0000100 }];
  const patches = [{ id: "own", ram: [{ at: "0xc0000080", length: 32 }] }];
  const spans = [{ patch: "own", file: 256, length: 64 }, { patch: "own", file: 288, length: 64 }];
  const got = footprint(raw, spans, patches, free);
  assert.equal(got.freeBytes, 256);
  assert.equal(got.codeDataBytes, 96);
  assert.equal(got.ramBytes, 32);
  assert.equal(got.unallocatedBytes, 128);
  assert.equal(got.largestGap, 96);
  const bad = raw.slice(); bad[256] = 0;
  assert.throws(() => footprint(bad, spans, patches, free));
  assert.throws(() => footprint(raw, spans, [{ id: "bad", ram: [{ at: "0xc0000200", length: 4 }] }], free));
});
