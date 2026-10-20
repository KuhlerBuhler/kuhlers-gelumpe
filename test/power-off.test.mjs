import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { run as exec, slots } from "./support/spawn.mjs";
import { existsSync, readFileSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { applyPatches, selectFor, PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { CHAINS } from "../data/hooks.mjs";
import { identify } from "../src/firmware.mjs";

// Blechy at switch-off (docs/messungen/2026-10-15-blechy-power-off.md): Blechy waves, then the picture goes out like a tube, instead of the firmware's box.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const PATCH = read("data/patches/power-off.json");
const SET = read("data/patches/blech.json");
const CODE = 0x1a5900;               // file offset of 0xC01A5800
const CODE_END = 0x1a5cf0;           // 0xC01A5BF0, the word that says the sequence runs
const FRAME = 0x1a4d00;              // 0xC01A4C00, the picture
const FRAME_END = 0x1a5100;          // 0xC01A5000, where MFX 2 starts
const WAIT_CALL = 0x38b74;           // file offset of 0xC0038A74, the call of the wait function in the power-off handler

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const stock = process.env.E2_STOCK_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !vsb ? "E2_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);
const flashArgs = flash.length ? ["--flash", ...flash] : [];

test("the power-off patch has the v1 format, says what it replaces, copies nothing and runs nothing at start", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "power-off");
  assert.deepEqual(PATCH.builds, ["hacktribe", "stock"]);
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
    assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  }
  assert.equal(PATCH.startPhase, undefined, "the hook sits in the power-off handler, not in the start phase");
});

test("it is our code, our picture and one hooked word: a branch with link into the code, in a free run clear of the other patches", () => {
  assert.equal(PATCH.changes.length, 3);
  const [code, frame, hook] = PATCH.changes;
  const n = fromHex(code.bytes).length;
  assert.equal(code.file, CODE);
  assert.ok(code.file + n <= CODE_END, `${n} bytes of code`);
  assert.equal(frame.file, FRAME);
  assert.equal(fromHex(frame.bytes).length, 1024, "a whole display");
  assert.ok(frame.file + 1024 <= FRAME_END);
  assert.ok(fromHex(frame.bytes).some(b => b), "the picture is not blank");
  assert.equal(hook.file, WAIT_CALL);
  const word = Buffer.from(fromHex(hook.bytes)).readUInt32LE(0);
  assert.equal(word >>> 24, 0xeb, "branch with link");
  const target = 0xc0038a74 + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
  assert.ok(target >= 0xc01a5800 && target < 0xc01a5800 + n, "the call goes into our code");
  for (const build of ["hacktribe", "stock"]) {
    const selected = selectFor(SET.patches.map(read), build);
    assert.deepEqual(selected.reasons, [], build);
    const spans = selected.patches.flatMap(patch => patch.changes ?? []).filter(c => c.file >= 0x1a0000 && c.file < 0x200100).map(c => [c.file, c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length)]).sort((a, b) => a[0] - b[0]);
    for (let i = 1; i < spans.length; i++) assert.ok(spans[i][0] >= spans[i - 1][1], `${build}: 0x${spans[i][0].toString(16)} overlaps the span before it`);
  }
});

test("the hook is declared on its own chain and the chain knows the site", () => {
  assert.equal(PATCH.hooks.length, 1);
  assert.equal(PATCH.hooks[0].site, "0xC0038A74");
  assert.equal(PATCH.hooks[0].chain, "power-off");
  assert.equal(PATCH.hooks[0].swallow, false);
  assert.deepEqual(CHAINS["power-off"].flatMap(stage => stage.sites), [0xc0038a74]);
});

test("the BLECH set lists it after the theme", () => {
  assert.ok(SET.patches.indexOf("data/patches/power-off.json") > SET.patches.indexOf("data/patches/blech-theme.json"));
});

test("the assembler and the patch builder agree with the committed patch", { skip }, () => {
  const run = spawnSync(python(), [join(dir, "patch/power_off.py"), "--vsb", vsb], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/power_off.py --vsb SYSTEM.VSB --out data/patches/power-off.json");
});

test("applied to the own firmware it changes only what it names and goes with the whole BLECH set", { skip }, async () => {
  const original = new Uint8Array(readFileSync(vsb));
  const res = await applyPatches(original, [PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal((await identify(res.bytes)).known, true);
  const named = PATCH.changes.map(c => [c.file, c.bytes.length / 2]);
  for (let i = 0; i < original.length; i++) {
    if (original[i] !== res.bytes[i]) assert.ok(named.some(([at, n]) => i >= at && i < at + n), `0x${i.toString(16)} changed without being named`);
  }
  assert.equal(res.allowCode.length, 0, "nothing of it runs at start");
  const whole = await applyPatches(original, SET.patches.map(read));
  assert.equal(whole.ok, true, whole.reasons.join(" "));
  assert.ok(whole.spans.some(s => s.patch === "power-off"));
});

test("applied to Korg's own firmware (E2_STOCK_VSB) it goes in as well, with the hooked word where it is on Hacktribe", { skip: stock ? false : "E2_STOCK_VSB not set" }, async () => {
  const original = new Uint8Array(readFileSync(stock));
  const res = await applyPatches(original, [PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal(Buffer.from(res.bytes).readUInt32LE(WAIT_CALL) >>> 24, 0xeb);
});

describe("the power-off picture in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-10-15/blechy-power-off, picture, kill switch and an unchanged save on Hacktribe", { skip: skipEmu }, async () => {
    const patched = await patchedCopy(vsb);
    try {
      const report = await cases(patched.path);
      for (const id of ["picture_shown", "stock_shows_the_box", "switch_off_time", "save_identical", "save_identical_after_edit", "picture_shown_after_edit", "exit_held_is_stock", "mains_power_ignores_the_key"]) {
        assert.ok(report.checks.some(c => c.id === `power_off:${id}`), id);
      }
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-15/blechy-power-off, the same on Korg's own firmware", { skip: skipEmu || (stock ? false : "E2_STOCK_VSB not set") }, async () => {
    const patched = await patchedCopy(stock);
    try {
      const report = await cases(patched.path);
      assert.equal(report.checks.length, 9);
    } finally {
      patched.remove();
    }
  });
});

async function cases(path) {
  const run = await exec(python(), [join(dir, "emu/power_off_cases.py"), "cases", "--patched", path, ...flashArgs], { timeout: 600_000, maxBuffer: 4 * 1024 * 1024 });
  assert.ifError(run.error);
  const report = JSON.parse(run.stdout);
  assert.deepEqual(report.checks.filter(c => !c.ok), []);
  assert.equal(run.status, 0);
  return report;
}

function patchedCopy(source) {
  const original = new Uint8Array(readFileSync(source));
  const directory = mkdtempSync(join(tmpdir(), "gelumpe-power-off-"));
  const path = join(directory, "SYSTEM.VSB");
  return applyPatches(original, SET.patches.map(read)).then(res => {
    assert.equal(res.ok, true, res.reasons.join(" "));
    writeFileSync(path, res.bytes);
    return { path, remove: () => rmSync(directory, { recursive: true, force: true }) };
  });
}
