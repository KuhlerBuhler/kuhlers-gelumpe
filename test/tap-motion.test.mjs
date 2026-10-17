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

// TAP motion (docs/ideen/39-automationen-tap.md, docs/messungen/2026-10-15-tap-motion-patch.md).
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/tap-motion.json");
const SET = read("../data/patches/blech.json").patches.map(p => read(`../${p}`)).filter(p => !(p.builds.length === 1 && p.builds[0] === "stock"));
const CODE = 0x188100;              // file offset of 0xC0188000
const CODE_END = 0x188900;          // 0xC0188800
// the replaced words: the key handler's load before the tap tempo call, the TAP LED's beat flash, the LED manager's tick
const WORDS = [[0x42cc0 - 0x0 + 0x100, 0xc0042cc0], [0x881e0 + 0x100, 0xc00881e0], [0x87740 + 0x100, 0xc0087740]];
const FRAME = [0x836f0 + 0x100, 0xc00836f0];       // the frame's call: a bl that calls the code, which makes the original call first

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !vsb ? "E2_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);
const flashArgs = flash.length ? ["--flash", ...flash] : [];

test("TAP motion has the v1 format, says what it replaces and declares its RAM", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "tap-motion");
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
    assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  }
  assert.deepEqual(PATCH.ram.map(r => [r.at, r.length]), [["0xC0188F00", 64]]);
});

test("it is our code plus three replaced words branching into the code and a call into it, and every hook is declared", () => {
  assert.equal(PATCH.changes.length, 2 + WORDS.length);
  const [code, ...rest] = PATCH.changes;
  const words = rest.slice(0, WORDS.length);
  const call = rest[WORDS.length];
  assert.equal(call.file, FRAME[0]);
  const bl = Buffer.from(fromHex(call.bytes)).readUInt32LE(0);
  assert.equal(bl >>> 24, 0xeb, "the frame's call stays a call");
  const n = fromHex(code.bytes).length;
  assert.ok(code.file === CODE && code.file + n <= CODE_END, `${n} bytes`);
  for (const [i, [file, address]] of WORDS.entries()) {
    assert.equal(words[i].file, file);
    const word = Buffer.from(fromHex(words[i].bytes)).readUInt32LE(0);
    assert.equal(word >>> 24, 0xea, `0x${address.toString(16)} branches`);
    const target = address + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    assert.ok(target >= 0xc0188000 && target < 0xc0188000 + n, `0x${address.toString(16)} goes into our code`);
  }
  const blTarget = FRAME[1] + 8 + (((bl & 0xffffff) << 8) >> 8) * 4;
  assert.ok(blTarget >= 0xc0188000 && blTarget < 0xc0188000 + n, "the frame's call goes into our code");
  assert.deepEqual(PATCH.hooks.map(h => h.site).sort(), [...WORDS, FRAME].map(([, a]) => `0x${a.toString(16).toUpperCase()}`).sort());
  const res = checkHooks([PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("the hooks behind the start name the bytes that run before the main screen, and nothing else of it does", () => {
  const spans = PATCH.startPhase.map(s => [s.file, s.length]);
  assert.ok(spans.some(([file]) => file === WORDS[1][0]) && spans.some(([file]) => file === WORDS[2][0]), "the beat flash and the LED tick run before the main screen");
  assert.ok(!spans.some(([file]) => file === WORDS[0][0]), "the key handler runs only on a key");
  for (const s of PATCH.startPhase) assert.ok(s.why.length > 20, "every span says why");
});

test("it sits clear of every other patch of the set and is accepted with all of them", () => {
  const span = (c, id) => [c.file, c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length), id];
  const mine = PATCH.changes.map(c => span(c, PATCH.id));
  const others = SET.filter(p => p.id !== PATCH.id).flatMap(p => p.changes.filter(c => typeof c.file === "number").map(c => span(c, p.id)));
  for (const [a, b] of mine) for (const [c, d, id] of others) assert.ok(b <= c || d <= a, `tap-motion and ${id} overlap at 0x${Math.max(a, c).toString(16)}`);
  const res = checkHooks(SET);
  assert.equal(res.ok, true, res.reasons.join(" "));
});

test("the BLECH menu writes the word TAP motion reads, as bit 3 of the settings flags", () => {
  const menu = readFileSync(new URL("../tools/patch/script_menu.s", import.meta.url), "utf8");
  const builder = readFileSync(new URL("../tools/patch/tap_motion.py", import.meta.url), "utf8");
  const word = menu.match(/^\.equ TM_SETTING, (0x[0-9A-Fa-f]+)/m);
  assert.ok(word, "script_menu.s names TM_SETTING");
  const state = builder.match(/^STATE = (0x[0-9A-Fa-f]+)/m)[1];
  assert.equal(parseInt(word[1], 16), parseInt(state, 16), "STATE + S_SETTING (0) of tools/patch/tap_motion.py");
  assert.match(menu, /orreq r0, r0, #8\n/, "OFF is bit 3 of the flags");
});

test("the assembler and the patch builder agree with the committed patch", { skip }, () => {
  const run = spawnSync(python(), [join(dir, "patch/tap_motion.py"), "--vsb", vsb], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/tap_motion.py --vsb SYSTEM.VSB --out data/patches/tap-motion.json");
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

describe("TAP motion in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-10-15/tap-motion-patch, the whole BLECH set: toggle, memory, LED, stock, SHIFT, REC, pattern, Master FX and app cases", { skip: skipEmu }, async () => {
    const original = new Uint8Array(readFileSync(vsb));
    const res = await applyPatches(original, SET);
    assert.equal(res.ok, true, res.reasons.join(" "));
    const directory = mkdtempSync(join(tmpdir(), "gelumpe-tapmotion-"));
    const path = join(directory, "SYSTEM.VSB");
    writeFileSync(path, res.bytes);
    try {
      const run = await exec(python(), [join(dir, "emu/tap_motion_cases.py"), "cases", "--patched", path, ...flashArgs], { timeout: 1_800_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.filter(c => !c.ok), []);
      for (const id of ["on_in_the_middle_of_the_bar", "off_in_the_middle_of_the_bar", "tap_tempo_is_gone", "trigger_hold_comes_back", "led_follows_the_selected_part", "stock_without_the_patch",
        "shift_tap_is_the_bpm_page", "rec_with_the_motion_off", "write_saves_the_state_at_write_time", "mfx_off_at_once", "mfx_pad_let_go", "app_owns_tap"]) {
        assert.ok(report.some(c => c.id === `tapmotion:${id}`), id);
      }
      assert.equal(run.status, 0);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
