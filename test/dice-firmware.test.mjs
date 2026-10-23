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
import { identify } from "../src/firmware.mjs";

// Dice (docs/messungen/2026-10-16-wuerfeln.md).
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/dice.json");
const ALL = read("../data/patches/blech.json").patches.map(p => read(`../${p}`));
const SET = ALL.filter(p => !(p.builds.length === 1 && p.builds[0] === "stock"));
const CODE = 0x18a100;              // file offset of 0xC018A000
const CODE_END = 0x18a900;          // 0xC018A800
// the replaced word: the first instruction of the mode keys' key function (PART ERASE, TRIGGER, SEQUENCER, KEYBOARD, CHORD, STEP JUMP)
const WORD = [0x6ffdc, 0xc006fedc];

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

test("the dice patch has the v1 format, says what it replaces and declares its RAM", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "dice");
  assert.deepEqual(PATCH.builds, ["hacktribe", "stock"]);
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
    assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  }
  assert.deepEqual(PATCH.ram.map(r => [r.at, r.length]), [["0xC018AF00", 64]]);
});

test("it is our code plus one replaced word that branches into it, and the hook is declared", () => {
  assert.equal(PATCH.changes.length, 2);
  const [code, word] = PATCH.changes;
  const n = fromHex(code.bytes).length;
  assert.ok(code.file === CODE && code.file + n <= CODE_END, `${n} bytes`);
  assert.equal(word.file, WORD[0]);
  const w = Buffer.from(fromHex(word.bytes)).readUInt32LE(0);
  assert.equal(w >>> 24, 0xea, "the key function branches");
  const target = WORD[1] + 8 + (((w & 0xffffff) << 8) >> 8) * 4;
  assert.ok(target >= 0xc018a000 && target < 0xc018a000 + n, "it goes into our code");
  assert.deepEqual(PATCH.hooks.map(h => h.site), ["0xC006FEDC"]);
  assert.equal(PATCH.hooks[0].chain, "mode-key");
  const res = checkHooks([PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("no start phase: the key function runs on a key, never before the main screen", () => {
  assert.deepEqual(PATCH.startPhase, []);
});

test("it sits clear of every other patch of the set and is accepted with all of them", () => {
  const span = (c, id) => [c.file, c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length), id];
  const mine = PATCH.changes.map(c => span(c, PATCH.id));
  const others = SET.filter(p => p.id !== PATCH.id).flatMap(p => (p.changes ?? []).filter(c => typeof c.file === "number").map(c => span(c, p.id)));
  for (const [a, b] of mine) for (const [c, d, id] of others) assert.ok(b <= c || d <= a, `dice and ${id} overlap at 0x${Math.max(a, c).toString(16)}`);
  const res = checkHooks(SET);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("the setting word is the first word of the state, the way a menu page will find it", () => {
  const builder = readFileSync(new URL("../tools/patch/dice.py", import.meta.url), "utf8");
  assert.match(builder, /^DC_SETTING = STATE \+ S_SETTING/m);
  assert.match(builder, /^S_SETTING, S_RNG, S_POOLN, S_POOL = 0, 4, 8, 0x10/m);
  assert.match(builder, /^STATE = 0xC018AF00/m);
});

test("the assembler and the patch builder agree with the committed patch", { skip }, () => {
  const run = spawnSync(python(), [join(dir, "patch/dice.py"), "--vsb", vsb], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/dice.py --vsb SYSTEM.VSB --out data/patches/dice.json");
});

test("applied to the own firmware it changes only what it names", { skip }, async () => {
  const original = new Uint8Array(readFileSync(vsb));
  const res = await applyPatches(original, [PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal((await identify(res.bytes)).known, true);
  const named = PATCH.changes.map(c => [c.file, c.bytes.length / 2]);
  for (let i = 0; i < original.length; i++) {
    if (original[i] !== res.bytes[i]) assert.ok(named.some(([at, n]) => i >= at && i < at + n), `0x${i.toString(16)} changed without being named`);
  }
  const all = await applyPatches(original, SET);
  assert.equal(all.ok, true, all.reasons.join(" "));
});

test("applied to Korg's own firmware it goes in as well, on the same word, and builds the same patch", { skip: stock ? false : "E2_STOCK_VSB not set" }, async () => {
  const original = new Uint8Array(readFileSync(stock));
  const res = await applyPatches(original, [PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal(Buffer.from(res.bytes).readUInt32LE(WORD[0]) >>> 24, 0xea, "the key function branches");
  const run = spawnSync(python(), [join(dir, "patch/dice.py"), "--vsb", stock], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "the same bytes for Korg's build (the scale table and the key function are where the builder expects them)");
});

describe("the dice in the emulator", { concurrency: slots }, () => {
  for (const [label, path, build, skipWhy] of [["Hacktribe", vsb, "hacktribe", skipEmu], ["Korg's own firmware", stock, "stock", !stock ? "E2_STOCK_VSB not set" : !local ? "emulation only runs in test:local or test:emu" : false]]) {
    test(`emulate:2026-10-16/dice, the whole BLECH set on ${label}: roll, scale, length, play, LEDs, keys, screens and stock cases`, { skip: skipWhy }, async () => {
      const original = new Uint8Array(readFileSync(path));
      const res = await applyPatches(original, selectFor(ALL, build).patches);
      assert.equal(res.ok, true, res.reasons.join(" "));
      const directory = mkdtempSync(join(tmpdir(), "gelumpe-dice-"));
      const file = join(directory, "SYSTEM.VSB");
      writeFileSync(file, res.bytes);
      try {
        const run = await exec(python(), [join(dir, "emu/dice_cases.py"), "cases", "--patched", file, ...flashArgs], { timeout: 1_800_000, maxBuffer: 4 * 1024 * 1024 });
        assert.ifError(run.error);
        const report = JSON.parse(run.stdout);
        assert.deepEqual(report.filter(c => !c.ok), []);
        for (const id of ["combo_rolls_the_selected_part", "rolls_only_the_selected_part", "nothing_written_to_flash", "notes_stay_in_key_and_scale", "length_bounds_the_roll", "last_step_bounds_the_roll",
          "part_plays_what_was_written", "roll_while_playing_leaves_no_stuck_note", "pad_leds_follow_the_roll", "other_keys_are_the_firmwares", "no_roll_in_menu_or_window", "stock_without_the_patch", "setting_on_again"]) {
          assert.ok(report.some(c => c.id === `dice:${id}`), id);
        }
        assert.equal(run.status, 0);
      } finally {
        rmSync(directory, { recursive: true, force: true });
      }
    });
  }
});
