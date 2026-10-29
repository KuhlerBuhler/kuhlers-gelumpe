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
import { emuPython } from "./support/emu.mjs";
import { run } from "./support/spawn.mjs";

// The sample swap: a sample file larger than the DSP's user bank, the active set in the DSP, the rest from the card or a RAM
// cache (tools/patch/sample_swap.py, docs/messungen/2026-10-26-sample-swap-bau.md).
const root = fileURLToPath(new URL("../", import.meta.url));
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/sample-swap.json");
const SITES = [0xC00364F4, 0xC0036510, 0xC00366D8, 0xC003621C, 0xC00369F0, 0xC00836F4, 0xC002D684, 0xC005F1D4, 0xC0079A74, 0xC0099FFC, 0xC0099D88];
const AREAS = [[0xC01A2FD0, 0xC01A3C00], [0xC018A4C0, 0xC018AF00], [0xC0189760, 0xC0189F00],
  [0xC019A400, 0xC019C400], [0xC018BF40, 0xC018C400]];
const file = address => address - 0xC0000000 + 0x100;

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const stock = process.env.E2_STOCK_VSB;
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !vsb ? "E2_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);

test("the patch has the v1 format, is for both red builds and copies nothing of the firmware", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.id, "sample-swap");
  assert.deepEqual(buildsOf(PATCH), ["hacktribe", "stock"]);
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/);
    assert.ok(change.note);
    assert.equal(change.copy, undefined);
  }
  for (const span of PATCH.startPhase) {
    assert.ok(span.why.length > 20);
    assert.ok(PATCH.changes.some(c => span.file >= c.file && span.file + span.length <= c.file + c.bytes.length / 2));
  }
});

test("it is code in five free areas plus a branch at each of its eleven sites into that code", () => {
  const code = PATCH.changes.slice(0, AREAS.length);
  for (const [i, [lo, hi]] of AREAS.entries()) {
    assert.equal(code[i].file, file(lo));
    assert.ok(code[i].file + code[i].bytes.length / 2 <= file(hi));
  }
  const words = PATCH.changes.slice(AREAS.length);
  assert.deepEqual(words.map(w => w.file), SITES.map(file));
  for (const [i, site] of SITES.entries()) {
    const word = Buffer.from(fromHex(words[i].bytes)).readUInt32LE(0);
    assert.equal((word >>> 24) & 0x0E, 0x0A, `0x${site.toString(16)} is a branch`);
    const target = site + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    assert.ok(AREAS.some(([lo, hi]) => target >= lo && target < hi), `0x${site.toString(16)} goes into the swap's code`);
  }
  assert.deepEqual(PATCH.hooks.map(h => h.site), SITES.map(a => `0x${a.toString(16).toUpperCase()}`));
  const res = checkHooks([PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("its state is in a free run and its buffers and cache above the interrupt stack", () => {
  assert.deepEqual(PATCH.ram.slice(0, 2).map(r => [r.at, r.length]), [["0xC0188530", 0x200], ["0xC274F000", 0xC4000000 - 0xC274F000]]);
});

test("it is part of the BLECH set and composes with every other patch of both red builds", async () => {
  const set = await loadBlechSet(async url => read(`../${url}`), BLECH_SET_URL);
  assert.ok(set.patches.some(p => p.id === "sample-swap"));
  for (const build of ["hacktribe", "stock"]) {
    const res = checkHooks(set.patches.filter(p => buildsOf(p).includes(build)));
    assert.equal(res.ok, true, res.reasons.join(" "));
  }
  const synth = read("../data/patches/blech-synth.json").patches;
  assert.ok(!synth.includes("data/patches/sample-swap.json"), "the blue Synth has no mapped places for the swap");
});

test("its routines run in ARM against tables made in the test", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "test_sample_swap"], {
    cwd: fileURLToPath(new URL("../tools/patch/", import.meta.url)), encoding: "utf8", timeout: 120_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("the builder agrees with the committed patch, for either build's firmware", { skip }, () => {
  for (const path of [vsb, stock].filter(Boolean)) {
    const out = spawnSync(python(), [join(root, "tools/patch/sample_swap.py"), "--vsb", path], { encoding: "utf8", timeout: 120_000 });
    assert.ifError(out.error);
    assert.equal(out.status, 0, out.stderr);
    assert.deepEqual(JSON.parse(out.stdout), PATCH, "rebuild with tools/patch/sample_swap.py --vsb SYSTEM.VSB --out data/patches/sample-swap.json");
  }
});

test("in the emulator the swap starts with the first pattern, waits at a switch, keeps the budget and owns its cache only while playing", { skip: skipEmu }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-sample-swap-"));
  try {
    const set = await loadBlechSet(async url => read(`../${url}`), BLECH_SET_URL);
    const patched = await applyPatches(new Uint8Array(readFileSync(vsb)), set.patches);
    assert.equal(patched.ok, true, patched.reasons?.join(" "));
    const firmware = join(dir, "BLECH.VSB");
    writeFileSync(firmware, patched.bytes);
    const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
    const result = await run(python(), ["tools/emu/swap_cases.py", "cases", "--patched", firmware, ...flash.length ? ["--flash", ...flash] : []], {
      cwd: root, timeout: 3_600_000, maxBuffer: 16 * 1024 * 1024,
    });
    assert.ifError(result.error);
    const report = JSON.parse(result.stdout);
    assert.deepEqual(report.filter(c => !c.ok), []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
