import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { emuPython } from "./support/emu.mjs";

test("sample file leases serialize readers and writers and retain uncertain catalogue state", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "discover", "-s", "tools/patch", "-p", "test_sample_owner.py"], {
    encoding: "utf8", timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});
