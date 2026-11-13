import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { emuPython } from "./support/emu.mjs";

test("SysEx guards preserve live swap code and protect the remaining released RAM", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "discover", "-s", "tools/emu", "-p", "test_sysex_guards.py"], {
    encoding: "utf8", timeout: 60_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
