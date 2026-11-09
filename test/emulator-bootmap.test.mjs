import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { emuPython } from "./support/emu.mjs";

test("the startup trace retains startup work and stops before main-screen frames", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "discover", "-s", "tools/emu", "-p", "test_bootmap.py"], {
    encoding: "utf8", timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});
