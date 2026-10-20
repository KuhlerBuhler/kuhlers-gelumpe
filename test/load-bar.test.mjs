import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { run as exec, slots } from "./support/spawn.mjs";
import { existsSync, readFileSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { applyPatches, PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { checkHooks } from "../src/hooks.mjs";
import { identify } from "../src/firmware.mjs";

// The loading animation (docs/ideen/41-startbild-ausbauen.md, entwuerfe/design-1.3/geraet).
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/load-bar.json");
const SPLASH_DATA = read("../assets/blechy/splash.json");
const OTHERS = ["splash-editor", "mfx-switch", "pattern-switch", "script-runtime", "blechtribe", "blech-theme"].map(id => read(`../data/patches/${id}.json`));
const CODE = 0x181100;               // file offset of 0xC0181000
const CODE_END = 0x182000;           // 0xC0181F00, where the run time state begins
const LOOK = 0x183a00;               // file offset of 0xC0183900: the rest of the look's code
const LOOK_END = 0x184100;           // 0xC0184000
const ART = 0x1a3e00;                // file offset of 0xC01A3D00: assets/blechy/loading.bin
const ART_BYTES = readFileSync(new URL("../assets/blechy/loading.bin", import.meta.url));
// the replaced words: the stat call, the loader's text update, the loader call, the frame function's flush, the display send's page compare
const WORDS = [[0x2af60, 0xeb, 0xc002ae60], [0x367d4, 0xeb, 0xc00366d4], [0x38e60, 0xeb, 0xc0038d60], [0x8380c, 0xea, 0xc008370c], [0x16184, 0xeb, 0xc0016084]];

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !vsb ? "E2_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);
const flashArgs = flash.length ? ["--flash", ...flash] : [];

test("the loading bar has the v1 format, says what it replaces and names what runs at start", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "load-bar");
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
    assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  }
  assert.equal(PATCH.startPhase.length, 7);
  for (const span of PATCH.startPhase) {
    assert.ok(span.why.length > 20);
    assert.ok(PATCH.changes.some(c => span.file >= c.file && span.file + span.length <= c.file + c.bytes.length / 2), `0x${span.file.toString(16)} is not written by the patch`);
  }
});

test("it is our code in two places, the animation's pictures, the card picture and five replaced words, each a branch into the code, and every hook is declared", () => {
  assert.equal(PATCH.changes.length, 4 + WORDS.length);
  const [code, art, card, look, ...words] = PATCH.changes;
  const n = fromHex(code.bytes).length;
  assert.ok(code.file === CODE && code.file + n <= CODE_END, `${n} bytes`);
  assert.ok(look.file === LOOK && look.file + fromHex(look.bytes).length <= LOOK_END, "the look's code");
  assert.equal(art.file, ART);
  assert.deepEqual(Buffer.from(fromHex(art.bytes)), ART_BYTES, "assets/blechy/loading.bin as it is");
  assert.equal(card.file, (ART + ART_BYTES.length + 3) & ~3, "the card picture right behind the animation's pictures");
  const runs = fromHex(card.bytes);
  let size = 0;
  for (let i = 0; i < runs.length; i += 2) size += runs[i];
  assert.equal(size, 2048, "the two card pictures' runs fill a frame each");
  for (const [i, [file, opcode, address]] of WORDS.entries()) {
    assert.equal(words[i].file, file);
    const word = Buffer.from(fromHex(words[i].bytes)).readUInt32LE(0);
    assert.equal(word >>> 24, opcode, `0x${address.toString(16)} branches${opcode === 0xeb ? " and links" : ""}`);
    const target = address + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    assert.ok(target >= 0xc0181000 && target < 0xc0181000 + n, `0x${address.toString(16)} goes into our code`);
  }
  assert.deepEqual(PATCH.hooks.map(h => h.site).sort(), WORDS.map(([, , a]) => `0x${a.toString(16).toUpperCase()}`).sort());
  const res = checkHooks([PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("it sits clear of every other patch of the set and is accepted with all of them", async () => {
  const spans = [...OTHERS, PATCH].flatMap(p => p.changes.map(c => [c.file, c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length), p.id])).sort((a, b) => a[0] - b[0]);
  for (let i = 1; i < spans.length; i++) assert.ok(spans[i][0] >= spans[i - 1][1], `${spans[i - 1][2]} and ${spans[i][2]} overlap`);
  const res = checkHooks([...OTHERS, PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("the assembler and the patch builder agree with the committed patch", { skip }, () => {
  const run = spawnSync(python(), [join(dir, "patch/load_bar.py"), "--vsb", vsb], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/load_bar.py --vsb SYSTEM.VSB --out data/patches/load-bar.json");
});

test("applied to the own firmware it changes only what it names, alone and with the other patches", { skip }, async () => {
  const original = new Uint8Array(readFileSync(vsb));
  const res = await applyPatches(original, [PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal((await identify(res.bytes)).known, true);
  const named = PATCH.changes.map(c => [c.file, c.bytes.length / 2]);
  for (let i = 0; i < original.length; i++) {
    if (original[i] !== res.bytes[i]) assert.ok(named.some(([at, n]) => i >= at && i < at + n), `0x${i.toString(16)} changed without being named`);
  }
  assert.equal(res.allowCode.length, 7, "the spans the patch asks to run at start");
  const all = await applyPatches(original, [...OTHERS, PATCH, SPLASH_DATA]);
  assert.equal(all.ok, true, all.reasons.join(" "));
});

describe("the loading bar in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-10-15/ladebalken, the animation, the percent, the finale, the stock cases and the rescue paths", { skip: skipEmu }, async () => {
    const patched = await patchedCopy([PATCH, SPLASH_DATA]);
    try {
      const run = await exec(python(), [join(dir, "emu/loadbar_cases.py"), "cases", "--patched", patched.path, ...flashArgs], { timeout: 1_800_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.filter(c => !c.ok), []);
      for (const id of ["overlay_frames_are_the_animation", "percent_counts_up", "finale_from_95", "at_most_20_pictures_a_second", "display_stays_dark",
        "loader_is_no_slower", "main_screen_is_clean", "no_card_is_stock", "exit_held_is_stock", "no_sample_file_is_stock", "panel_update_untouched",
        "start_mode_1_untouched", "own_image_then_the_animation", "look_needs_the_menu"]) {
        assert.ok(report.some(c => c.id === `loadbar:${id}`), id);
      }
      assert.equal(run.status, 0);
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-15/ladebalken, the export check passes with the start spans the patch names", { skip: skipEmu }, async () => {
    const patched = await patchedCopy([PATCH, SPLASH_DATA]);
    try {
      const args = ["--base", vsb, "--patched", patched.path, ...flashArgs, "--allow", "0xf9954:1024", ...patched.allowCode.flatMap(([at, n]) => ["--allow-code", `0x${at.toString(16)}:${n}`])];
      const run = await exec(python(), [join(dir, "emu/check.py"), ...args], { timeout: 1_800_000, maxBuffer: 8 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.checks.filter(c => !c.ok), []);
      assert.ok(report.checks.some(c => c.id === "loadbar:overlay_frames_are_the_animation"), "the patch's own cases ran");
      assert.equal(run.status, 0);
      const bare = await exec(python(), [join(dir, "emu/check.py"), "--base", vsb, "--patched", patched.path, ...flashArgs, "--allow", "0xf9954:1024"], { timeout: 1_800_000, maxBuffer: 8 * 1024 * 1024 });
      assert.equal(bare.status, 1, "without the spans the hooks are changes in the start code");
    } finally {
      patched.remove();
    }
  });
});

function patchedCopy(patches) {
  const original = new Uint8Array(readFileSync(vsb));
  const directory = mkdtempSync(join(tmpdir(), "gelumpe-loadbar-"));
  const path = join(directory, "SYSTEM.VSB");
  return applyPatches(original, patches).then(res => {
    assert.equal(res.ok, true, res.reasons.join(" "));
    writeFileSync(path, res.bytes);
    return { path, allowCode: res.allowCode, remove: () => rmSync(directory, { recursive: true, force: true }) };
  });
}
