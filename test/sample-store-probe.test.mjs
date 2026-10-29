import { test } from "node:test";
import assert from "node:assert/strict";
import { emuPython } from "./support/emu.mjs";
import { run } from "./support/spawn.mjs";

test("the device card probe refuses collisions and unconfirmed execution, and restores owned RAM", async () => {
  const result = await run(emuPython(), ["tools/device/test_sample_store_probe.py"], { timeout: 30_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr || result.stdout);
});

test("the device card probe runs with native file APIs and preserves the generated active library", {
  skip: !process.env.E2_VSB && "E2_VSB not set",
}, async () => {
  for (const source of [process.env.E2_VSB, process.env.E2_STOCK_VSB].filter(Boolean)) {
    const result = await run(emuPython(), ["tools/emu/sample_store_probe_cases.py", "--vsb", source], { timeout: 60_000 });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr || result.stdout);
    const report = JSON.parse(result.stdout);
    assert.equal(report.hardware_contact, false);
    assert.equal(report.checks.length, 1);
    assert.deepEqual(report.checks.filter(c => !c.ok), []);
  }
});
