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

// Note assistant (docs/messungen/2026-10-15-note-assistant.md).
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/note-assistant.json");
const SET = read("../data/patches/blech.json").patches.map(p => read(`../${p}`)).filter(p => !(p.builds.length === 1 && p.builds[0] === "stock"));
const CODE = 0x189100;              // file offset of 0xC0189000
const CODE_END = 0x189900;          // 0xC0189800
// the replaced words: the first instruction of the keyboard's pad event, of the firmware's pad light, and the last one of the LED manager's tick
const WORDS = [[0x44c3c, 0xc0044b3c], [0x8880c, 0xc008870c], [0x878d4, 0xc00877d4]];

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

test("the note assistant has the v1 format, says what it replaces and declares its RAM", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "note-assistant");
  assert.deepEqual(PATCH.builds, ["hacktribe", "stock"]);
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
    assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  }
  assert.deepEqual(PATCH.ram.map(r => [r.at, r.length]), [["0xC0189F00", 64]]);
});

test("it is our code plus three replaced words, each branching into the code, and every hook is declared", () => {
  assert.equal(PATCH.changes.length, 1 + WORDS.length);
  const [code, ...words] = PATCH.changes;
  const n = fromHex(code.bytes).length;
  assert.ok(code.file === CODE && code.file + n <= CODE_END, `${n} bytes`);
  for (const [i, [file, address]] of WORDS.entries()) {
    assert.equal(words[i].file, file);
    const word = Buffer.from(fromHex(words[i].bytes)).readUInt32LE(0);
    assert.equal(word >>> 24, 0xea, `0x${address.toString(16)} branches`);
    const target = address + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    assert.ok(target >= 0xc0189000 && target < 0xc0189000 + n, `0x${address.toString(16)} goes into our code`);
  }
  assert.deepEqual(PATCH.hooks.map(h => h.site).sort(), WORDS.map(([, a]) => `0x${a.toString(16).toUpperCase()}`).sort());
  assert.ok(PATCH.hooks.every(h => h.swallow === false), "no hook keeps the firmware from its own code");
  const res = checkHooks([PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("only the LED tick's hook runs before the main screen, and the patch names it and its code", () => {
  const spans = PATCH.startPhase.map(s => [s.file, s.length]);
  assert.ok(spans.some(([file]) => file === WORDS[2][0]), "the LED tick runs before the main screen");
  assert.ok(!spans.some(([file]) => file === WORDS[0][0] || file === WORDS[1][0]), "the pad event and the pad light run only on a pad or a note");
  for (const s of PATCH.startPhase) assert.ok(s.why.length > 20, "every span says why");
});

test("it sits clear of every other patch of the set and is accepted with all of them", () => {
  const span = (c, id) => [c.file, c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length), id];
  const mine = PATCH.changes.map(c => span(c, PATCH.id));
  const others = SET.filter(p => p.id !== PATCH.id).flatMap(p => p.changes.filter(c => typeof c.file === "number").map(c => span(c, p.id)));
  for (const [a, b] of mine) for (const [c, d, id] of others) assert.ok(b <= c || d <= a, `note-assistant and ${id} overlap at 0x${Math.max(a, c).toString(16)}`);
  const res = checkHooks(SET);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("the BLECH menu writes the word the note assistant reads, as bit 4 of the settings flags", () => {
  const builder = readFileSync(new URL("../tools/patch/note_assist.py", import.meta.url), "utf8");
  const menu = readFileSync(new URL("../tools/patch/script_menu.s", import.meta.url), "utf8");
  assert.match(builder, /^NA_SETTING = STATE \+ S_SETTING/m);
  assert.match(builder, /^S_SETTING, S_SINCE, S_NOTE, S_PAD, S_PARTPAD, S_FADE, S_LEVEL = 0, 4, 8, 0xC, 0x10, 0x14, 0x20/m);
  assert.match(builder, /^FLAG_OFF_BIT = 4 /m);
  const word = menu.match(/^\.equ NA_SETTING, (0x[0-9A-Fa-f]+)/m);
  assert.ok(word, "script_menu.s names NA_SETTING");
  const state = builder.match(/^STATE = (0x[0-9A-Fa-f]+)/m)[1];
  assert.equal(parseInt(word[1], 16), parseInt(state, 16), "STATE + S_SETTING (0) of tools/patch/note_assist.py");
  assert.match(menu, /bit 4 NOTE ASSIST is OFF/);
  assert.match(menu, /orreq r0, r0, #16\n\s+str r0, \[r7, #12\]/, "OFF is bit 4 of the flags");
});

test("the assembler and the patch builder agree with the committed patch", { skip }, () => {
  const run = spawnSync(python(), [join(dir, "patch/note_assist.py"), "--vsb", vsb], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/note_assist.py --vsb SYSTEM.VSB --out data/patches/note-assistant.json");
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

test("applied to Korg's own firmware it goes in as well, on the same words", { skip: stock ? false : "E2_STOCK_VSB not set" }, async () => {
  const original = new Uint8Array(readFileSync(stock));
  const res = await applyPatches(original, [PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  const word = at => Buffer.from(res.bytes).readUInt32LE(at);
  for (const [file] of WORDS) assert.equal(word(file) >>> 24, 0xea, `0x${file.toString(16)} branches`);
});

describe("the note assistant in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-10-15/note-assistant, the whole BLECH set: layout, hints, timing, new note, firmware wins, modes, stock, values and lock cases", { skip: skipEmu }, async () => {
    const original = new Uint8Array(readFileSync(vsb));
    const res = await applyPatches(original, SET);
    assert.equal(res.ok, true, res.reasons.join(" "));
    const directory = mkdtempSync(join(tmpdir(), "gelumpe-noteassist-"));
    const path = join(directory, "SYSTEM.VSB");
    writeFileSync(path, res.bytes);
    try {
      const run = await exec(python(), [join(dir, "emu/note_assist_cases.py"), "cases", "--patched", path, ...flashArgs], { timeout: 1_800_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.filter(c => !c.ok), []);
      for (const id of ["layout_is_the_key_and_scale", "fitting_pads_show_the_hint", "other_pads_stay_dark", "hints_come_with_the_next_tick", "hints_end_after_a_second_and_a_half", "new_note_replaces_the_hints",
        "held_pad_keeps_the_firmwares_light", "blue_of_the_part_stays", "sequencer_light_wins", "no_hint_in_other_pad_modes", "no_hint_in_the_menu", "octave_shift_ends_the_hints",
        "stock_without_the_patch", "setting_off_gives_the_leds_back", "firmware_pad_values", "led_lock_keeps_the_pads"]) {
        assert.ok(report.some(c => c.id === `noteassist:${id}`), id);
      }
      assert.equal(run.status, 0);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
