import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { emuPython } from "./support/emu.mjs";

test("physical sample versions distinguish old DSP rows from replaced file entries", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "discover", "-s", "tools/patch", "-p", "test_sample_versions.py"], {
    encoding: "utf8", timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});
