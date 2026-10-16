import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { run as exec, slots } from "./support/spawn.mjs";
import { existsSync, readFileSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { applyPatches, selectFor, PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { checkHooks } from "../src/hooks.mjs";
import { checkRam } from "../src/ramspans.mjs";
import { identifyBase } from "../src/firmware.mjs";

// Synth filters on Korg's original (docs/messungen/2026-10-15-synth-filter.md).
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/synth-filters.json");
const ALL = read("../data/patches/blech.json").patches.map(p => read(`../${p}`));
const STOCK_SET = selectFor(ALL, "stock").patches;
const CODE = 0x190100;              // file offset of 0xC0190000
const CODE_END = 0x190200;          // 0xC0190100
// the replaced words: the key handler's comparison with 0x14 and the part setter's branch past the folding
const WORDS = [[0x6fce8 + 0x100, 0xc006fce8], [0x495dc + 0x100, 0xc00495dc]];

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const stock = process.env.E2_STOCK_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !stock ? "E2_STOCK_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);
const flashArgs = flash.length ? ["--flash", ...flash] : [];

test("the synth filters patch has the v1 format, is for Korg's build only, copies nothing and declares no RAM", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "synth-filters");
  assert.deepEqual(PATCH.builds, ["stock"]);
  assert.deepEqual(PATCH.notNeededOn, ["hacktribe"], "a set skips it on Hacktribe's build instead of refusing");
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
    assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  }
  assert.deepEqual(PATCH.ram, []);
});

test("it is our code plus two replaced words, each branching into the code, and every hook is declared", () => {
  assert.equal(PATCH.changes.length, 1 + WORDS.length);
  const [code, ...words] = PATCH.changes;
  const n = fromHex(code.bytes).length;
  assert.ok(code.file === CODE && code.file + n <= CODE_END, `${n} bytes`);
  for (const [i, [file, address]] of WORDS.entries()) {
    assert.equal(words[i].file, file);
    const word = Buffer.from(fromHex(words[i].bytes)).readUInt32LE(0);
    assert.equal(word >>> 24, 0xea, `0x${address.toString(16)} branches`);
    const target = address + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    assert.ok(target >= 0xc0190000 && target < 0xc0190000 + n, `0x${address.toString(16)} goes into our code`);
  }
  assert.deepEqual(PATCH.hooks.map(h => h.site).sort(), WORDS.map(([, a]) => `0x${a.toString(16).toUpperCase()}`).sort());
  const res = checkHooks([PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("the setter runs at start, so its word and the code are named; the key handler runs only on a key and is not", () => {
  const spans = PATCH.startPhase.map(s => [s.file, s.length]);
  assert.ok(spans.some(([file]) => file === WORDS[1][0]), "the part setter runs for the parts of the first pattern at start");
  assert.ok(spans.some(([file]) => file === CODE));
  assert.ok(!spans.some(([file]) => file === WORDS[0][0]), "the key handler runs only on a key");
  for (const s of PATCH.startPhase) assert.ok(s.why.length > 20, "every span says why");
});

test("the table in the code is the rule: a cycle per family, the same make across families, OFF at the end", () => {
  const code = Buffer.from(fromHex(PATCH.changes[0].bytes));
  const table = code.subarray(code.length - 51);
  const row = key => Array.from({ length: 17 }, (_, current) => table[key * 17 + current]);
  assert.deepEqual(row(0), [1, 2, 3, 4, 5, 6, 0, 1, 2, 4, 5, 6, 1, 2, 4, 5, 6]);
  assert.deepEqual(row(1), [7, 7, 8, 7, 9, 10, 11, 8, 9, 10, 11, 0, 7, 8, 9, 10, 11]);
  assert.deepEqual(row(2), [12, 12, 13, 12, 14, 15, 16, 12, 13, 14, 15, 16, 13, 14, 15, 16, 0]);
});

test("it sits clear of every other patch of the stock set and is accepted with all of them", () => {
  const span = (c, id) => [c.file, c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length), id];
  const mine = PATCH.changes.map(c => span(c, PATCH.id));
  const others = STOCK_SET.filter(p => p.id !== PATCH.id).flatMap(p => p.changes.filter(c => typeof c.file === "number").map(c => span(c, p.id)));
  for (const [a, b] of mine) for (const [c, d, id] of others) assert.ok(b <= c || d <= a, `synth-filters and ${id} overlap at 0x${Math.max(a, c).toString(16)}`);
  const res = checkHooks(STOCK_SET);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.deepEqual(checkRam(STOCK_SET), []);
});

test("the Hacktribe build does not get it, and the set is not refused for it", () => {
  const chosen = selectFor(ALL, "hacktribe");
  assert.deepEqual(chosen.reasons, []);
  assert.equal(chosen.patches.some(p => p.id === "synth-filters"), false);
  assert.equal(selectFor([PATCH], "hacktribe").reasons.length, 0);
  assert.equal(selectFor([{ ...PATCH, notNeededOn: undefined }], "hacktribe").reasons.length, 1, "without the marker a patch for the other build is still a reason");
});

test("the assembler and the patch builder agree with the committed patch", { skip }, () => {
  const run = spawnSync(python(), [join(dir, "patch/synth_filters.py"), "--vsb", stock], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/synth_filters.py --vsb SYSTEM.VSB --out data/patches/synth-filters.json");
});

test("applied to Korg's own firmware it changes only what it names", { skip }, async () => {
  const original = new Uint8Array(readFileSync(stock));
  const res = await applyPatches(original, [PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  const after = await identifyBase(res.bytes);
  assert.deepEqual([after.ok, after.build], [true, "stock"]);
  const named = PATCH.changes.map(c => [c.file, c.bytes.length / 2]);
  for (let i = 0; i < original.length; i++) {
    if (original[i] !== res.bytes[i]) assert.ok(named.some(([at, n]) => i >= at && i < at + n), `0x${i.toString(16)} changed without being named`);
  }
  const all = await applyPatches(original, STOCK_SET);
  assert.equal(all.ok, true, all.reasons.join(" "));
});

describe("the synth filters in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-10-15/synth-filter, the whole BLECH set on Korg's build: keys, names, LEDs, pattern load, round trip and EXIT at power-on", { skip: skipEmu }, async () => {
    const original = new Uint8Array(readFileSync(stock));
    const res = await applyPatches(original, STOCK_SET);
    assert.equal(res.ok, true, res.reasons.join(" "));
    const directory = mkdtempSync(join(tmpdir(), "gelumpe-synthfilter-"));
    const path = join(directory, "SYSTEM.VSB");
    writeFileSync(path, res.bytes);
    try {
      const run = await exec(python(), [join(dir, "emu/synth_filter_cases.py"), "cases", "--patched", path, ...flashArgs], { timeout: 1_800_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.filter(c => !c.ok), []);
      for (const key of ["lpf", "hpf", "bpf"]) {
        for (const id of ["cycle", "leds", "names", "message", "frames", "table"]) assert.ok(report.some(c => c.id === `synthfilter:${key}_${id}`), `${key}_${id}`);
      }
      for (const id of ["electribe_frames_are_korgs", "load_keeps_type", "load_leaves_slot", "roundtrip", "kill_keys_are_korgs", "kill_folds_synth_types", "kill_write_loses_type"]) {
        assert.ok(report.some(c => c.id === `synthfilter:${id}`), id);
      }
      assert.equal(run.status, 0);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
