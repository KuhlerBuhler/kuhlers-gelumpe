import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { emuPython } from "./support/emu.mjs";
import { run } from "./support/spawn.mjs";
import { loadBlechSet, BLECH_SET_URL } from "../src/patcher.mjs";
import { applyPatches } from "../src/patch.mjs";

test("native snapshots stream complete sample entries through the journalled writer", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "discover", "-s", "tools/patch", "-p", "test_sample_snapshot.py"], {
    encoding: "utf8", timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});

test("snapshot entries survive native FatFs writes and reload with the original PCM", {
  skip: !process.env.E2_VSB && !process.env.E2_STOCK_VSB && "own red firmware not set",
}, async () => {
  const set = await loadBlechSet(async url => JSON.parse(readFileSync(new URL(`../${url}`, import.meta.url), "utf8")), BLECH_SET_URL);
  const directory = mkdtempSync(join(tmpdir(), "gelumpe-sample-snapshot-"));
  try {
    for (const original of [process.env.E2_VSB, process.env.E2_STOCK_VSB].filter(Boolean)) {
      const patched = await applyPatches(new Uint8Array(readFileSync(original)), set.patches);
      assert.equal(patched.ok, true, patched.reasons?.join(" "));
      const path = join(directory, "patched.vsb");
      writeFileSync(path, patched.bytes);
      const result = await run(emuPython(), ["tools/emu/sample_snapshot_cases.py", "--patched", path], { timeout: 180_000 });
      assert.ifError(result.error);
      assert.equal(result.status, 0, result.stderr || result.stdout);
      const report = JSON.parse(result.stdout);
      assert.equal(report.hardware_contact, false);
      assert.equal(report.audio, false);
      assert.equal(report.dma, false);
      assert.equal(report.checks.length, 4);
      assert.deepEqual(report.checks.filter(check => !check.ok), []);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
