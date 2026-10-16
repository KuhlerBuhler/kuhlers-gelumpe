import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatches, PATCH_FORMAT, buildsOf, fromHex } from "../src/patch.mjs";
import { checkHooks } from "../src/hooks.mjs";
import { BLECH_SET_URL, loadBlechSet } from "../src/patcher.mjs";
import { run } from "./support/spawn.mjs";

// The sample error patch: the loader of e2sSample.all skips a sample it cannot take and the window names the first
// one (tools/patch/sample_errors.py, docs/messungen/2026-10-15-sample-fehler.md).
const root = fileURLToPath(new URL("../", import.meta.url));
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/sample-errors.json");
const CODE = 0x183100;               // file offset of 0xC0183000
const CODE_END = 0x183800;           // 0xC0183700
// the replaced words: address, whether the original is a plain branch (the rest are instructions)
const WORDS = [0xC00364F0, 0xC0035FB4, 0xC0035FC4, 0xC0035FD4, 0xC004EE0C, 0xC004EE50, 0xC004EE68, 0xC0036700, 0xC0036714, 0xC00630F0, 0xC0063144];

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const stock = process.env.E2_STOCK_VSB;
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !vsb ? "E2_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);

test("the patch has the v1 format, is for both builds, says what it replaces and names what runs at start", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "sample-errors");
  assert.deepEqual(buildsOf(PATCH), ["hacktribe", "stock"]);
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
    assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  }
  for (const span of PATCH.startPhase) {
    assert.ok(span.why.length > 20);
    assert.ok(PATCH.changes.some(c => span.file >= c.file && span.file + span.length <= c.file + c.bytes.length / 2), `0x${span.file.toString(16)} is not written by the patch`);
  }
});

test("it is our code plus eleven replaced words, each a branch into it, and every hook is declared", () => {
  assert.equal(PATCH.changes.length, 1 + WORDS.length);
  const [code, ...words] = PATCH.changes;
  const n = fromHex(code.bytes).length;
  assert.ok(code.file === CODE && code.file + n <= CODE_END, `${n} bytes`);
  for (const [i, address] of WORDS.entries()) {
    assert.equal(words[i].file, address - 0xC0000000 + 0x100);
    const word = Buffer.from(fromHex(words[i].bytes)).readUInt32LE(0);
    assert.equal((word >>> 24) & 0x0E, 0x0A, `0x${address.toString(16)} is a branch`);
    const target = address + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    assert.ok(target >= 0xC0183000 && target < 0xC0183000 + n, `0x${address.toString(16)} goes into our code`);
  }
  assert.deepEqual(PATCH.hooks.map(h => h.site).sort(), WORDS.map(a => `0x${a.toString(16).toUpperCase()}`).sort());
  const res = checkHooks([PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("it keeps its run time state in free RAM of its own, clear of Blechy's block and of the start image editor", () => {
  assert.deepEqual(PATCH.ram.map(r => [r.at, r.length]), [["0xC0183800", 256]]);
  assert.ok(0xC0183900 <= 0xC0184000 && 0xC0183700 <= 0xC0183800);
});

test("it is part of the BLECH set and applies together with the others", async () => {
  const set = await loadBlechSet(async url => read(`../${url}`), BLECH_SET_URL);
  assert.ok(set.patches.some(p => p.id === "sample-errors"));
  const res = checkHooks(set.patches.filter(p => buildsOf(p).includes("stock")));
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("the assembler and the patch builder agree with the committed patch, for either build's firmware", { skip }, () => {
  for (const path of [vsb, stock].filter(Boolean)) {
    const out = spawnSync(python(), [join(root, "tools/patch/sample_errors.py"), "--vsb", path], { encoding: "utf8", timeout: 60_000 });
    assert.ifError(out.error);
    assert.equal(out.status, 0, out.stderr);
    assert.deepEqual(JSON.parse(out.stdout), PATCH, "rebuild with tools/patch/sample_errors.py --vsb SYSTEM.VSB --out data/patches/sample-errors.json");
  }
});

test("in the emulator a sample the loader refuses is skipped, the window names it, EXIT at power-on changes nothing", { skip: skipEmu }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-sample-errors-"));
  try {
    const set = await loadBlechSet(async url => read(`../${url}`), BLECH_SET_URL);
    const base = readFileSync(vsb);
    const patched = await applyPatches(new Uint8Array(base), set.patches);
    assert.equal(patched.ok, true, patched.reasons?.join(" "));
    const firmware = join(dir, "BLECH.VSB");
    writeFileSync(firmware, patched.bytes);
    const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
    const result = await run(python(), ["tools/emu/sample_error_cases.py", "cases", "--patched", firmware, ...flash.length ? ["--flash", ...flash] : []], {
      cwd: root, env: { ...process.env, GELUMPE_JOBS: process.env.GELUMPE_JOBS || "4" }, timeout: 900_000, maxBuffer: 16 * 1024 * 1024,
    });
    assert.ifError(result.error);
    const report = JSON.parse(result.stdout);
    assert.deepEqual(report.filter(c => !c.ok), []);
    assert.ok(report.length >= 12);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
