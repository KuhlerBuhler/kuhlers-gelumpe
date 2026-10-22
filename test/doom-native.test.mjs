import { test } from "node:test";
import assert from "node:assert/strict";
import { run } from "./support/spawn.mjs";
import { existsSync, mkdtempSync } from "node:fs";
import { delimiter, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = process.env.E2_EMU_PYTHON || fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const required = process.env.E2_DOOM_REQUIRED === "1";
const build = process.env.E2_DOOM_BUILD;

function localFile(name) {
  const path = process.env[name];
  assert.ok(path && existsSync(path), `${name} must name the documented local artifact`);
  return path;
}

test("Native Doom adapter obeys read-only files, heap, input, real clock reads and quit states on ARM", {
  skip: !build ? "requires E2_DOOM_BUILD with the built native ARM runtime" : false,
}, async () => {
  assert.ok(existsSync(join(build, "doom-runtime.bin")));
  assert.ok(existsSync(join(build, "symbols.txt")));
  const result = await run(python, ["tools/doom/runtime_tests.py", "--build", build, "-v"], {
    cwd: root, timeout: 60_000, maxBuffer: 1024 * 1024,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stderr, /Ran 15 tests/);
  assert.match(result.stderr, /\bOK\b/);
});

test("Original Doom plays through native drivers, changes level, quits and powers off", {
  skip: !required ? "requires E2_DOOM_REQUIRED=1 and documented local firmware artifacts" : false,
}, async () => {
  const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
  assert.ok(flash.length && flash.every(existsSync), "E2_FLASH must name the required local flash dump");
  const output = process.env.E2_DOOM_REPORT ? join(process.env.E2_DOOM_REPORT, "playable") : mkdtempSync(join(tmpdir(), "gelumpe-doom-playable-"));
  const result = await run(python, ["tools/doom/run_runtime.py",
    "--image", localFile("E2_DOOM_IMAGE"), "--program", localFile("E2_DOOM_PROGRAM"),
    "--wad", localFile("E2_DOOM_WAD"), "--flash", ...flash,
    "--seconds", "200", "--card-mib", "512", "--scenario", "controls", "--output", output], {
    cwd: root, timeout: 900_000, maxBuffer: 8 * 1024 * 1024,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, true);
  assert.equal(report.state.stage, 6);
  assert.equal(report.state.error, 0);
  assert.equal(report.powered, false);
  assert.ok(report.state.frames > 0 && report.state.gametic > 0);
  assert.ok(report.state.key_events >= 2 && report.state.file_reads > 0 && report.state.bytes_read > 0);
  assert.ok(report.controls.checks.every(check => check.ok));
  for (const id of ["turn", "forward", "fire", "use", "main-menu", "new-game-e2m1", "level2-spi-frame", "quit-dialog", "quit-stopped", "power-off"]) {
    assert.ok(report.controls.checks.some(check => check.id === id && check.ok), id);
  }
  assert.ok(existsSync(join(output, "game-frame.png")));
  assert.ok(report.game_frame_pixels > 0 && report.game_frame_pixels < 8192);
  assert.equal(report.guards_ok, true);
  assert.deepEqual(report.tasks, [1, 8]);
  assert.ok(report.sampler.every(name => ["globals", "patterns"].includes(name)), "only what the firmware reads before it mounts the card");
  assert.deepEqual(report.asserts, []);
  assert.equal(report.sd_write_calls, 0);
  assert.equal(report.sd_write_commands, 0);
  assert.equal(report.sd_unchanged, true);
});

test("Doom firmware preserves all boot modes and safely reports SD and WAD failures", {
  skip: !required ? "requires E2_DOOM_REQUIRED=1 and documented local firmware artifacts" : false,
}, async () => {
  const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
  assert.ok(flash.length && flash.every(existsSync), "E2_FLASH must name the required local flash dump");
  const output = process.env.E2_DOOM_REPORT || mkdtempSync(join(tmpdir(), "gelumpe-doom-regression-"));
  const result = await run(python, ["tools/doom/runtime_regression.py",
    "--base", localFile("E2_VSB"), "--image", localFile("E2_DOOM_IMAGE"),
    "--program", localFile("E2_DOOM_PROGRAM"), "--wad", localFile("E2_DOOM_WAD"),
    "--flash", ...flash, "--output", output], {
    cwd: root, timeout: 900_000, maxBuffer: 4 * 1024 * 1024,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, true);
  assert.equal(report.count, 34);
  assert.equal(report.passed, report.count);
  assert.deepEqual(report.failed, []);
  assert.ok(existsSync(report.report));
});
