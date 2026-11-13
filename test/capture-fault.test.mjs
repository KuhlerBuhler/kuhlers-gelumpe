import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { emuPython } from "./support/emu.mjs";

test("capture failure guards preserve native frames and refuse false completion", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "discover", "-s", "tools/patch", "-p", "test_capture_fault.py"], {
    encoding: "utf8", timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});
