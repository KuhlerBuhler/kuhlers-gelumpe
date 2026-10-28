import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatches } from "../src/patch.mjs";
import { buildOf, sha256 } from "../src/firmware.mjs";
import { loadBlechSet, BLECH_SET_URL, VERIFIED_URL } from "../src/patcher.mjs";
import { emuPython } from "./support/emu.mjs";
import { run as exec } from "./support/spawn.mjs";
import { makePattern } from "./helpers.mjs";

// The app's check boots the start scenarios from the user's own flash, but the cases of the patches expect the Init
// patterns of a blank flash (one bar, no chain). A used flash must not change their result. The flash here is built
// from our own pattern blocks, never a dump.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const hacktribe = vsb && buildOf(new Uint8Array(readFileSync(vsb))) === "hacktribe";
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : !hacktribe ? "E2_VSB is not Hacktribe" : false;

const root = fileURLToPath(new URL("../", import.meta.url));
const checker = join(root, "tools/emu/check.py");
const PATTERNS = 0x240000, BLOCK = 0x4000, LENGTH = 37;      // pattern bank in the flash; block offset 37: bars minus one

/** The red's blank flash with 250 patterns of eight bars in the bank. */
async function usedFlash() {
  const blank = await exec(emuPython(), ["-c", "import sys; from machine import blank_flash; sys.stdout.buffer.write(blank_flash().hex().encode())"],
    { cwd: join(root, "tools/emu"), timeout: 60_000, maxBuffer: 40 * 1024 * 1024 });
  assert.equal(blank.status, 0, blank.stderr);
  const flash = new Uint8Array(Buffer.from(blank.stdout, "hex"));
  for (let n = 0; n < 250; n++) {
    const pattern = makePattern({ name: `P${n + 1}` });
    pattern[LENGTH] = 7;
    flash.set(pattern, PATTERNS + n * BLOCK);
  }
  return flash;
}

const cases = report => report.checks.filter(c => !/^(header|dsp_stream|boot:|update_offer|panel_update|start_mode:|kill_switch|dsp_boot_once|start_phase)/.test(c.id))
  .map(c => [c.id, c.ok]);

test("check: a used flash boots the start scenarios and leaves the cases of the patches as on a blank one", { skip, timeout: 4 * 3600_000 }, async () => {
  const readJson = url => JSON.parse(readFileSync(join(root, url), "utf8"));
  const original = new Uint8Array(readFileSync(vsb));
  const res = await applyPatches(original, (await loadBlechSet(readJson, BLECH_SET_URL)).patches);
  assert.equal(res.ok, true, res.reasons.join(" "));
  const output = await sha256(res.bytes);
  assert.ok(readJson(VERIFIED_URL).results.some(r => r.output === output), "the copy is a verified one");
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-check-flash-"));
  try {
    const patched = join(dir, "SYSTEM.VSB"), own = join(dir, "flash.bin");
    writeFileSync(patched, res.bytes);
    writeFileSync(own, await usedFlash());
    const span = ([at, n]) => `0x${at.toString(16)}:${n}`;
    const args = [checker, "--base", vsb, "--patched", patched, ...res.allow.flatMap(s => ["--allow", span(s)]), ...res.allowCode.flatMap(s => ["--allow-code", span(s)])];
    const reports = [];
    for (const extra of [[], ["--boot-flash", own]]) {
      const run = await exec(emuPython(), [...args, ...extra], { timeout: 2 * 3600_000, maxBuffer: 16 * 1024 * 1024 });
      assert.ifError(run.error);
      reports.push(JSON.parse(run.stdout));
    }
    const [blank, used] = reports;
    assert.equal(blank.ok, true, JSON.stringify(blank.checks.filter(c => !c.ok)));
    assert.ok(used.checks.find(c => c.id === "boot:normal").ok, "the own flash boots to the main screen");
    assert.deepEqual(cases(used), cases(blank));
    assert.equal(used.ok, true, JSON.stringify(used.checks.filter(c => !c.ok)));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
