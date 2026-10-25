import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { run as exec, slots } from "./support/spawn.mjs";
import { existsSync, readFileSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { applyPatches, PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { identify } from "../src/firmware.mjs";

// The MFX 2 switch (docs/messungen/2026-10-10-mfx-umschalter.md).
const PATCH = JSON.parse(readFileSync(new URL("../data/patches/mfx-switch.json", import.meta.url), "utf8"));
const SPLASH = JSON.parse(readFileSync(new URL("../data/patches/splash-editor.json", import.meta.url), "utf8"));
const CODE = 0x1a5100;               // file offset of 0xC01A5000
const CODE_END = 0x1a5d00;           // 0xC01A5C00
// file offset of each hooked word: the key dispatcher's first instruction, the screen tick call, the type setter's first instruction, the pattern copy call
const HOOKS = [[0x701d8, 0xea, 0xc00700d8], [0x837f8, 0xeb, 0xc00836f8], [0x48b64, 0xea, 0xc0048a64], [0x4c3bc, 0xeb, 0xc004c2bc]];

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !vsb ? "E2_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);
const flashArgs = flash.length ? ["--flash", ...flash] : [];

test("the MFX switch patch has the v1 format, says what it replaces and names what runs at start", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "mfx-switch");
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
    assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  }
});

test("the spans it asks to run at start are inside its changes, small, and leave out the key hook and the flash code", () => {
  assert.equal(PATCH.startPhase.length, 5);
  let code = 0;
  for (const span of PATCH.startPhase) {
    assert.ok(span.why.length > 10);
    const inside = PATCH.changes.some(c => span.file >= c.file && span.file + span.length <= c.file + c.bytes.length / 2);
    assert.ok(inside, `0x${span.file.toString(16)} is not written by the patch`);
    if (span.file >= CODE && span.file < CODE_END) code += span.length;
  }
  assert.ok(code < 640, `${code} bytes of our code run at start`);
  const [codeChange] = PATCH.changes;
  const keyHookEnd = CODE + 0x13c;      // key_hook and call_fw
  assert.ok(!PATCH.startPhase.some(s => s.file < keyHookEnd && s.file + s.length > CODE && s.file >= CODE), "the key hook does not run at start");
  assert.ok(codeChange.bytes.length / 2 > code);
});

test("the patch is our code in the free run plus four hooked words, each a branch into it", () => {
  assert.equal(PATCH.changes.length, 1 + HOOKS.length);
  const [code, ...hooks] = PATCH.changes;
  const n = fromHex(code.bytes).length;
  assert.ok(code.file === CODE && code.file + n <= CODE_END, `${n} bytes`);
  assert.equal(hooks.length, HOOKS.length);
  for (const [i, [file, opcode, address]] of HOOKS.entries()) {
    assert.equal(hooks[i].file, file);
    const word = Buffer.from(fromHex(hooks[i].bytes)).readUInt32LE(0);
    assert.equal(word >>> 24, opcode, `0x${address.toString(16)} branches${opcode === 0xeb ? " and links" : ""}`);
    const off = ((word & 0xffffff) << 8) >> 8;
    const target = address + 8 + off * 4;
    assert.ok(target >= 0xc01a5000 && target < 0xc01a5000 + n, `0x${address.toString(16)} goes into our code`);
  }
});

test("it sits clear of the splash editor and both patches apply together", async () => {
  const splashEnd = Math.max(...SPLASH.changes.map(c => c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length)).filter(e => e < 0x1b0000));
  assert.ok(splashEnd <= CODE, `splash editor ends at 0x${splashEnd.toString(16)}`);
  const spans = [...SPLASH.changes, ...PATCH.changes].map(c => [c.file, c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length)]).sort((a, b) => a[0] - b[0]);
  for (let i = 1; i < spans.length; i++) assert.ok(spans[i][0] >= spans[i - 1][1], "no overlap");
});

test("the assembler and the patch builder agree with the committed patch", { skip }, () => {
  const run = spawnSync(python(), [join(dir, "patch/mfx_switch.py"), "--vsb", vsb], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/mfx_switch.py --vsb SYSTEM.VSB --out data/patches/mfx-switch.json");
});

test("the default MFX 2 type is a patch parameter", { skip }, () => {
  const build = (...args) => {
    const run = spawnSync(python(), [join(dir, "patch/mfx_switch.py"), "--vsb", vsb, ...args], { encoding: "utf8", timeout: 60_000 });
    assert.equal(run.status, 0, run.stderr);
    return JSON.parse(run.stdout).changes[0].bytes;
  };
  const base = build();
  assert.notEqual(build("--b-type", "12"), base);
  assert.equal(build("--b-type", "7"), base);
  const refused = spawnSync(python(), [join(dir, "patch/mfx_switch.py"), "--vsb", vsb, "--b-type", "0"], { encoding: "utf8" });
  assert.notEqual(refused.status, 0);
});

test("applied to the own firmware it changes only what it names, and the splash editor goes with it", { skip }, async () => {
  const original = new Uint8Array(readFileSync(vsb));
  const res = await applyPatches(original, [PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal((await identify(res.bytes)).known, true);
  const named = PATCH.changes.map(c => [c.file, c.bytes.length / 2]);
  assert.ok(named.slice(1).every(([, n]) => n === 4));
  for (let i = 0; i < original.length; i++) {
    if (original[i] !== res.bytes[i]) assert.ok(named.some(([at, n]) => i >= at && i < at + n), `0x${i.toString(16)} changed without being named`);
  }
  assert.equal(res.allowCode.length, PATCH.startPhase.length, "the spans the patch asks to run at start");
  const both = await applyPatches(original, [SPLASH, PATCH]);
  assert.equal(both.ok, true, both.reasons.join(" "));
  assert.equal(both.allowCode.length, SPLASH.startPhase.length + PATCH.startPhase.length, "the splash editor's spans and this patch's");
});

describe("the MFX 2 switch in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-10-10/mfx-umschalter, the switch, the DSP messages and the kill switch", { skip: skipEmu }, async () => {
    const patched = await patchedCopy([PATCH]);
    try {
      const run = await exec(python(), [join(dir, "emu/mfx_cases.py"), "cases", "--base", vsb, "--patched", patched.path, ...flashArgs], { timeout: 600_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.checks.filter(c => !c.ok), []);
      for (const id of ["boot", "switch", "dsp_messages", "exit_held"]) assert.ok(report.checks.some(c => c.id === `mfx:${id}`), id);
      assert.equal(run.status, 0);
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-10/mfx-umschalter, scripted run against the stock firmware", { skip: skipEmu }, async () => {
    const patched = await patchedCopy([PATCH]);
    try {
      const run = await exec(python(), [join(dir, "emu/mfx_cases.py"), "run", "--base", vsb, "--patched", patched.path, ...flashArgs], { timeout: 1_800_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.steps.filter(s => !s.ok), []);
      assert.ok(report.steps.length >= 40);
      assert.equal(run.status, 0);
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-10/mfx-umschalter, the export check passes with the start spans the patch names, alone and together with the splash editor", { skip: skipEmu }, async () => {
    const alone = await patchedCopy([PATCH]);
    const both = await patchedCopy([SPLASH, PATCH]);
    try {
      const args = copy => ["--base", vsb, "--patched", copy.path, ...flashArgs, ...copy.allowCode.flatMap(([at, n]) => ["--allow-code", `0x${at.toString(16)}:${n}`])];
      for (const copy of [alone, both]) {
        const run = await exec(python(), [join(dir, "emu/check.py"), ...args(copy)], { timeout: 1_800_000, maxBuffer: 8 * 1024 * 1024 });
        assert.ifError(run.error);
        const report = JSON.parse(run.stdout);
        assert.deepEqual(report.checks.filter(c => !c.ok), []);
        assert.ok(report.checks.some(c => c.id === "mfx:switch"), "the patch's own cases ran");
        assert.equal(run.status, 0);
      }
      assert.equal(alone.allowCode.length, 5);
      const bare = await exec(python(), [join(dir, "emu/check.py"), "--base", vsb, "--patched", alone.path, ...flashArgs], { timeout: 1_800_000, maxBuffer: 8 * 1024 * 1024 });
      assert.equal(bare.status, 1, "without the spans the hooks are changes in the start code");
    } finally {
      alone.remove();
      both.remove();
    }
  });
});

function patchedCopy(patches) {
  const original = new Uint8Array(readFileSync(vsb));
  const directory = mkdtempSync(join(tmpdir(), "gelumpe-mfx-"));
  const path = join(directory, "SYSTEM.VSB");
  return applyPatches(original, patches).then(res => {
    assert.equal(res.ok, true, res.reasons.join(" "));
    writeFileSync(path, res.bytes);
    return { path, allowCode: res.allowCode, remove: () => rmSync(directory, { recursive: true, force: true }) };
  });
}
