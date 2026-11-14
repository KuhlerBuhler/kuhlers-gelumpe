import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { emuPython } from "./support/emu.mjs";

test("the experimental Blackfin backend bounds worker failures and checks generated programs", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "discover", "-s", "tools/emu", "-p", "test_blackfin_*.py"], {
    encoding: "utf8", timeout: 60_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});
