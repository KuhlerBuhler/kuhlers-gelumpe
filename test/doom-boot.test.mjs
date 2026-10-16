import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { delimiter } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = process.env.E2_EMU_PYTHON || fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const required = process.env.E2_EMU_REQUIRED === "1" || process.env.E2_LOCAL_REQUIRED === "1";

test("Doom boot probe runs SD, LCD and panel without sampler tasks and preserves every existing start mode", {
  skip: !required ? "requires the documented local firmware and flash dump" : false,
}, () => {
  const base = process.env.E2_VSB;
  const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
  assert.ok(base && existsSync(base), "E2_VSB must name the local firmware");
  assert.ok(flash.length && flash.every(existsSync), "E2_FLASH must name the required local flash dump");
  const result = spawnSync(python, ["tools/doom/boot_probe.py", "--base", base, "--flash", ...flash], {
    cwd: root, encoding: "utf8", timeout: 300_000, maxBuffer: 4 * 1024 * 1024,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, true);
  assert.equal(report.checks.length, 25);
  assert.deepEqual(report.checks.filter(check => !check.ok), []);
  assert.deepEqual(report.active.tasks, [1, 8]);
  assert.deepEqual(report.active.sampler, []);
  assert.deepEqual(report.active.status, [5, 0, 1024, 0, 0, 1, 0]);
  assert.equal(report.active.screen, null);
  assert.equal(report.active.lcd_sha256, report.frame_sha256);
  assert.equal(report.active.read_sha256, report.frame_sha256);
  for (const mask of ["00000000", "00002000", "00002408"]) {
    assert.ok(report.checks.some(check => check.id === `normal-${mask}` && check.ok));
  }
  for (const name of ["update-offer", "panel-update"]) {
    for (const mask of ["00000000", "00000408"]) {
      assert.ok(report.checks.some(check => check.id === `${name}-${mask}` && check.ok));
    }
  }
});
