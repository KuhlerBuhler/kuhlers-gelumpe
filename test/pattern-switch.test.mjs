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

// The pattern switch (docs/ideen/46-patternwechsel-bestaetigung.md).
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/pattern-switch.json");
const OTHERS = ["splash-editor", "mfx-switch", "script-runtime", "blechtribe", "blech-theme"].map(id => read(`../data/patches/${id}.json`));
const CODE = 0x180100;              // file offset of 0xC0180000
const CODE_END = 0x180d00;          // 0xC0180C00
// the replaced words: wheel branch, pad and MIDI first instruction, MENU and EXIT slots (pointers), sequence end call, STOP first instruction, label load
const WORDS = [[0x6523c, 0xea, 0xc006513c], [0x6eee4, 0xea, 0xc006ede4], [0x6ef00, 0xea, 0xc006ee00], [0xe35b0, null, 0xc00e34b0],
  [0xe35a0, null, 0xc00e34a0], [0x5f2c4, 0xeb, 0xc005f1c4], [0x81c5c, 0xea, 0xc0081b5c], [0x86ec4, 0xeb, 0xc0086dc4], [0x81f18, 0xea, 0xc0081e18]];

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !vsb ? "E2_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);
const flashArgs = flash.length ? ["--flash", ...flash] : [];

test("the pattern switch has the v1 format, says what it replaces and runs only its stopped sync hook at start", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "pattern-switch");
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
    assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  }
  // the stopped sync observer (0xC0081E18) runs from the start on; every other hook sits behind the start and the rescue paths
  assert.deepEqual(PATCH.startPhase.map(s => s.file), [0x81f18, 0x1806a0]);
  assert.ok(PATCH.startPhase.every(s => s.why.length > 20));
});

test("it is our code plus nine replaced words, each leading into the code, and every hook is declared", () => {
  assert.equal(PATCH.changes.length, 1 + WORDS.length);
  const [code, ...words] = PATCH.changes;
  const n = fromHex(code.bytes).length;
  assert.ok(code.file === CODE && code.file + n <= CODE_END, `${n} bytes`);
  for (const [i, [file, opcode, address]] of WORDS.entries()) {
    assert.equal(words[i].file, file);
    const word = Buffer.from(fromHex(words[i].bytes)).readUInt32LE(0);
    const target = opcode === null ? word : address + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    if (opcode !== null) assert.equal(word >>> 24, opcode, `0x${address.toString(16)} branches${opcode === 0xeb ? " and links" : ""}`);
    assert.ok(target >= 0xc0180000 && target < 0xc0180000 + n, `0x${address.toString(16)} goes into our code`);
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
  const run = spawnSync(python(), [join(dir, "patch/pattern_switch.py"), "--vsb", vsb], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/pattern_switch.py --vsb SYSTEM.VSB --out data/patches/pattern-switch.json");
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
  assert.equal(res.allowCode.length, 0, "no start span");
  const all = await applyPatches(original, [...OTHERS, PATCH]);
  assert.equal(all.ok, true, all.reasons.join(" "));
});

describe("the pattern switch in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-10-15/patternwechsel, browse, confirm, EXIT, STOP, chain and the stock cases", { skip: skipEmu }, async () => {
    const patched = await patchedCopy([PATCH]);
    try {
      const run = await exec(python(), [join(dir, "emu/pswitch_cases.py"), "cases", "--patched", patched.path, ...flashArgs], { timeout: 1_800_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.filter(c => !c.ok), []);
      for (const id of ["browse_is_silent", "browse_label_is_view", "confirm_switches_at_sequence_end", "exit_takes_browse_back", "exit_takes_confirmation_back", "stopped_is_stock",
        "stop_drops_browse", "chain_runs_while_browsing", "pad_wins_over_browse", "exit_held_is_stock", "no_card_is_stock", "setting_off_is_stock"]) {
        assert.ok(report.some(c => c.id === `pswitch:${id}`), id);
      }
      assert.equal(run.status, 0);
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-15/patternwechsel, with MFX 2 in the copy browsing leaves the effect alone and the change brings MFX 2 for the new pattern", { skip: skipEmu }, async () => {
    const patched = await patchedCopy([read("../data/patches/mfx-switch.json"), PATCH]);
    try {
      const run = await exec(python(), [join(dir, "emu/pswitch_cases.py"), "cases", "--patched", patched.path, "--only", "9", ...flashArgs], { timeout: 900_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.filter(c => !c.ok), []);
      assert.ok(report.some(c => c.id === "pswitch:mfx2_combined"));
      assert.equal(run.status, 0);
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-15/patternwechsel, the export check passes with the patch alone and starts nowhere before the rescue paths", { skip: skipEmu }, async () => {
    const patched = await patchedCopy([PATCH]);
    try {
      const run = await exec(python(), [join(dir, "emu/check.py"), "--base", vsb, "--patched", patched.path, ...flashArgs], { timeout: 1_800_000, maxBuffer: 8 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.checks.filter(c => !c.ok), []);
      assert.ok(report.checks.some(c => c.id === "pswitch:browse_is_silent"), "the patch's own cases ran");
      assert.equal(run.status, 0);
    } finally {
      patched.remove();
    }
  });
});

test("the BLECH menu writes the word the pattern switch reads, and keeps OFF as bit 2 of the settings flags", () => {
  const menu = readFileSync(new URL("../tools/patch/script_menu.s", import.meta.url), "utf8");
  const builder = readFileSync(new URL("../tools/patch/pattern_switch.py", import.meta.url), "utf8");
  const word = menu.match(/^\.equ PS_SETTING, (0x[0-9A-Fa-f]+)/m);
  assert.ok(word, "script_menu.s names PS_SETTING");
  const state = builder.match(/^STATE = (0x[0-9A-Fa-f]+)/m)[1];
  assert.equal(parseInt(word[1], 16), parseInt(state, 16) + 0x10, "STATE + S_SETTING of tools/patch/pattern_switch.py");
  assert.match(menu, /orreq r0, r0, #4\n(?:[^\n]*\n){0,12}?\s+str r0, \[r7, #12\]/, "OFF is bit 2 of the flags");
});

function patchedCopy(patches) {
  const original = new Uint8Array(readFileSync(vsb));
  const directory = mkdtempSync(join(tmpdir(), "gelumpe-pswitch-"));
  const path = join(directory, "SYSTEM.VSB");
  return applyPatches(original, patches).then(res => {
    assert.equal(res.ok, true, res.reasons.join(" "));
    writeFileSync(path, res.bytes);
    return { path, allowCode: res.allowCode, remove: () => rmSync(directory, { recursive: true, force: true }) };
  });
}
