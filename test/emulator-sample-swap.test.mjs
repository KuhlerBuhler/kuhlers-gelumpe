import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { emuPython } from "./support/emu.mjs";

test("native sample allocation reclaims the tail but leaves interior holes", { skip: !process.env.E2_VSB && "E2_VSB not set" }, () => {
  const result = spawnSync(emuPython(), ["tools/emu/sample_swap_cases.py", "--vsb", process.env.E2_VSB], {
    encoding: "utf8", timeout: 60_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.hardware_contact, false);
  assert.equal(report.dsp_model, "not used");
  assert.equal(report.checks.length, 8);
  for (const check of report.checks) assert.equal(check.ok, true, check.id);
});
