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
import { CHAINS } from "../data/hooks.mjs";

// Hacktribe's oscillators on the empty slots 421 to 496 of Korg's build (docs/messungen/2026-11-08-ht-osc-freie-plaetze.md).
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const PATCH = read("../data/patches/ht-osc.json");
const ALL = read("../data/patches/blech.json").patches.map(p => read(`../${p}`));
const STOCK_SET = selectFor(ALL, "stock").patches;
const CODE = 0x14f100;              // file offset of 0xC014F000
const CODE_END = 0x14fd00;          // 0xC014FC00, the code of beat-eighth
const ENTRIES = 76;
// the replaced words and the condition of the call that replaces each
const SITES = [[0xc004f5a8, 0xe], [0xc004e354, 0xe], [0xc00362a4, 0x0], [0xc0040d64, 0xe], [0xc00997a4, 0xe]];

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const stock = process.env.E2_STOCK_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !stock ? "E2_STOCK_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);
const flashArgs = flash.length ? ["--flash", ...flash] : [];

test("the ht-osc patch has the v1 format, is for Korg's build only, copies nothing and has no setting word", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.id, "ht-osc");
  assert.deepEqual(PATCH.builds, ["stock"]);
  assert.deepEqual(PATCH.notNeededOn, ["hacktribe"], "Hacktribe has the oscillators already; a set skips it there");
  for (const change of PATCH.changes) assert.equal(change.copy, undefined, "nothing of the firmware is copied");
  assert.deepEqual(PATCH.ram, [], "always on: no switch, no setting word");
});

test("five instructions call into our code, which ends before the code of beat-eighth", () => {
  const [code, ...calls] = PATCH.changes;
  const n = fromHex(code.bytes).length;
  assert.ok(code.file === CODE && code.file + n <= CODE_END, `${n} bytes`);
  assert.deepEqual(calls.map(c => 0xc0000000 + c.file - 0x100).sort(), SITES.map(([a]) => a).sort());
  for (const call of calls) {
    const site = 0xc0000000 + call.file - 0x100;
    const word = Buffer.from(fromHex(call.bytes)).readUInt32LE(0);
    assert.equal(word >>> 28, SITES.find(([a]) => a === site)[1], `condition at 0x${site.toString(16)}`);
    assert.equal((word >>> 24) & 0xf, 0xb, `0x${site.toString(16)} is a bl`);
    const to = site + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    assert.ok(to >= 0xc014f000 && to < 0xc014f000 + n, `${site.toString(16)} calls ${to.toString(16)}`);
  }
});

test("the table holds Hacktribe's 76 oscillators in its order and spelling, DSP entries only", () => {
  const code = Buffer.from(fromHex(PATCH.changes[0].bytes));
  const table = code.subarray(code.length - ENTRIES * 32);
  const names = Array.from({ length: ENTRIES }, (_, i) => table.subarray(i * 32, i * 32 + 16).toString("latin1").split("\0")[0]);
  const family = prefix => ["SAW", "SQU", "TRI", "SINE"].map(w => `${prefix}-${w}`);
  assert.deepEqual(names.slice(0, 16), [...family("DUAL"), ...family("OCT"), "CHIP-TRI 1", "CHIP-TRI 2", "CHIP-PULSE", "CHIP-NOISE", ...family("RING")]);
  const x = ["-24", "-12", "-7", "0", "+7", "+12", "+24"];
  assert.deepEqual(names.slice(16, 44), ["SAW", "SQUARE", "TRI", "SINE"].flatMap(w => x.map(s => `X-${w} ${s}`)));
  const vpm = ["0.5", "1", "2", "3", "4", "8", "16", "32"];
  assert.deepEqual(names.slice(44), ["SAW", "SQUARE", "TRI", "SINE"].flatMap(w => vpm.map(s => `VPM-${w} ${s}`)));
  for (let i = 0; i < ENTRIES; i++) assert.ok(table.readUInt16LE(i * 32 + 0x12) < 0x32, `${names[i]} is a DSP entry`);
});

test("its hooks are in the register, its start-phase code is named, and the BLECH set carries it", () => {
  const sites = Object.values(CHAINS).flat().flatMap(stage => stage.sites);
  assert.deepEqual(PATCH.hooks.map(h => Number(h.site)).sort(), SITES.map(([a]) => a).sort());
  for (const hook of PATCH.hooks) assert.ok(CHAINS[hook.chain] && sites.includes(Number(hook.site)), hook.site);
  assert.ok(PATCH.startPhase.some(s => s.file === CODE));
  for (const s of PATCH.startPhase) assert.ok(s.why.length > 20, "every span says why");
  assert.ok(read("../data/patches/blech.json").patches.includes("data/patches/ht-osc.json"));
});

test("it sits clear of every other patch of the stock set and is accepted with all of them", () => {
  const span = (c, id) => [c.file, c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length), id];
  const mine = PATCH.changes.map(c => span(c, PATCH.id));
  const others = STOCK_SET.filter(p => p.id !== PATCH.id).flatMap(p => (p.changes ?? []).filter(c => typeof c.file === "number").map(c => span(c, p.id)));
  for (const [a, b] of mine) for (const [c, d, id] of others) assert.ok(b <= c || d <= a, `ht-osc and ${id} overlap at 0x${Math.max(a, c).toString(16)}`);
  const res = checkHooks(STOCK_SET);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.deepEqual(checkRam(STOCK_SET), []);
});

test("the Hacktribe and the synth build do not get it, and no set is refused for it", () => {
  for (const build of ["hacktribe", "synth"]) {
    const chosen = selectFor(ALL, build);
    assert.equal(chosen.patches.some(p => p.id === "ht-osc"), false, build);
  }
  assert.deepEqual(selectFor(ALL, "hacktribe").reasons, []);
  assert.equal(selectFor([PATCH], "hacktribe").reasons.length, 0);
});

test("the assembler and the patch builder agree with the committed patch", { skip }, () => {
  const run = spawnSync(python(), [join(dir, "patch/ht_osc.py"), "--vsb", stock], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/ht_osc.py --vsb SYSTEM.VSB --out data/patches/ht-osc.json");
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
});

describe("the Hacktribe oscillators in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-11-08/ht-osc, the whole BLECH set on Korg's build: names, card, knob, voice, pattern, export, EXIT and an old settings file", { skip: skipEmu }, async () => {
    const original = new Uint8Array(readFileSync(stock));
    const res = await applyPatches(original, STOCK_SET);
    assert.equal(res.ok, true, res.reasons.join(" "));
    const directory = mkdtempSync(join(tmpdir(), "gelumpe-htosc-"));
    const path = join(directory, "SYSTEM.VSB");
    writeFileSync(path, res.bytes);
    try {
      const run = await exec(python(), [join(dir, "emu/ht_osc_cases.py"), "--vsb", path, ...flashArgs], { timeout: 1_800_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.filter(c => !c.ok), []);
      for (const id of ["ohne-karte-oszillatoren", "datei-eintrag-450-abgelehnt-rest-geladen", "regler-hoch", "pattern-430-nach-neustart", "export-ohne-421-bis-499", "exit-wie-firmware", "alte-einstellung-bit-6-oszillatoren"]) {
        assert.ok(report.some(c => c.id === `ht-osc:${id}`), id);
      }
      assert.equal(run.status, 0);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
