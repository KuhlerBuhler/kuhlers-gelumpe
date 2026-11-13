import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { emuPython } from "./support/emu.mjs";

test("the voice watcher permits only read commands and detects changing bindings", () => {
  const result = spawnSync(emuPython(), ["-m", "unittest", "discover", "-s", "tools/device", "-p", "test_sample_voice_watch.py"], {
    encoding: "utf8", timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});
