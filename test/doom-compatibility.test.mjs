import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { delimiter, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { run } from "./support/spawn.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = process.env.E2_EMU_PYTHON || "python3";
const available = (await run(python, ["--version"], { timeout: 10_000 })).status === 0;
const required = process.env.E2_DOOM_REQUIRED === "1";
const script = "tools/doom/compatibility.py";

test("Doom compatibility refuses a synthetic image without the Doom boot hook", {
  skip: !available && !required ? "requires Python" : false,
}, async () => {
  assert.ok(available, "Python is required");
  const directory = mkdtempSync(join(tmpdir(), "gelumpe-doom-compat-refused-"));
  const image = join(directory, "own-fixture.bin");
  const report = join(directory, "report.json");
  writeFileSync(image, Buffer.alloc(0x200100, 255));
  const result = await run(python, [script, "--image", image, "--report", report], {
    cwd: root, timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 1, result.stdout + result.stderr);
  const checks = JSON.parse(readFileSync(report, "utf8"));
  assert.equal(checks.ok, false);
  assert.ok(checks.entries.some(entry => entry.id === "doom:boot-hook" && !entry.ok));
});

test("Current Doom firmware preserves TAP motion, SHIFT plus TAP, app capture and optional SysEx", {
  skip: !required ? "requires E2_DOOM_REQUIRED=1 and local firmware artifacts" : false,
}, async () => {
  assert.ok(available, "Python is required");
  const image = process.env.E2_DOOM_IMAGE;
  const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
  const sysex = process.env.E2_DOOM_SYSEX_CASES;
  assert.ok(image && existsSync(image), "E2_DOOM_IMAGE must name the built current firmware");
  assert.ok(flash.length && flash.every(existsSync), "E2_FLASH must name the local flash dump");
  if (sysex) assert.ok(existsSync(sysex), "E2_DOOM_SYSEX_CASES must name the external case source");
  const report = process.env.E2_DOOM_COMPAT_REPORT || join(mkdtempSync(join(tmpdir(), "gelumpe-doom-compat-")), "report.json");
  const result = await run(python, [script, "--image", image, "--flash", ...flash,
    ...(sysex ? ["--sysex-cases", sysex] : []), "--report", report], {
    cwd: root, timeout: 1_800_000, maxBuffer: 8 * 1024 * 1024,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const checks = JSON.parse(readFileSync(report, "utf8"));
  assert.equal(checks.ok, true);
  assert.deepEqual(checks.entries.filter(entry => !entry.ok), []);
  for (const name of ["on_in_the_middle_of_the_bar", "off_in_the_middle_of_the_bar",
    "shift_tap_is_the_bpm_page", "app_owns_tap"]) {
    assert.ok(checks.entries.some(entry => entry.id === `tapmotion:${name}`), name);
  }
  assert.deepEqual(checks.groups.tap_motion, [0, 3, 6]);
  if (sysex) {
    assert.deepEqual(checks.groups.sysex, [0, 1, 2]);
    assert.ok(checks.entries.some(entry => entry.id === "sysex:info"));
    assert.ok(checks.entries.some(entry => entry.id === "sysex:write_random"));
  }
});
